"""LDBC SNB benchmark evaluation harness for TigerGraph.

The LDBC Social Network Benchmark (SNB) is the industry-standard workload for
graph databases. This module provides a deterministic benchmark harness that:

- Runs a **power test**: fixed set of queries, measures single-stream latency.
- Runs a **throughput test**: time-bounded, parallel execution, measures QPS.
- Produces a structured :class:`BenchmarkReport` with per-query percentiles.

Architecture
------------

``LDBCSNBBenchmark``
  High-level orchestrator. Exposes ``run_warmup()``, ``run_power_test()``,
  ``run_throughput_test()`` and ``generate_report()``.

``QueryExecutor``
  Abstract execution layer. The default implementation is a mock that adds
  realistic jitter; swap it for a real TigerGraph REST client in production.

``ResultCollector``
  Accumulates raw :class:`QueryResult` objects and produces per-query
  statistics (min / max / mean / p50 / p90 / p99).

TigerGraph REST API
-------------------

Queries are dispatched via the REST++ endpoint::

    POST http://{host}:{port}/restpp/query/{graph}/{query_name}
    Content-Type: application/json
    GS-QUIET: true

Parameters are passed as a JSON body. Install queries first with
``gsql < query.gsql`` or via the TigerGraph Admin portal.

Reference: https://docs.tigergraph.com/tigergraph-server/current/api/built-in-endpoints

LDBC SNB Interactive Workload
-----------------------------

The interactive (BI) workload defines 14 query templates (IC01–IC14 for
interactive complex, IS01–IS14 for interactive simple). Each template is
parameterised by deterministic seed values that produce consistent result
sizes across benchmark runs. The :func:`generate_params` function reproduces
the parameter generation logic.
"""

from __future__ import annotations

import json
import random
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from math import inf
from pathlib import Path
from statistics import mean as _mean
from statistics import quantiles
from threading import Lock
from typing import Any, Callable, Iterable

# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


@dataclass
class QueryResult:
    """Result of a single query execution."""

    query_id: str
    """Short identifier, e.g. ``"IC01"``."""

    start_time: float
    """Wall-clock start (seconds, same reference as :func:`time.perf_counter`)."""

    end_time: float
    """Wall-clock end (seconds)."""

    latency_ms: float
    """End-to-end wall-clock latency in milliseconds."""

    success: bool
    """True when the query completed without an error."""

    error: str | None
    """Error message string when ``success`` is ``False``."""

    result_count: int
    """Number of result rows / vertices returned (0 on error)."""

    params: dict[str, Any]
    """Query parameters used for this invocation."""

    @property
    def duration_ms(self) -> float:
        """Alias for ``latency_ms`` (backwards-compatible accessor)."""
        return self.latency_ms

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QueryStats:
    """Aggregated latency statistics for a single query_id across N runs."""

    count: int
    """Number of successful executions."""

    min_ms: float
    """Minimum latency observed."""

    max_ms: float
    """Maximum latency observed."""

    mean_ms: float
    """Arithmetic mean latency."""

    p50_ms: float
    """50th percentile (median) latency."""

    p90_ms: float
    """90th percentile latency."""

    p99_ms: float
    """99th percentile latency."""

    success_rate: float
    """Fraction of executions that succeeded (0..1)."""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BenchmarkReport:
    """Full benchmark output for one workload."""

    benchmark_name: str
    """Always ``"ldbc_snb"``."""

    scale_factor: float
    """LDBC SF (1, 10, 30, 100 …)."""

    workload: str
    """``"interactive"`` or ``"bi"``."""

    start_time: str
    """ISO-8601 wall-clock start."""

    end_time: str
    """ISO-8601 wall-clock end."""

    duration_seconds: float
    """Total wall-clock elapsed for this benchmark run."""

    # Power test
    power_test_elapsed_ms: float
    power_test_queries: int
    power_test_success: int
    power_test_failures: int

    # Throughput test
    throughput_test_elapsed_ms: float
    throughput_test_queries_completed: int
    throughput_test_qps: float

    # Per-query breakdown
    query_stats: dict[str, QueryStats] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["query_stats"] = {k: v.to_dict() for k, v in self.query_stats.items()}
        return out


# ---------------------------------------------------------------------------
# LDBC SNB Interactive query catalogue
# ---------------------------------------------------------------------------

