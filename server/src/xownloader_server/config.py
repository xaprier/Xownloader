from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    client_api_token: SecretStr | None = None
    admin_api_token: SecretStr | None = None
    host: str = "127.0.0.1"
    port: int = 8000
    download_directory: Path = Path("./data/downloads")
    database_path: Path = Path("./data/xownloader.db")
    retention_hours: int = Field(default=24, gt=0)
    max_concurrent_downloads: int = Field(default=2, gt=0)
    max_queue_size: int = Field(default=50, gt=0)
    rate_limit_requests_per_minute: int = Field(default=10, gt=0)
    preview_rate_limit_requests_per_minute: int = Field(default=30, gt=0)
    max_file_size_mb: int = Field(default=2048, gt=0)
    min_free_disk_mb: int = Field(default=1024, ge=0)
    cleanup_interval_minutes: int = Field(default=15, gt=0)
    allowed_output_formats: str = "mp4,mp3"
    allowed_video_qualities: str = "480p,720p,1080p"
    allowed_audio_bitrates: str = "128K,192K,320K"
    cors_allowed_origins: str = "http://localhost:8080,http://127.0.0.1:8080"
    instagram_username: str | None = None
    instagram_password: SecretStr | None = None
    instagram_totp_seed: SecretStr | None = None
    instagram_session_path: Path = Path("./data/instagram_session.json")
    instagram_download_delay_seconds: float = Field(default=2.0, ge=0)

    @property
    def output_formats(self) -> frozenset[str]:
        return frozenset(item.strip().lower() for item in self.allowed_output_formats.split(","))

    @property
    def video_qualities(self) -> frozenset[str]:
        return frozenset(item.strip().lower() for item in self.allowed_video_qualities.split(","))

    @property
    def audio_bitrates(self) -> frozenset[str]:
        return frozenset(item.strip().upper() for item in self.allowed_audio_bitrates.split(","))

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_allowed_origins.split(",") if item.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="XOWNLOADER_",
        extra="ignore",
    )


settings = Settings()
