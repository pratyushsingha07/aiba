"""
app/core/config.py
──────────────────
Loads all environment variables from .env (via python-dotenv) and exposes
them as a typed Settings object. Never hardcode credentials — always read from env.
"""
import os
from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Supabase
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_anon_key: str = ""
    database_url: str = ""

    # JWT — your Supabase project's JWT secret (Settings → API → JWT Secret)
    jwt_secret: str = "test-secret-do-not-use-in-production"
    jwt_algorithm: str = "HS256"

    # Upload config
    upload_temp_dir: str = "./tmp/pending"
    upload_ttl_seconds: int = 3600

    # AI Config
    groq_api_key: str = ""
    anthropic_api_key: str = ""
    insight_provider: str = "groq"
    ask_provider: str = "claude"

    model_config = {"env_file": ".env", "extra": "ignore"}


    @field_validator("upload_temp_dir")
    @classmethod
    def ensure_upload_dir_exists(cls, v: str) -> str:
        os.makedirs(v, exist_ok=True)
        return v


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton. Call get_settings() everywhere instead of os.getenv()."""
    return Settings()
