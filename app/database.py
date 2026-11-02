from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

client: AsyncIOMotorClient | None = None
db = None

async def connect_to_mongo():
    global client, db
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DATABASE]
    # Indexes support common lookup and sync-history operations.
    await db.users.create_index("email", unique=True)
    await db.field_records.create_index([("owner_id", 1), ("client_record_id", 1)], unique=True)
    await db.field_records.create_index([("owner_id", 1), ("sync_status", 1)])
    await db.sync_history.create_index([("owner_id", 1), ("created_at", -1)])
    await db.network_observations.create_index([("owner_id", 1), ("created_at", -1)])

async def close_mongo_connection():
    global client
    if client is not None:
        client.close()
        client = None

def get_db():
    if db is None:
        raise RuntimeError("Database is not connected.")
    return db
