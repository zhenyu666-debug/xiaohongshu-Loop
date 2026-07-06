"""pbp-api: thin FastAPI service exposing donor-screener-pbp candidate scoring results.

Reads from `data/candidates.csv` (header: id,smiles,score,descriptor_*) and exposes:
- GET /healthz
- GET /api/candidates (list with optional score range filter)
- GET /api/candidates/{id}
- GET /api/candidates/top20
- GET /api/candidates/distribution
"""
__version__ = "0.1.0"