# The 14 interactive-complex (IC) and 14 interactive-simple (IS) query
# identifiers as defined by the LDBC SNB specification.
INTERACTIVE_COMPLEX = [f"IC{i:02d}" for i in range(1, 15)]
INTERACTIVE_SIMPLE = [f"IS{i:02d}" for i in range(1, 15)]

# Mapping of query_id → estimated base latency in milliseconds.
# These values are calibrated for SF1 on a typical TigerGraph installation.
# Replace with empirical measurements from a calibration run.
BASE_LATENCY_MS: dict[str, float] = {
    **{qid: 15.0 for qid in INTERACTIVE_SIMPLE},  # IS queries are lightweight
    **{qid: 45.0 for qid in INTERACTIVE_COMPLEX},  # IC queries are heavier
}


def default_query_set(workload: str) -> list[str]:
    """Return the default query list for ``workload``."""
    if workload == "interactive":
        return INTERACTIVE_COMPLEX + INTERACTIVE_SIMPLE
    raise ValueError(f"Unknown workload {workload!r}")


# ---------------------------------------------------------------------------
# Parameter generation
# ---------------------------------------------------------------------------


def generate_params(query_id: str, seed: int) -> dict[str, Any]:
    """Generate deterministic query parameters for ``query_id`` from ``seed``.

    Reproduces the LDBC SNB parameter-generation formula::

        param = floor((RAND() * range) + offset)

    The seed drives the deterministic pseudo-random sequence so that two
    benchmark runs with the same seed produce the same parameter sets.

    Parameters
    ----------
    query_id:
        LDBC query identifier, e.g. ``"IC01"``.
    seed:
        Integer seed that drives the RNG.

    Returns
    -------
    dict
        Parameter name → value mapping suitable for JSON serialisation.
    """
    rng = random.Random(seed)

    if query_id.startswith("IS"):
        # Interactive simple queries tend to return 1–100 rows.
        return {
            "personId": int(rng.random() * 1_000_000),
            "maxDate": "2012-11-29",
            "limit": int(rng.random() * 100) + 1,
        }

    # Interactive complex (IC01–IC14)
    ic_idx = INTERACTIVE_COMPLEX.index(query_id) if query_id in INTERACTIVE_COMPLEX else 0

    if ic_idx == 0:  # IC01 — latest posts
        return {
            "personId": int(rng.random() * 1_000_000),
            "maxDate": "2012-11-29",
            "limit": 20,
        }
    if ic_idx == 1:  # IC02 — friends of friends
        return {
            "personId": int(rng.random() * 1_000_000),
            "maxDate": "2012-11-29",
        }
    if ic_idx == 2:  # IC03 — short messages
        return {
            "personId": int(rng.random() * 1_000_000),
            "maxDate": "2012-11-29",
            "limit": 20,
        }
    if ic_idx == 3:  # IC04 — recent comments
        return {
            "personId": int(rng.random() * 1_000_000),
            "maxDate": "2012-11-29",
            "limit": 20,
        }
    if ic_idx == 4:  # IC05 — co-authors
        return {"personId": int(rng.random() * 1_000_000)}
    if ic_idx == 5:  # IC06 — similar interests
        return {
            "tagName": f"Tag_{int(rng.random() * 1000)}",
            "cutoffDate": "2012-11-29",
        }
    if ic_idx == 6:  # IC07 — friend recommendations
        return {"personId": int(rng.random() * 1_000_000), "cutoffDate": "2012-11-29"}
    if ic_idx == 7:  # IC08 — comment replies
        return {"personId": int(rng.random() * 1_000_000), "maxDate": "2012-11-29"}
    if ic_idx == 8:  # IC09 — tag count by year
        return {"tagName": f"Tag_{int(rng.random() * 1000)}"}
    if ic_idx == 9:  # IC10 — messages by year
        return {"year": 2012}
    if ic_idx == 10:  # IC11 — city statistics
        return {"countryName": "Angola"}
    if ic_idx == 11:  # IC12 — related tags
        return {"tagName": f"Tag_{int(rng.random() * 1000)}"}
    if ic_idx == 12:  # IC13 — top posters
        return {"forumId": int(rng.random() * 100_000)}
    # IC14 fallback
    return {
        "personId": int(rng.random() * 1_000_000),
        "maxDate": "2012-11-29",
        "limit": 10,
    }


