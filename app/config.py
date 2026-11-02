from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "Adaptive Offline Data Synchronization API"
    ENVIRONMENT: str = "development"
    API_PREFIX: str = "/api/v1"
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DATABASE: str = "adaptive_sync_db"
    JWT_SECRET_KEY: str = "development-only-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
