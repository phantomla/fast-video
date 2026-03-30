"""Dashboard API — cost tracking endpoints."""
from fastapi import APIRouter, Query
from app.services import cost_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", summary="Cost stats by day / model / type")
def get_stats(days: int = Query(default=30, ge=1, le=365)) -> dict:
    return cost_service.get_stats(days)