# ---------------------------------------------------------------------------
# Query executor
# ---------------------------------------------------------------------------


class QueryExecutor:
    """Executes LDBC SNB queries against TigerGraph (or a mock).

    The default ``MockQueryExecutor`` simulates query latency with configurable
    jitter (±10 %) and a configurable error rate. To run against a real
    TigerGraph instance, subclass this and override ``_execute``.
    """

    def __init__(
        self,
        *,
        host: str = "localhost",
        port: int = 14240,
        graph: str = "ldbc",
        secret: str = "",
        base_latency_ms: float | None = None,
        jitter_pct: float = 0.10,
        error_rate: float = 0.0,
        timeout_s: float = 30.0,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.graph = graph
        self.secret = secret
        self.jitter_pct = jitter_pct
        self.error_rate = error_rate
        self.timeout_s = timeout_s
        # Pluggable sleep for tests (bypasses actual delays).
        self._sleep_fn = sleep_fn or time.sleep

        # Resolve per-query base latencies
        if base_latency_ms is not None:
            self._base: Callable[[str], float] = lambda _: base_latency_ms
        else:
            self._base = lambda qid: BASE_LATENCY_MS.get(qid, 30.0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, query_id: str, params: dict[str, Any]) -> QueryResult:
        """Execute a single query and return a :class:`QueryResult`."""
        return self._execute(query_id, params)

    def execute_batch(
        self,
        items: Iterable[tuple[str, dict[str, Any]]],
        *,
        max_workers: int = 1,
    ) -> list[QueryResult]:
        """Execute multiple queries, optionally in parallel.

        Parameters
        ----------
        items:
            Iterable of ``(query_id, params)`` pairs.
        max_workers:
            Thread pool size. ``1`` means sequential (no threading).

        Returns
        -------
        list[QueryResult]
            Results in the same order as ``items``.
        """
        results: list[QueryResult | None] = [None] * sum(1 for _ in items)
        idx_lock = Lock()
        idx = 0

        def _submit(item: tuple[str, dict[str, Any]]) -> None:
            nonlocal idx
            qid, pars = item
            with idx_lock:
                i = idx
                idx += 1
            results[i] = self._execute(qid, pars)

        if max_workers <= 1:
            for item in items:
                _submit(item)
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                futures = [ex.submit(_submit, item) for item in items]
                for f in as_completed(futures):
                    f.result()  # propagate exceptions

        return [r for r in results if r is not None]

    # ------------------------------------------------------------------
    # Core execution (override for real TigerGraph)
    # ------------------------------------------------------------------

    def _execute(self, query_id: str, params: dict[str, Any]) -> QueryResult:
        """Run the query and return a :class:`QueryResult`.

        This base implementation dispatches to ``_execute_mock``, which
        simulates realistic latency with configurable jitter and error rates.
        To run against a live TigerGraph instance, override and call
        ``_execute_real`` instead.
        """
        return self._execute_mock(query_id, params)

    def _execute_real(self, query_id: str, params: dict[str, Any]) -> QueryResult:
        """Execute via TigerGraph REST++ API.

        Raises
        ------
        RuntimeError
            When TigerGraph returns a non-2xx status or times out.
        """
        import urllib.request

        url = f"http://{self.host}:{self.port}/restpp/query/{self.graph}/{query_id}"
        body = json.dumps(params).encode("utf-8")

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "GS-QUIET": "true",
        }
        if self.secret:
            headers["Authorization"] = f"Bearer {self.secret}"

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                data = json.loads(resp.read())
                latency_ms = (time.perf_counter() - t0) * 1000
                # TigerGraph returns a dict with a "results" key.
                result_count = len(data.get("results", []))
                return QueryResult(
                    query_id=query_id,
                    start_time=t0,
                    end_time=time.perf_counter(),
                    latency_ms=latency_ms,
                    success=True,
                    error=None,
                    result_count=result_count,
                    params=params,
                )
        except Exception as exc:  # noqa: BLE001
            return QueryResult(
                query_id=query_id,
                start_time=t0,
                end_time=time.perf_counter(),
                latency_ms=(time.perf_counter() - t0) * 1000,
                success=False,
                error=str(exc),
                result_count=0,
                params=params,
            )

    def _execute_mock(self, query_id: str, params: dict[str, Any]) -> QueryResult:
        """Mock execution that adds realistic jitter and random errors."""
        t0 = time.perf_counter()
        base = self._base(query_id)

        # Random error injection
        if random.random() < self.error_rate:
            latency_ms = base * random.uniform(0.9, 1.1)
            return QueryResult(
                query_id=query_id,
                start_time=t0,
                end_time=time.perf_counter(),
                latency_ms=latency_ms,
                success=False,
                error="Simulated connection timeout",
                result_count=0,
                params=params,
            )

        # Jitter: ±jitter_pct of base latency
        jitter = random.uniform(-self.jitter_pct, self.jitter_pct)
        latency_ms = base * (1.0 + jitter)

        # Simulate actual query execution time via pluggable sleep
        self._sleep_fn(latency_ms / 1000.0)

        result_count = int(random.uniform(0, 100))  # mock row count
        return QueryResult(
            query_id=query_id,
            start_time=t0,
            end_time=time.perf_counter(),
            latency_ms=latency_ms,
            success=True,
            error=None,
            result_count=result_count,
            params=params,
        )


