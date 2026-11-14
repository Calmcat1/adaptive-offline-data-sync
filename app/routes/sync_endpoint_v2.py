from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from app.adaptive_engine_v3 import recommend_sync
from app.schemas import MetricsContext, SyncRecommendationResponse

router = APIRouter(prefix="/sync", tags=["Sync Recommendation"])

@router.post("/recommend", response_model=SyncRecommendationResponse)
def get_sync_recommendation(context: MetricsContext):
    """Receives metrics context and outputs adaptive sync decision."""
    try:
        return recommend_sync(context.dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/recommend/batch", response_model=List[SyncRecommendationResponse])
def get_batch_sync_recommendation(contexts: List[Dict[str, Any]]):
    """Processes batch dataset inputs for offline/historical evaluation."""
    try:
        return [recommend_sync(ctx) for ctx in contexts]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))