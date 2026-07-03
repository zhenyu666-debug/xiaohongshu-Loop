from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from pbp_api import dataset

router = APIRouter()


@router.get("/candidates")
async def list_candidates(
    score_min: Optional[float] = Query(None, ge=0, le=10),
    score_max: Optional[float] = Query(None, ge=0, le=10),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    """List candidates ordered by score desc, optionally filtered by score range."""
    items = dataset.filter_by_score(score_min, score_max)
    total = len(items)
    page = items[offset : offset + limit]
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [c.to_dict() for c in page],
    }


@router.get("/candidates/top20")
async def top20() -> dict:
    """Top-20 candidates by score."""
    items = dataset.load_all()[:20]
    return {"items": [c.to_dict() for c in items]}


@router.get("/candidates/distribution")
async def distribution(buckets: int = Query(10, ge=2, le=50)) -> dict:
    """Score histogram."""
    return {"buckets": buckets, "items": dataset.distribution(buckets)}


@router.get("/candidates/{cid}")
async def get_candidate(cid: int) -> dict:
    for c in dataset.load_all():
        if c.id == cid:
            return c.to_dict()
    raise HTTPException(status_code=404, detail=f"candidate {cid} not found")