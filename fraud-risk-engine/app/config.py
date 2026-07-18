"""Typed application settings.

All runtime configuration flows through :class:`Settings`. We intentionally
keep this dependency-free (no ``pydantic-settings``) so the package works
in air-gapped CI. Settings read from ``os.environ`` with sane defaults.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal


class Settings:
    """Top-level configuration object for fraud-risk-engine."""

    def __init__(self, env: dict[str, str] | None = None) -> None:
        e = env if env is not None else dict(os.environ)

        # --- TigerGraph ---
        self.tg_host: str = e.get("TG_HOST", "localhost")
        self.tg_restpp_port: int = int(e.get("TG_RESTPP_PORT", "14240"))
        self.tg_gsql_port: int = int(e.get("TG_GSQL_PORT", "14240"))
        self.tg_username: str = e.get("TG_USERNAME", "tigergraph")
        self.tg_password: str = e.get("TG_PASSWORD", "tigergraph")
        self.tg_graph_name: str = e.get("TG_GRAPH_NAME", "FraudRisk")

        # --- Application ---
        self.app_host: str = e.get("APP_HOST", "0.0.0.0")
        self.app_port: int = int(e.get("APP_PORT", "8765"))
        self.app_log_level: Literal["debug", "info", "warning", "error"] = e.get(
            "APP_LOG_LEVEL", "info"
        )  # type: ignore[assignment]
        self.app_cors_origins: str = e.get("APP_CORS_ORIGINS", "*")

        # --- Synthetic data ---
        self.synth_accounts: int = int(e.get("SYNTH_ACCOUNTS", "1200"))
        self.synth_devices: int = int(e.get("SYNTH_DEVICES", "900"))
        self.synth_merchants: int = int(e.get("SYNTH_MERCHANTS", "300"))
        self.synth_transactions: int = int(e.get("SYNTH_TRANSACTIONS", "20000"))
        self.synth_fraud_rings: int = int(e.get("SYNTH_FRAUD_RINGS", "6"))
        self.synth_seed: int = int(e.get("SYNTH_SEED", "20260716"))

        # --- Detection thresholds ---
        self.thresh_ring_min_len: int = int(e.get("THRESH_RING_MIN_LEN", "3"))
        self.thresh_shared_device_min: int = int(e.get("THRESH_SHARED_DEVICE_MIN", "3"))
        self.thresh_burst_tx_window_min: int = int(e.get("THRESH_BURST_TX_WINDOW_MIN", "10"))
        self.thresh_burst_tx_count: int = int(e.get("THRESH_BURST_TX_COUNT", "12"))
        self.thresh_pagerank_topk: int = int(e.get("THRESH_PAGERANK_TOPK", "50"))

    # --- Derived helpers ---
    @property
    def restpp_url(self) -> str:
        return f"http://{self.tg_host}:{self.tg_restpp_port}"

    @property
    def gsql_url(self) -> str:
        return f"http://{self.tg_host}:{self.tg_gsql_port}"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.app_cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.app_cors_origins.split(",") if o.strip()]

    def to_dict(self) -> dict:
        """Public, JSON-serialisable snapshot — used by /api/health."""
        return {
            "tg_host": self.tg_host,
            "tg_restpp_port": self.tg_restpp_port,
            "tg_graph_name": self.tg_graph_name,
            "app_port": self.app_port,
            "synth_accounts": self.synth_accounts,
            "synth_transactions": self.synth_transactions,
            "synth_fraud_rings": self.synth_fraud_rings,
            "synth_seed": self.synth_seed,
            "thresholds": {
                "ring_min_len": self.thresh_ring_min_len,
                "shared_device_min": self.thresh_shared_device_min,
                "burst_tx_window_min": self.thresh_burst_tx_window_min,
                "burst_tx_count": self.thresh_burst_tx_count,
                "pagerank_topk": self.thresh_pagerank_topk,
            },
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()