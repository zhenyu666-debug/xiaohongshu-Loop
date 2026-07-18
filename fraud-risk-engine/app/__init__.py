"""fraud-risk-engine top-level package."""

from .api import VERSION, create_app
from .config import Settings, get_settings

__all__ = ["app", "create_app", "Settings", "VERSION", "get_settings"]

# A module-level ``app`` so ``uvicorn fraud_risk_engine:app`` works.
app = create_app()
