from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    download_directory: Path = Path("./data/downloads")
    retention_hours: int = 24
    max_concurrent_downloads: int = 2

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="XOWNLOADER_",
        extra="ignore",
    )


settings = Settings()
