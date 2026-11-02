from bson import ObjectId
from datetime import datetime, timezone

def now_utc():
    return datetime.now(timezone.utc)

def serialize_doc(doc: dict) -> dict:
    if not doc:
        return doc
    result = dict(doc)
    if "_id" in result:
        result["id"] = str(result.pop("_id"))
    for key, value in list(result.items()):
        if isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
    return result
