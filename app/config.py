from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_path: Path = Path.home() / ".infinitepay" / "app.db"
    infinitepay_base_url: str = "https://api.checkout.infinitepay.io"
    http_timeout: float = 15.0
    worker_poll_seconds: float = 5.0
    run_inline_worker: bool = True

    webhook_encryption_key: str = ""


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.db_path.parent.mkdir(parents=True, exist_ok=True)
    return s
