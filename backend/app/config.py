from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "MedAssist"
    environment: str = "development"
    secret_key: str = "dev-secret-change-me"
    fernet_key: str = ""

    # SQLite file under backend/data/. Cross-platform, no server required.
    database_url: str = "sqlite+aiosqlite:///./data/medassist.db"

    # Chroma persistent store (LangChain-backed RAG).
    chroma_dir: str = "./data/chroma"
    chroma_collection: str = "disease_kb"

    jwt_lifetime_seconds: int = 900
    refresh_lifetime_seconds: int = 604800
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""

    ollama_url: str = "http://localhost:11434"
    medgemma_model: str = "medgemma:4b"

    frontend_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
