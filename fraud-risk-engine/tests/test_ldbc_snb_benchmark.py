"""Tests for the LDBC SNB benchmark harness.

Covers:
- :class:`QueryResult` and :class:`QueryStats` dataclasses
- :class:`ResultCollector` ingestion, aggregation, and serialisation
- :class:`QueryExecutor` (mock) execution, latency simulation, and error injection
- :class:`LDBCSNBBenchmark` power test, throughput test, and report generation
- CLI argument parsing
"""

from __future__ import annotations

import json
import tempfile
import time
from datetime import datetime
from pathlib import Path

import pytest

from app.eval.ldbc_snb_benchmark import (
    BASE_LATENCY_MS,
    BenchmarkReport,
    INTERACTIVE_COMPLEX,
    INTERACTIVE_SIMPLE,
    LDBCSNBBenchmark,
    QueryExecutor,
    QueryResult,
    QueryStats,
    ResultCollector,
    default_query_set,
    generate_params,
)


# ---------------------------------------------------------------------------
# Fast mock helpers
# ---------------------------------------------------------------------------

def _make_result(
    query_id: str,
    latency_ms: float = 1.0,
    success: bool = True,
    error: str | None = None,
) -> QueryResult:
    """Factory for a QueryResult with a real wall-clock time."""
    t0 = time.perf_counter()
    return QueryResult(
        query_id=query_id,
        start_time=t0,
        end_time=t0,
        latency_ms=latency_ms,
        success=success,
        error=error,
        result_count=1,
        params={},
    )


