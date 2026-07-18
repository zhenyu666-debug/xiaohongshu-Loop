"""fraud-risk-engine package entry-point.

Exposes :data:`app` for ``uvicorn fraud_risk_engine.api:app``-style run.
"""

from .api import VERSION, create_app

__all__ = ["app", "create_app", "VERSION"]

# Lazy ``app`` accessor keeps ``uvicorn`` happy at module-import time even
# when the static frontend has not been generated yet.
app = create_app()