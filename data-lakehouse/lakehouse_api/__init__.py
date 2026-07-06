"""lakehouse-api: thin FastAPI service exposing data-lakehouse analytics.

If TRINO_HOST/TRINO_PORT env vars are set and reachable, queries are
forwarded to Trino. Otherwise the service returns deterministic seed
data so the GUI can render meaningful charts during local dev.
"""
__version__ = "0.1.0"