"""TigerGraph loader package — schema + queries + data upload orchestration."""

from .tg_loader import (
    LoaderResult,
    ensure_schema,
    install_queries,
    load_dataset,
    upsert_vertices,
    upsert_edges,
    ping,
)

__all__ = [
    "LoaderResult",
    "ensure_schema",
    "install_queries",
    "load_dataset",
    "upsert_vertices",
    "upsert_edges",
    "ping",
]