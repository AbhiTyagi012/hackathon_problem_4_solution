from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # points at app/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Decision Automation Platform"
    log_level: str = "INFO"
    cors_origins: str = "*"

    rules_dir: str = str(BASE_DIR / "rules" / "data")
    catalog_path: str = str(BASE_DIR / "catalog" / "data" / "products.json")
    purchase_history_path: str = str(BASE_DIR / "history" / "data" / "purchase_history.json")

    # Grok / xAI LLM configuration
    xai_api_key: str = ""
    grok_model: str = "grok-4"
    grok_base_url: str = "https://api.x.ai/v1"
    llm_timeout_seconds: float = 30.0

    # Gemini embeddings configuration
    gemini_api_key: str = ""
    gemini_embedding_model: str = "text-embedding-004"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.xai_api_key.strip())

    @property
    def embedding_enabled(self) -> bool:
        return bool(self.gemini_api_key.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
