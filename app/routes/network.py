from fastapi import APIRouter, Depends, Query
from app.database import get_db
from app.schemas import NetworkObservationIn
from app.security import get_current_user
from app.utils import now_utc, serialize_doc

router = APIRouter(prefix="/network", tags=["Network Observations"])

@router.post("/observations")
async def add_observation(payload: NetworkObservationIn, user=Depends(get_current_user)):
    doc = {"owner_id": user["_id"], **payload.model_dump(), "created_at": now_utc()}
    result = await get_db().network_observations.insert_one(doc)
    doc["_id"] = result.inserted_id
    return {"observation": serialize_doc(doc)}

@router.get("/observations")
async def list_observations(limit: int = Query(default=100, ge=1, le=1000), user=Depends(get_current_user)):
    cursor = get_db().network_observations.find({"owner_id": user["_id"]}).sort("created_at", -1).limit(limit)
    return {"observations": [serialize_doc(doc) async for doc in cursor]}
