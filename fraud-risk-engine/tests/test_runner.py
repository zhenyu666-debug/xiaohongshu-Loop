"""Tests for the runner abstraction (W:cli-1).

Covers:

- :func:`app.runner.make_runner` factory dispatch by ``client``.
- :class:`LocalRunner` producing the same alert kinds as the in-place
  :func:`run_local_detector` for a synthetic dataset.
- :class:`RemoteRunner` falling back to the local detector when TG is
  unreachable (no live RESTPP needed).
- :func:`app.cli.main` accepting the new ``--client`` flag and dispatching
  to the correct runner.
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout

import pytest

from app.cli import main as cli_main
from app.loader.synth_generator import build_dataset
from app.runner import (
    ClientKind,
    LocalRunner,
    RemoteRunner,
    make_runner,
)


def test_make_runner_local() -> None:
    ds = build_dataset(
        accounts=80, devices=40, merchants=15, transactions=600,
        fraud_rings=2, seed=20260724,
    )
    runner = make_runner(ClientKind.LOCAL, dataset=ds)
    assert isinstance(runner, LocalRunner)
    assert runner.dataset is ds


def test_make_runner_local_requires_dataset() -> None:
    with pytest.raises(ValueError, match="requires a GeneratedDataset"):
        make_runner(ClientKind.LOCAL)


def test_make_runner_auto_and_tg_use_remote() -> None:
    ds = build_dataset(
        accounts=80, devices=40, merchants=15, transactions=600,
        fraud_rings=2, seed=20260724,
    )
    auto = make_runner(ClientKind.AUTO, dataset=ds)
    tg = make_runner(ClientKind.TG, dataset=None)
    assert isinstance(auto, RemoteRunner)
    assert isinstance(tg, RemoteRunner)
    # TG path keeps the dataset reference so a future 'no-alert' path can
    # still fall back; AUTO path passes it through to run_remote_detector.
    assert auto.dataset is ds
    assert tg.dataset is None


def test_local_runner_produces_local_alerts() -> None:
    ds = build_dataset(
        accounts=120, devices=80, merchants=20, transactions=2000,
        fraud_rings=4, seed=20260716,
    )
    runner = LocalRunner(ds)
    run = runner.run()
    assert run.backend == "local"
    assert run.status == "ok"
    kinds = {a.kind for a in run.alerts}
    assert {"transaction_ring", "shared_device", "burst_transactions", "pagerank"} <= kinds


def test_remote_runner_falls_back_when_tg_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When RESTPP is unreachable, RemoteRunner must serve the local
    fallback dataset via :func:`run_remote_detector`."""
    from app import detection as det_mod

    ds = build_dataset(
        accounts=120, devices=80, merchants=20, transactions=2000,
        fraud_rings=4, seed=20260716,
    )

    # Force TigerGraphDetector.ping to return False so run_remote_detector
    # walks the fallback branch instead of trying a real HTTP call.
    monkeypatch.setattr(det_mod.TigerGraphDetector, "ping", lambda self: False)

    runner = RemoteRunner(dataset=ds)
    run = runner.run()
    assert run.status in {"ok", "partial"}
    # Backend string should announce a fallback.
    assert "fallback" in run.backend or run.backend.startswith("local")
    assert len(run.alerts) > 0


def test_cli_detect_default_is_auto() -> None:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli_main(["detect"])
    out = buf.getvalue()
    assert rc == 0
    assert "client  : auto" in out
    assert "alerts  :" in out


def test_cli_detect_local_explicit() -> None:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli_main(["detect", "--client", "local"])
    out = buf.getvalue()
    assert rc == 0
    assert "client  : local" in out
    # Forced local path must NOT report a fallback backend.
    assert "fallback" not in out


def test_cli_doctor_still_works() -> None:
    """Regression guard: refactoring the subparser list must not break
    other CLI subcommands."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli_main(["doctor"])
    assert rc == 0
    assert "python :" in buf.getvalue()
