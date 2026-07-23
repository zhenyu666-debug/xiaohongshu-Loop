"""Top-level runner abstraction.

W:cli-1 in ``graph_chain.tiger.md`` calls for a single ``Runner`` interface
that hides whether the detection run happens against the local in-memory
:class:`GeneratedDataset` or against a real TigerGraph RESTPP endpoint.

This module exposes:

- :class:`Runner` — the protocol every runner implements
- :class:`LocalRunner` — wraps :class:`LocalDetector`
- :class:`RemoteRunner` — wraps :class:`TigerGraphDetector` with optional
  fallback to the local detector when TigerGraph is unreachable
- :func:`make_runner` — factory used by ``app.cli`` so the CLI ``detect``
  subcommand can dispatch on a single ``--client {auto,local,tg}`` flag

The previous CLI in ``app.cli`` hard-coded :func:`run_local_detector`.
This module is the missing piece so the same code path serves all three
modes (``auto``, ``local``, ``tg``) without changing how FastAPI calls
detect — :func:`run_remote_detector` keeps its existing semantics.
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable

from .detection import (
    DetectionRun,
    LocalDetector,
    TigerGraphDetector,
    run_remote_detector,
)
from .loader.synth_generator import GeneratedDataset


class ClientKind(str, Enum):
    """CLI-selectable detection backend.

    ``AUTO`` is the wide path: try TigerGraph first, fall back to the local
    detector if RESTPP is unreachable or returns no alerts. ``LOCAL`` and
    ``TG`` force a single backend (useful for repro / benchmarking).
    """

    AUTO = "auto"
    LOCAL = "local"
    TG = "tg"


@runtime_checkable
class Runner(Protocol):
    """A detection runner. Single method: :meth:`run`."""

    def run(self) -> DetectionRun:
        ...


class LocalRunner:
    """Runner that runs the pure-Python :class:`LocalDetector`."""

    def __init__(
        self,
        dataset: GeneratedDataset,
        *,
        ring_min_len: int = 3,
        shared_device_min: int = 3,
        burst_min_count: int = 12,
        top_k: int = 50,
    ) -> None:
        self.dataset = dataset
        self.thresholds = {
            "ring_min_len": ring_min_len,
            "shared_device_min": shared_device_min,
            "burst_min_count": burst_min_count,
            "top_k": top_k,
        }

    def run(self) -> DetectionRun:
        detector = LocalDetector(self.dataset, **self.thresholds)
        return detector.run()


class RemoteRunner:
    """Runner that prefers TigerGraph and falls back to local.

    When ``dataset`` is provided and TigerGraph returns no alerts (or is
    unreachable), this runner delegates to :func:`run_local_detector` so the
    call site sees a usable :class:`DetectionRun` either way.
    """

    def __init__(
        self,
        dataset: GeneratedDataset | None = None,
    ) -> None:
        self.dataset = dataset
        self.detector = TigerGraphDetector()

    def run(self) -> DetectionRun:
        return run_remote_detector(fallback_dataset=self.dataset)


def make_runner(
    client: ClientKind | str,
    dataset: GeneratedDataset | None = None,
) -> Runner:
    """Build the right :class:`Runner` for ``client``.

    ``auto`` → :class:`RemoteRunner` (TG first, falls back to local when
    ``dataset`` is not None, returns degraded run when it is).
    ``local`` → :class:`LocalRunner` (requires ``dataset``).
    ``tg`` → :class:`RemoteRunner` forced; ignored dataset is fine.
    """
    kind = ClientKind(client)
    if kind is ClientKind.LOCAL:
        if dataset is None:
            raise ValueError("LocalRunner requires a GeneratedDataset")
        return LocalRunner(dataset)
    return RemoteRunner(dataset)
