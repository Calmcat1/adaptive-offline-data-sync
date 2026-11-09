from fastapi import APIRouter, Depends, HTTPException, Query
from app.database import get_db
from app.schemas import SyncRequest
from app.security import get_current_user
from app.utils import now_utc, serialize_doc
from app.adaptive_engine_v1 import recommend_sync, train_model

router = APIRouter(prefix="/sync", tags=["Synchronization"])

@router.post("/decision")
async def get_sync_decision(payload: SyncRequest, user=Depends(get_current_user)):
    context = payload.model_dump(exclude={"records"})
    context["queue_size"] = len(payload.records)
    decision = recommend_sync(context)
    return {"decision": decision, "pending_records": len(payload.records)}

@router.post("/execute")
async def execute_sync(payload: SyncRequest, user=Depends(get_current_user)):
    db = get_db()
    context = payload.model_dump(exclude={"records"})
    context["queue_size"] = len(payload.records)
    decision = recommend_sync(context)
    if not decision["should_sync"]:
        return {"status": "deferred", "decision": decision, "accepted": 0, "conflicts": 0, "failed": len(payload.records)}

    max_records = decision.get("max_records", len(payload.records))
    batch = payload.records[:max_records]
    accepted, conflicts, failed = [], [], []
    started = now_utc()

    for item in batch:
        try:
            existing = await db.field_records.find_one({
                "owner_id": user["_id"], "client_record_id": item.client_record_id
            })
            if existing:
                # Idempotent retry if same logical record and same version.
                if existing.get("version", 1) == item.version and existing.get("data") == item.data:
                    accepted.append(item.client_record_id)
                    continue
                # Preserve server version and store incoming version for explicit resolution.
                await db.field_records.update_one({"_id": existing["_id"]}, {"$set": {
                    "conflict": True,
                    "sync_status": "conflict",
                    "client_conflict_data": item.data,
                    "client_conflict_version": item.version,
                    "conflict_detected_at": now_utc(),
                }})
                conflicts.append(item.client_record_id)
            else:
                await db.field_records.insert_one({
                    "owner_id": user["_id"],
                    "client_record_id": item.client_record_id,
                    "data": item.data,
                    "client_updated_at": item.client_updated_at,
                    "server_updated_at": now_utc(),
                    "version": item.version,
                    "sync_status": "synced",
                    "conflict": False,
                    "created_at": now_utc(),
                })
                accepted.append(item.client_record_id)
        except Exception:
            failed.append(item.client_record_id)

    completed = now_utc()
    history = {
        "owner_id": user["_id"],
        "created_at": completed,
        "started_at": started,
        "completed_at": completed,
        "network_type": payload.network_type,
        "signal_strength": payload.signal_strength,
        "bandwidth_kbps": payload.bandwidth_kbps,
        "latency_ms": payload.latency_ms,
        "battery_percent": payload.battery_percent,
        "queue_size": len(payload.records),
        "sent_count": len(batch),
        "accepted_count": len(accepted),
        "conflict_count": len(conflicts),
        "failed_count": len(failed),
        "sync_success": len(failed) == 0 and len(conflicts) == 0,
        "duration_ms": max(0.0, (completed - started).total_seconds() * 1000),
        "strategy": decision["strategy"],
    }
    await db.sync_history.insert_one(history)
    await db.network_observations.insert_one({
        "owner_id": user["_id"], "created_at": completed,
        "network_type": payload.network_type, "signal_strength": payload.signal_strength,
        "bandwidth_kbps": payload.bandwidth_kbps, "latency_ms": payload.latency_ms,
        "battery_percent": payload.battery_percent, "queue_size": len(payload.records),
        "sync_success": history["sync_success"], "duration_ms": history["duration_ms"],
    })
    return {
        "status": "completed" if not failed and not conflicts else "completed_with_issues",
        "decision": decision,
        "accepted_record_ids": accepted,
        "conflict_record_ids": conflicts,
        "failed_record_ids": failed,
        "not_processed_record_ids": [r.client_record_id for r in payload.records[max_records:]],
        "history": {k: v for k, v in history.items() if k not in ("owner_id",)},
    }

@router.get("/history")
async def sync_history(limit: int = Query(default=50, ge=1, le=200), user=Depends(get_current_user)):
    cursor = get_db().sync_history.find({"owner_id": user["_id"]}).sort("created_at", -1).limit(limit)
    return {"history": [serialize_doc(doc) async for doc in cursor]}

@router.get("/stats")
async def sync_stats(user=Depends(get_current_user)):
    db = get_db()
    query = {"owner_id": user["_id"]}
    total = await db.sync_history.count_documents(query)
    successes = await db.sync_history.count_documents({**query, "sync_success": True})
    conflicts = await db.field_records.count_documents({**query, "conflict": True})
    pending = await db.field_records.count_documents({**query, "sync_status": "pending"})
    return {
        "total_sync_attempts": total,
        "successful_sync_attempts": successes,
        "success_rate_percent": round(successes / total * 100, 2) if total else 0,
        "unresolved_conflicts": conflicts,
        "pending_records": pending,
    }

# @router.post("/train-model")
# async def retrain_model(user=Depends(get_current_user)):
#     # For a student prototype, authenticated users can trigger training.
#     # In a production system, restrict this endpoint to administrators.
#     cursor = get_db().network_observations.find({"owner_id": user["_id"]}).sort("created_at", -1).limit(5000)
#     observations = [doc async for doc in cursor]
#     result = train_model(observations)
#     return result