def _instant_executor(
    *,
    base_latency_ms: float = 1.0,
    jitter_pct: float = 0.0,
    error_rate: float = 0.0,
) -> QueryExecutor:
    """Mock executor that bypasses actual delays via pluggable sleep_fn."""
    return QueryExecutor(
        host="mock", port=0, graph="mock",
        base_latency_ms=base_latency_ms,
        jitter_pct=jitter_pct,
        error_rate=error_rate,
        sleep_fn=lambda _: None,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def collector() -> ResultCollector:
    return ResultCollector()


# ---------------------------------------------------------------------------
# QueryResult & QueryStats dataclasses
# ---------------------------------------------------------------------------


class TestQueryResult:
    def test_fields(self) -> None:
        r = QueryResult(
            query_id="IC01",
            start_time=1.0,
            end_time=2.0,
            latency_ms=1000.0,
            success=True,
            error=None,
            result_count=42,
            params={"personId": 123},
        )
        assert r.query_id == "IC01"
        assert r.latency_ms == 1000.0
        assert r.success is True
        assert r.error is None
        assert r.result_count == 42
        assert r.duration_ms == 1000.0

    def test_to_dict(self) -> None:
        r = QueryResult(
            query_id="IS01",
            start_time=0.0,
            end_time=0.5,
            latency_ms=500.0,
            success=False,
            error="timeout",
            result_count=0,
            params={},
        )
        d = r.to_dict()
        assert d["query_id"] == "IS01"
        assert d["success"] is False
        assert d["error"] == "timeout"


class TestQueryStats:
    def test_fields(self) -> None:
        s = QueryStats(
            count=10,
            min_ms=5.0,
            max_ms=95.0,
            mean_ms=50.0,
            p50_ms=48.0,
            p90_ms=88.0,
            p99_ms=94.0,
            success_rate=0.95,
        )
        assert s.count == 10
        assert s.success_rate == 0.95

    def test_to_dict(self) -> None:
        s = QueryStats(
            count=1, min_ms=1.0, max_ms=1.0,
            mean_ms=1.0, p50_ms=1.0,
            p90_ms=1.0, p99_ms=1.0, success_rate=1.0,
        )
        d = s.to_dict()
        assert "count" in d
        assert "mean_ms" in d


# ---------------------------------------------------------------------------
# ResultCollector — ingestion
# ---------------------------------------------------------------------------


class TestResultCollectorIngestion:
    def test_add_single(self, collector: ResultCollector) -> None:
        collector.add(_make_result("IC01"))
        assert collector.results_count() == 1

    def test_extend(self, collector: ResultCollector) -> None:
        collector.extend([_make_result("IC01") for _ in range(5)])
        assert collector.results_count() == 5


# ---------------------------------------------------------------------------
# ResultCollector — aggregation
# ---------------------------------------------------------------------------


class TestResultCollectorAggregation:
    def test_collect_latency_one_query(self, collector: ResultCollector) -> None:
        for ms in [10.0, 20.0, 30.0]:
            collector.add(_make_result("IC01", latency_ms=ms))
        collector.add(_make_result("IC02", latency_ms=99.0))
        lats = collector.collect_latency("IC01")
        assert lats == pytest.approx([10.0, 20.0, 30.0])

    def test_collect_latency_skips_failures(self, collector: ResultCollector) -> None:
        for _ in range(3):
            collector.add(_make_result("IC01", success=False, error="boom"))
        collector.add(_make_result("IC01", latency_ms=20.0, success=True))
        lats = collector.collect_latency("IC01")
        assert lats == pytest.approx([20.0])

    def test_collect_throughput(self, collector: ResultCollector) -> None:
        for _ in range(7):
            collector.add(_make_result("IC01"))
        for _ in range(3):
            collector.add(_make_result("IC01", success=False, error="err"))
        ok, fail = collector.collect_throughput()
        assert ok == 7
        assert fail == 3

    def test_query_stats_min_max_mean(self, collector: ResultCollector) -> None:
        for ms in [5.0, 10.0, 15.0, 20.0, 25.0]:
            collector.add(_make_result("IC01", latency_ms=ms))
        s = collector.query_stats("IC01")
        assert s.count == 5
        assert s.min_ms == pytest.approx(5.0)
        assert s.max_ms == pytest.approx(25.0)
        assert s.mean_ms == pytest.approx(15.0)
        assert s.success_rate == pytest.approx(1.0)

    def test_query_stats_empty_returns_defaults(self, collector: ResultCollector) -> None:
        s = collector.query_stats("NONEXISTENT")
        assert s.count == 0
        assert s.success_rate == 0.0
        assert s.min_ms == 0.0

    def test_all_stats_multiple_queries(self, collector: ResultCollector) -> None:
        """Each query_id's success_rate is computed over its own results only."""
        for qid in ("IC01", "IC02", "IC03"):
            collector.add(_make_result(qid))
        stats = collector.all_stats()
        assert set(stats.keys()) == {"IC01", "IC02", "IC03"}
        for s in stats.values():
            assert s.count == 1
            assert s.success_rate == pytest.approx(1.0)

    def test_success_rate_ignores_other_queries(self, collector: ResultCollector) -> None:
        """IC01 has 1 success out of 2; IC02 has 1 success out of 1."""
        collector.add(_make_result("IC01", success=True))
        collector.add(_make_result("IC01", success=False))
        collector.add(_make_result("IC02", success=True))
        assert collector.query_stats("IC01").success_rate == pytest.approx(0.5)
        assert collector.query_stats("IC02").success_rate == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# ResultCollector — serialisation
# ---------------------------------------------------------------------------


class TestResultCollectorSerialisation:
    def test_export_json(self, collector: ResultCollector) -> None:
        collector.add(_make_result("IC01"))
        collector.add(_make_result("IC02"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.jsonl"
            collector.export_json(path)
            lines = path.read_text(encoding="utf-8").splitlines()
            assert len(lines) == 2
            for line in lines:
                d = json.loads(line)
                assert "query_id" in d
                assert "latency_ms" in d

    def test_results_count(self, collector: ResultCollector) -> None:
        assert collector.results_count() == 0
        collector.add(_make_result("IC01"))
        assert collector.results_count() == 1


# ---------------------------------------------------------------------------
# ResultCollector — percentile edge cases
# ---------------------------------------------------------------------------


class TestPercentileEdgeCases:
    def test_single_latency_value(self, collector: ResultCollector) -> None:
        collector.add(_make_result("IC01", latency_ms=42.0))
        s = collector.query_stats("IC01")
        assert s.min_ms == s.max_ms == s.p50_ms == s.p90_ms == s.p99_ms == pytest.approx(42.0)

    def test_two_latency_values(self, collector: ResultCollector) -> None:
        collector.add(_make_result("IC01", latency_ms=10.0))
        collector.add(_make_result("IC01", latency_ms=20.0))
        s = collector.query_stats("IC01")
        assert s.count == 2
        assert s.success_rate == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# QueryExecutor mock
# ---------------------------------------------------------------------------


class TestQueryExecutorMock:
    def test_execute_returns_result(self) -> None:
        ex = _instant_executor()
        result = ex.execute("IC01", {"personId": 42})
        assert isinstance(result, QueryResult)
        assert result.query_id == "IC01"
        assert result.success is True
        assert result.error is None

    def test_execute_batch_sequential(self) -> None:
        ex = _instant_executor()
        items = [("IS01", {}), ("IS02", {})]
        results = ex.execute_batch(items, max_workers=1)
        assert len(results) == 2
        assert all(r.success for r in results)

    def test_execute_batch_parallel(self) -> None:
        ex = _instant_executor()
        items = [("IS01", {}), ("IS02", {}), ("IS03", {}), ("IS04", {})]
        results = ex.execute_batch(items, max_workers=4)
        assert len(results) == 4
        assert all(r.success for r in results)

    def test_error_rate_injection(self) -> None:
        ex = _instant_executor(error_rate=0.8)
        failures = 0
        for _ in range(20):
            r = ex.execute("IC01", {})
            if not r.success:
                failures += 1
        assert failures >= 10, f"Expected ≥10 failures with 80% error rate, got {failures}"

    def test_jitter_within_bounds(self) -> None:
        ex = _instant_executor(base_latency_ms=100.0, jitter_pct=0.10)
        latencies = [ex.execute("IC01", {}).latency_ms for _ in range(50)]
        for lat in latencies:
            assert 90.0 <= lat <= 110.0, f"Latency {lat} outside ±10% bounds"


# ---------------------------------------------------------------------------
# generate_params
# ---------------------------------------------------------------------------


class TestGenerateParams:
    def test_deterministic_same_seed(self) -> None:
        assert generate_params("IC01", seed=123) == generate_params("IC01", seed=123)

    def test_deterministic_different_seeds(self) -> None:
        assert generate_params("IC01", seed=1) != generate_params("IC01", seed=2)

    def test_returns_dict(self) -> None:
        assert isinstance(generate_params("IC01", seed=0), dict)

    def test_ic_complex_params_have_limit(self) -> None:
        """IC queries should include a 'limit' parameter for bounded result sets."""
        ic_params = generate_params("IC01", seed=0)
        assert "limit" in ic_params

    def test_is_params_have_limit(self) -> None:
        """IS queries should include a 'limit' parameter for bounded result sets."""
        is_params = generate_params("IS01", seed=0)
        assert "limit" in is_params


# ---------------------------------------------------------------------------
# default_query_set
# ---------------------------------------------------------------------------


class TestDefaultQuerySet:
    def test_interactive_28_queries(self) -> None:
        qs = default_query_set("interactive")
        assert len(qs) == 28
        assert qs[:14] == INTERACTIVE_COMPLEX
        assert qs[14:] == INTERACTIVE_SIMPLE

    def test_unknown_workload_raises(self) -> None:
        with pytest.raises(ValueError):
            default_query_set("bi")


# ---------------------------------------------------------------------------
# LDBCSNBBenchmark — warmup
# ---------------------------------------------------------------------------


class TestWarmup:
    def test_warmup_runs(self) -> None:
        ex = _instant_executor()
        bench = LDBCSNBBenchmark(executor=ex, seed=0)
        bench.run_warmup(queries=3)  # must not raise

    def test_warmup_does_not_pollute_collector(self) -> None:
        ex = _instant_executor()
        bench = LDBCSNBBenchmark(executor=ex, seed=0)
        bench.run_warmup(queries=5)
        assert bench._collector.results_count() == 0


# ---------------------------------------------------------------------------
# LDBCSNBBenchmark — power test
# ---------------------------------------------------------------------------


class TestPowerTest:
    def test_power_test_correct_count(self) -> None:
        ex = _instant_executor()
        bench = LDBCSNBBenchmark(executor=ex, seed=0)
        bench.run_power_test(query_count=20)
        assert bench._collector.results_count() == 20

    def test_power_test_records_elapsed(self) -> None:
        ex = _instant_executor()
        bench = LDBCSNBBenchmark(executor=ex, seed=0)
        bench.run_power_test(query_count=10)
        assert bench._power_elapsed_ms > 0.0

    def test_power_test_custom_queries(self) -> None:
        ex = _instant_executor()
        bench = LDBCSNBBenchmark(executor=ex, seed=0)
        bench.run_power_test(query_count=4, queries=["IC01", "IC02"])
        stats = bench._collector.all_stats()
        assert set(stats.keys()) == {"IC01", "IC02"}
        assert stats["IC01"].count == 2
        assert stats["IC02"].count == 2

    def test_power_test_all_success(self) -> None:
        ex = _instant_executor(error_rate=0.0)
        bench = LDBCSNBBenchmark(executor=ex, seed=0)
        bench.run_power_test(query_count=10)
        ok, fail = bench._collector.collect_throughput()
        assert ok == 10
        assert fail == 0


# ---------------------------------------------------------------------------
# LDBCSNBBenchmark — throughput test
# ---------------------------------------------------------------------------


class TestThroughputTest:
    def test_throughput_test_runs(self) -> None:
        ex = _instant_executor()
        bench = LDBCSNBBenchmark(executor=ex, seed=0)
        bench.run_throughput_test(duration_s=0.05, concurrency=1)
        assert bench._throughput_elapsed_ms > 0.0

    def test_throughput_test_completes_within_duration(self) -> None:
        ex = _instant_executor()
        bench = LDBCSNBBenchmark(executor=ex, seed=0)
        target = 0.1
        bench.run_throughput_test(duration_s=target, concurrency=1)
        # Allow generous 3x tolerance for CI overhead / process startup
        assert bench._throughput_elapsed_ms / 1000 <= target * 3

    def test_throughput_test_qps_calculated(self) -> None:
        ex = _instant_executor()
        bench = LDBCSNBBenchmark(executor=ex, seed=0)
        bench.run_throughput_test(duration_s=0.1, concurrency=2)
        report = bench.generate_report()
        expected_qps = bench._collector.results_count() / (bench._throughput_elapsed_ms / 1000)
        assert report.throughput_test_qps == pytest.approx(expected_qps, rel=1e-3)


# ---------------------------------------------------------------------------
# LDBCSNBBenchmark — report
# ---------------------------------------------------------------------------


class TestBenchmarkReport:
    def test_generate_report_fields(self) -> None:
        ex = _instant_executor()
        bench = LDBCSNBBenchmark(executor=ex, seed=0, scale_factor=10.0)
        bench._start_time = "2026-07-21T00:00:00Z"
        bench._end_time = "2026-07-21T00:01:00Z"
        bench.run_power_test(query_count=5)
        report = bench.generate_report()

        assert isinstance(report, BenchmarkReport)
        assert report.benchmark_name == "ldbc_snb"
        assert report.scale_factor == 10.0
        assert report.workload == "interactive"
        assert report.power_test_queries == 5
        assert report.power_test_success == 5
        assert report.power_test_failures == 0
        assert report.start_time == "2026-07-21T00:00:00Z"
        assert report.end_time == "2026-07-21T00:01:00Z"

    def test_report_to_dict_serializable(self) -> None:
        ex = _instant_executor()
        bench = LDBCSNBBenchmark(executor=ex, seed=0)
        bench._start_time = "2026-07-21T00:00:00Z"
        bench._end_time = "2026-07-21T00:00:10Z"
        bench.run_power_test(query_count=3)
        report = bench.generate_report()
        d = report.to_dict()
        assert isinstance(d, dict)
        json.dumps(d)  # must not raise
        assert "query_stats" in d
        assert "power_test_elapsed_ms" in d

    def test_report_query_stats_populated(self) -> None:
        ex = _instant_executor()
        bench = LDBCSNBBenchmark(executor=ex, seed=0)
        bench.run_power_test(query_count=10, queries=["IC01"])
        report = bench.generate_report()
        assert "IC01" in report.query_stats
        stats = report.query_stats["IC01"]
        assert stats.count == 10
        assert stats.success_rate == pytest.approx(1.0)
        assert stats.min_ms > 0.0
        assert stats.max_ms >= stats.min_ms

    def test_report_empty_if_no_queries(self) -> None:
        ex = _instant_executor()
        bench = LDBCSNBBenchmark(executor=ex, seed=0)
        report = bench.generate_report()
        assert report.power_test_queries == 0
        assert report.throughput_test_queries_completed == 0

    def test_duration_seconds_sum(self) -> None:
        ex = _instant_executor()
        bench = LDBCSNBBenchmark(executor=ex, seed=0)
        bench.run_power_test(query_count=5)
        bench.run_throughput_test(duration_s=0.1, concurrency=1)
        report = bench.generate_report()
        expected = (bench._power_elapsed_ms + bench._throughput_elapsed_ms) / 1000
        assert report.duration_seconds == pytest.approx(expected, rel=1e-3)


# ---------------------------------------------------------------------------
# run_all
# ---------------------------------------------------------------------------


class TestRunAll:
    def test_run_all_produces_report(self) -> None:
        ex = _instant_executor()
        bench = LDBCSNBBenchmark(executor=ex, seed=0)
        # run_all calls run_warmup (fast with instant executor), power, then throughput
        bench.run_warmup(skip=True)  # skip warmup to avoid it running queries
        bench.run_power_test(query_count=5)
        bench.run_throughput_test(duration_s=0.1, concurrency=1)
        bench._start_time = datetime.now().isoformat()
        bench._end_time = datetime.now().isoformat()
        report = bench.generate_report()
        assert isinstance(report, BenchmarkReport)
        # power_test_queries = exactly the power test count (throughput excluded)
        assert report.power_test_queries == 5
        assert report.start_time != ""
        assert report.end_time != ""

    def test_run_all_timestamps_valid(self) -> None:
        ex = _instant_executor()
        bench = LDBCSNBBenchmark(executor=ex, seed=0)
        report = bench.run_all(power_count=3, throughput_duration_s=0.1)
        assert report.start_time != ""
        assert report.end_time != ""
        assert report.end_time >= report.start_time


# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------


class TestCLI:
    def test_build_parser(self) -> None:
        from app.eval.ldbc_snb_benchmark import _build_parser
        p = _build_parser()
        assert p is not None

    def test_default_args(self) -> None:
        from app.eval.ldbc_snb_benchmark import _build_parser
        args = _build_parser().parse_args([])
        assert args.mode == "all"
        assert args.scale_factor == 1.0
        assert args.power_count == 100
        assert args.concurrency == 4

    def test_custom_args(self) -> None:
        from app.eval.ldbc_snb_benchmark import _build_parser
        args = _build_parser().parse_args([
            "--mode", "power",
            "--sf", "10",
            "--power-count", "200",
            "--error-rate", "0.01",
        ])
        assert args.mode == "power"
        assert args.scale_factor == 10.0
        assert args.power_count == 200
        assert args.error_rate == 0.01
