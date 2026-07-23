"""CLI entry point. Used as:

    fraud-risk-engine              # help
    fraud-risk-engine doctor       # check Python env
    fraud-risk-engine build        # build + persist dataset
    fraud-risk-engine detect       # run local detector
    fraud-risk-engine serve        # launch FastAPI
    fraud-risk-engine schema       # print GSQL schema

(Or: python -m app.cli ...)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import get_settings
from .loader.synth_generator import build_dataset, dataset_to_jsonl_bundles
from .runner import ClientKind, LocalRunner, RemoteRunner, make_runner


def cmd_doctor(_: argparse.Namespace) -> int:
    import httpx
    import fastapi
    import pydantic

    s = get_settings()
    print(f"python : {sys.version.split()[0]}")
    print(f"fastapi: {fastapi.__version__}")
    print(f"pydantic: {pydantic.__version__}")
    try:
        import httpx as _h  # noqa: F401
        print(f"httpx : {_h.__version__}")
    except Exception:
        print("httpx : NOT INSTALLED")
    print(f"TigerGraph target: {s.restpp_url} graph={s.tg_graph_name}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    from .api import _persist_dataset, DATA_SEED_DIR, _build_dataset_from_settings

    settings = get_settings()
    if args.bare:
        ds = _build_dataset_from_settings(settings)
    else:
        ds = build_dataset(
            accounts=args.accounts or settings.synth_accounts,
            devices=args.devices or settings.synth_devices,
            merchants=args.merchants or settings.synth_merchants,
            transactions=args.transactions or settings.synth_transactions,
            fraud_rings=args.fraud_rings or settings.synth_fraud_rings,
            seed=args.seed or settings.synth_seed,
        )
    manifest = _persist_dataset(ds, DATA_SEED_DIR)
    counts = manifest.get("totals", {})
    print("Wrote dataset to", DATA_SEED_DIR)
    for k, v in counts.items():
        print(f"  {k:>16}: {v}")
    print(f"  planted_rings : {len(manifest.get('planted_rings', []))}")
    return 0


def cmd_detect(args: argparse.Namespace) -> int:
    from .api import _build_dataset_from_settings, STATE

    settings = get_settings()
    ds = STATE.get("latest_dataset") or _build_dataset_from_settings(settings)

    if args.client == ClientKind.TG:
        # Forced TG path: do not fall back, so the user sees a degraded
        # run instead of silently getting local results.
        runner: LocalRunner | RemoteRunner = RemoteRunner(dataset=None)
    elif args.client == ClientKind.LOCAL:
        runner = LocalRunner(ds)
    else:  # auto
        runner = make_runner(ClientKind.AUTO, dataset=ds)

    run = runner.run()
    print(f"client  : {args.client}")
    print(f"backend : {run.backend}")
    print(f"status  : {run.status}")
    print(f"alerts  : {len(run.alerts)}")
    for a in run.alerts:
        print(f"  - [{a.severity:>8}] {a.kind:<20} score={a.score} :: {a.title}")
    print(f"metrics : {run.metrics}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.api:app",
        host=settings.app_host,
        port=args.port or settings.app_port,
        reload=False,
        log_level=settings.app_log_level,
    )
    return 0


def cmd_schema(_: argparse.Namespace) -> int:
    from .schema import GSQL_SCHEMA

    sys.stdout.write(GSQL_SCHEMA)
    sys.stdout.write("\n")
    return 0


def cmd_queries(_: argparse.Namespace) -> int:
    from .queries.fraud_queries import (
        GSQL_BURST_TRANSACTIONS,
        GSQL_PAGERANK_ACCOUNTS,
        GSQL_SHARED_DEVICE_RINGS,
        GSQL_TRANSACTION_RINGS,
    )

    for name, body in [
        ("transactionRings", GSQL_TRANSACTION_RINGS),
        ("sharedDeviceRings", GSQL_SHARED_DEVICE_RINGS),
        ("burstTransactions", GSQL_BURST_TRANSACTIONS),
        ("pageRankAccounts", GSQL_PAGERANK_ACCOUNTS),
    ]:
        print(f"-- {name}")
        print(body)
        print()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fraud-risk-engine")
    sub = parser.add_subparsers(dest="cmd", required=False)

    sub.add_parser("doctor")
    p = sub.add_parser("build")
    p.add_argument("--seed", type=int)
    p.add_argument("--accounts", type=int)
    p.add_argument("--devices", type=int)
    p.add_argument("--merchants", type=int)
    p.add_argument("--transactions", type=int)
    p.add_argument("--fraud-rings", type=int)
    p.add_argument("--bare", action="store_true")
    p_detect = sub.add_parser("detect")
    p_detect.add_argument(
        "--client",
        choices=[c.value for c in ClientKind],
        default=ClientKind.AUTO.value,
        help="detection backend: auto (TG→local), local only, tg only (no fallback)",
    )
    p = sub.add_parser("serve")
    p.add_argument("--port", type=int)
    sub.add_parser("schema")
    sub.add_parser("queries")

    ns = parser.parse_args(argv if argv is not None else sys.argv[1:])
    cmd = ns.cmd or "doctor"
    dispatch = {
        "doctor": cmd_doctor,
        "build": cmd_build,
        "detect": cmd_detect,
        "serve": cmd_serve,
        "schema": cmd_schema,
        "queries": cmd_queries,
    }
    return dispatch[cmd](ns)


if __name__ == "__main__":
    sys.exit(main())