from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId
from app.database import get_db
from app.schemas import FieldRecordIn, ConflictResolutionIn
from app.security import get_current_user
from app.utils import now_utc, serialize_doc

router = APIRouter(prefix="/records", tags=["Field Records"])

@router.post("")
async def create_record(payload: FieldRecordIn, user=Depends(get_current_user)):
    db = get_db()
    owner = user["_id"]
    existing = await db.field_records.find_one({"owner_id": owner, "client_record_id": payload.client_record_id})
    if existing:
        return {"record": serialize_doc(existing), "duplicate": True}
    record = {
        "owner_id": owner,
        "client_record_id": payload.client_record_id,
        "data": payload.data,
        "client_updated_at": payload.client_updated_at,
        "server_updated_at": now_utc(),
        "version": payload.version,
        "sync_status": "synced",
        "conflict": False,
        "created_at": now_utc(),
    }
    await db.field_records.insert_one(record)
    return {"record": serialize_doc(record), "duplicate": False}

@router.get("")
async def list_records(
    sync_status: str | None = Query(default=None, pattern="^(synced|pending|conflict)$"),
    limit: int = Query(default=100, ge=1, le=500),
    user=Depends(get_current_user),
):
    query = {"owner_id": user["_id"]}
    if sync_status:
        query["sync_status"] = sync_status
    cursor = get_db().field_records.find(query).sort("server_updated_at", -1).limit(limit)
    return {"records": [serialize_doc(doc) async for doc in cursor], "count": await get_db().field_records.count_documents(query)}

@router.get("/{record_id}")
async def get_record(record_id: str, user=Depends(get_current_user)):
    if not ObjectId.is_valid(record_id):
        raise HTTPException(status_code=400, detail="Invalid record ID.")
    doc = await get_db().field_records.find_one({"_id": ObjectId(record_id), "owner_id": user["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Record not found.")
    return serialize_doc(doc)

@router.post("/{record_id}/resolve")
async def resolve_conflict(record_id: str, payload: ConflictResolutionIn, user=Depends(get_current_user)):
    if not ObjectId.is_valid(record_id):
        raise HTTPException(status_code=400, detail="Invalid record ID.")
    db = get_db()
    doc = await db.field_records.find_one({"_id": ObjectId(record_id), "owner_id": user["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Record not found.")
    if not doc.get("conflict"):
        raise HTTPException(status_code=409, detail="This record has no unresolved conflict.")
    data = payload.resolved_data if payload.resolved_data is not None else (
        doc["data"] if payload.strategy == "server_wins" else doc.get("client_conflict_data", doc["data"])
    )
    await db.field_records.update_one({"_id": doc["_id"]}, {"$set": {
        "data": data, "conflict": False, "sync_status": "synced",
        "conflict_resolution": payload.strategy, "server_updated_at": now_utc()
    }, "$unset": {"client_conflict_data": ""}})
    updated = await db.field_records.find_one({"_id": doc["_id"]})
    return {"record": serialize_doc(updated)}