# ---------------------------------------------------------------------------
# Result collector
# ---------------------------------------------------------------------------


class ResultCollector:
    """Accumulates :class:`QueryResult` objects and computes statistics."""

    def __init__(self) -> None:
        self._results: list[QueryResult] = []
        self._lock = Lock()

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def add(self, result: QueryResult) -> None:
        """Record a single query result."""
        with self._lock:
            self._results.append(result)

    def extend(self, results: Iterable[QueryResult]) -> None:
        """Record multiple results at once."""
        with self._lock:
            self._results.extend(results)

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def collect_latency(self, query_id: str) -> list[float]:
        """Return all successful latencies for ``query_id`` in ms."""
        with self._lock:
            return [r.latency_ms for r in self._results if r.query_id == query_id and r.success]

    def collect_throughput(self) -> tuple[int, int]:
        """Return ``(successes, failures)`` across all results."""
        with self._lock:
            ok = sum(1 for r in self._results if r.success)
            return ok, len(self._results) - ok

    def query_stats(self, query_id: str) -> QueryStats:
        """Compute latency statistics for ``query_id``."""
        lats = self.collect_latency(query_id)
        if not lats:
            return QueryStats(
                count=0,
                min_ms=0.0,
                max_ms=0.0,
                mean_ms=0.0,
                p50_ms=0.0,
                p90_ms=0.0,
                p99_ms=0.0,
                success_rate=0.0,
            )

        # Only count results for this query_id when computing success_rate
        with self._lock:
            this_total = sum(1 for r in self._results if r.query_id == query_id)
            this_successes = len(lats)

        success_rate = this_successes / this_total if this_total else 0.0

        p50, p90, p99 = self._percentiles(lats, [50, 90, 99])
        return QueryStats(
            count=this_successes,
            min_ms=min(lats),
            max_ms=max(lats),
            mean_ms=_mean(lats),
            p50_ms=p50,
            p90_ms=p90,
            p99_ms=p99,
            success_rate=success_rate,
        )

    def all_stats(self) -> dict[str, QueryStats]:
        """Compute statistics for every distinct query_id."""
        seen: set[str] = set()
        with self._lock:
            for r in self._results:
                seen.add(r.query_id)
        return {qid: self.query_stats(qid) for qid in sorted(seen)}

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def export_json(self, path: str | Path) -> Path:
        """Write all raw results to a JSON file (one dict per line)."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as fh:
            for r in self._results:
                fh.write(json.dumps(r.to_dict()) + "\n")
        return p

    def results_count(self) -> int:
        """Total number of recorded results."""
        with self._lock:
            return len(self._results)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _percentiles(data: list[float], qs: Iterable[int]) -> list[float]:
        """Return percentile values for ``data`` at the given quantiles."""
        if not data:
            return [0.0] * len(list(qs))
        try:
            # statistics.quantiles returns n-1 boundaries for n cuts.
            breaks = list(quantiles(data, n=100))
            return [breaks[max(0, min(q - 1, len(breaks) - 1))] for q in qs]
        except ValueError:  # not enough data points
            m = _mean(data)
            return [m] * len(list(qs))


# ---------------------------------------------------------------------------
# Benchmark orchestrator
# ---------------------------------------------------------------------------


class LDBCSNBBenchmark:
    """LDBC SNB benchmark runner.

    Parameters
    ----------
    executor:
        :class:`QueryExecutor` instance (default: a mock executor).
    scale_factor:
        LDBC scale factor (1, 10, 30 …). Stored in the report for
        bookkeeping; does not affect execution.
    workload:
        ``"interactive"`` — runs IC + IS query sets.
    seed:
        Master RNG seed for deterministic parameter generation.
    """

    def __init__(
        self,
        executor: QueryExecutor | None = None,
        *,
        scale_factor: float = 1.0,
        workload: str = "interactive",
        seed: int = 42,
    ) -> None:
        self.executor = executor or QueryExecutor()
        self.scale_factor = scale_factor
        self.workload = workload
        self.seed = seed

        self._collector = ResultCollector()
        self._power_elapsed_ms: float = 0.0
        self._throughput_elapsed_ms: float = 0.0
        self._start_time: str = ""
        self._end_time: str = ""
        self._power_test_queries: int = 0

    # ------------------------------------------------------------------
    # Phases
    # ------------------------------------------------------------------

    def run_warmup(
        self,
        *,
        queries: int = 10,
        skip: bool = False,
    ) -> None:
        """Execute ``queries`` warm-up queries to prime caches.

        Warm-up queries do not contribute to the benchmark metrics.
        A separate private executor is used so warm-up results never
        pollute the :class:`ResultCollector`.

        Parameters
        ----------
        queries:
            Number of warm-up queries to run (default 10).
        skip:
            Set to ``True`` to skip warm-up (useful in tests).
        """
        if skip:
            return
        warmup_executor = QueryExecutor(
            host=self.executor.host,
            port=self.executor.port,
            graph=self.executor.graph,
            secret=self.executor.secret,
            jitter_pct=self.executor.jitter_pct,
            error_rate=self.executor.error_rate,
            timeout_s=self.executor.timeout_s,
            sleep_fn=self.executor._sleep_fn,
        )
        warmup_set = [
            (qid, generate_params(qid, self.seed + i))
            for i, qid in enumerate(default_query_set(self.workload)[:queries])
        ]
        warmup_executor.execute_batch(warmup_set, max_workers=1)

    def run_power_test(
        self,
        *,
        query_count: int = 100,
        queries: list[str] | None = None,
    ) -> None:
        """Single-stream power test.

        Runs ``query_count`` queries sequentially, measuring wall-clock time
        from first query start to last query end.

        Parameters
        ----------
        query_count:
            Total number of query executions (default 100).
        queries:
            Query identifiers to use. Defaults to the workload query set.
        """
        query_ids = queries or default_query_set(self.workload)
        t0 = time.perf_counter()

        for i in range(query_count):
            qid = query_ids[i % len(query_ids)]
            params = generate_params(qid, self.seed + i)
            result = self.executor.execute(qid, params)
            self._collector.add(result)
        self._power_elapsed_ms = (time.perf_counter() - t0) * 1000
        self._power_test_queries = query_count

    def run_throughput_test(
        self,
        *,
        duration_s: float = 60.0,
        concurrency: int = 4,
        queries: list[str] | None = None,
    ) -> None:
        """Time-bounded throughput test with parallel execution.

        Generates and executes queries continuously until ``duration_s``
        seconds have elapsed. Measures QPS as ``completed / elapsed``.

        Parameters
        ----------
        duration_s:
            How long to run (default 60 seconds).
        concurrency:
            Number of parallel query workers (default 4).
        queries:
            Query identifiers to use. Defaults to the workload query set.
        """
        query_ids = queries or default_query_set(self.workload)
        stop_at = time.perf_counter() + duration_s
        t0 = time.perf_counter()
        seq = 0

        while time.perf_counter() < stop_at:
            batch_size = max(1, concurrency)
            items: list[tuple[str, dict[str, Any]]] = []
            for _ in range(batch_size):
                if time.perf_counter() >= stop_at:
                    break
                qid = query_ids[seq % len(query_ids)]
                params = generate_params(qid, self.seed + seq)
                items.append((qid, params))
                seq += 1

            if items:
                results = self.executor.execute_batch(items, max_workers=concurrency)
                self._collector.extend(results)

        self._throughput_elapsed_ms = (time.perf_counter() - t0) * 1000

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    def generate_report(self) -> BenchmarkReport:
        """Compile all collected results into a :class:`BenchmarkReport`."""
        success, failures = self._collector.collect_throughput()
        completed = self._collector.results_count()
        qps = completed / (self._throughput_elapsed_ms / 1000) if self._throughput_elapsed_ms > 0 else 0.0

        return BenchmarkReport(
            benchmark_name="ldbc_snb",
            scale_factor=self.scale_factor,
            workload=self.workload,
            start_time=self._start_time,
            end_time=self._end_time,
            duration_seconds=(self._power_elapsed_ms + self._throughput_elapsed_ms) / 1000,
            power_test_elapsed_ms=self._power_elapsed_ms,
            power_test_queries=self._power_test_queries,
            power_test_success=success,
            power_test_failures=failures,
            throughput_test_elapsed_ms=self._throughput_elapsed_ms,
            throughput_test_queries_completed=completed,
            throughput_test_qps=qps,
            query_stats=self._collector.all_stats(),
        )

    # ------------------------------------------------------------------
    # Convenience runners
    # ------------------------------------------------------------------

    def run_all(
        self,
        *,
        power_count: int = 100,
        throughput_duration_s: float = 60.0,
        throughput_concurrency: int = 4,
    ) -> BenchmarkReport:
        """Run warm-up → power test → throughput test, then return the report."""
        self._start_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.run_warmup()
        self.run_power_test(query_count=power_count)
        self.run_throughput_test(
            duration_s=throughput_duration_s,
            concurrency=throughput_concurrency,
        )
        self._end_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return self.generate_report()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> Any:
    import argparse

    p = argparse.ArgumentParser(description="LDBC SNB benchmark harness for TigerGraph")
    p.add_argument("--mode", default="all", choices={"all", "power", "throughput"},
                   help="Which test phase to run")
    p.add_argument("--sf", type=float, default=1.0, dest="scale_factor",
                   help="LDBC scale factor (1, 10, 30 …)")
    p.add_argument("--workload", default="interactive", choices={"interactive"},
                   help="LDBC workload type")
    p.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility")
    p.add_argument("--power-count", type=int, default=100,
                   help="Number of queries in the power test")
    p.add_argument("--duration", type=float, default=60.0,
                   help="Throughput test duration in seconds")
    p.add_argument("--concurrency", type=int, default=4,
                   help="Parallel query workers for throughput test")
    p.add_argument("--host", default="localhost", help="TigerGraph host")
    p.add_argument("--port", type=int, default=14240, help="TigerGraph REST++ port")
    p.add_argument("--graph", default="ldbc", help="TigerGraph graph name")
    p.add_argument("--base-latency", type=float, default=None,
                   dest="base_latency_ms", help="Base latency per query in ms (mock only)")
    p.add_argument("--error-rate", type=float, default=0.0, dest="error_rate",
                   help="Fraction of queries that should fail (0..1)")
    p.add_argument("--output", default="", help="Write JSON report to this path")
    return p


def _main() -> None:
    args = _build_parser().parse_args()

    executor = QueryExecutor(
        host=args.host,
        port=args.port,
        graph=args.graph,
        base_latency_ms=args.base_latency_ms,
        error_rate=args.error_rate,
    )

    bench = LDBCSNBBenchmark(
        executor=executor,
        scale_factor=args.scale_factor,
        workload=args.workload,
        seed=args.seed,
    )

    bench._start_time = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if args.mode in {"all", "power"}:
        bench.run_warmup()
        bench.run_power_test(query_count=args.power_count)

    if args.mode in {"all", "throughput"}:
        bench.run_throughput_test(
            duration_s=args.duration,
            concurrency=args.concurrency,
        )

    bench._end_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
    report = bench.generate_report()

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        print(f"Report written to {out}")
    else:
        print(json.dumps(report.to_dict(), indent=2))


if __name__ == "__main__":
    _main()

__all__ = [
    "BenchmarkReport",
    "INTERACTIVE_COMPLEX",
    "INTERACTIVE_SIMPLE",
    "LDBCSNBBenchmark",
    "QueryExecutor",
    "QueryResult",
    "QueryStats",
    "ResultCollector",
    "default_query_set",
    "generate_params",
]
