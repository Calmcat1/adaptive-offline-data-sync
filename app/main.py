from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import client, db
from app.config import settings
from app.database import connect_to_mongo, close_mongo_connection
from app.routes import auth, records, network, sync_endpoint_v1, sync_endpoint_v2

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()

app = FastAPI(
    title=settings.APP_NAME,
    description="ADAS:An Adaptive Offline Data Synchronization Framework for Intermittent Network Environments in Kenya",
    version="1.0.0",
    lifespan=lifespan,
)

origins = [item.strip() for item in settings.CORS_ORIGINS.split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(records.router, prefix=settings.API_PREFIX)
app.include_router(sync_endpoint_v2.router, prefix=settings.API_PREFIX)
app.include_router(network.router, prefix=settings.API_PREFIX)

@app.get("/", tags=["Health"])
async def root():
    return {"message": settings.APP_NAME, "docs": "/docs"}

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}

@app.get("/db-test")
def test_database():
    client.admin.command("ping")

    return {
        "status": "connected",
        "database": db.name
    }