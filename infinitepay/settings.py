from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IPAY_", env_file=".env", extra="ignore")

    db_path: Path = Path.home() / ".infinitepay" / "app.db"
    infinitepay_base_url: str = "https://api.infinitepay.io"
    http_timeout: float = 15.0
    worker_poll_seconds: float = 5.0
    run_inline_worker: bool = True  # set False when running dedicated `ipay worker` service


settings = Settings()
settings.db_path.parent.mkdir(parents=True, exist_ok=True)
