import shutil

from xownloader_server.config import Settings
from xownloader_server.errors import InsufficientStorage, PolicyViolation
from xownloader_server.models import DownloadRequest
from xownloader_server.registry import ProviderRegistry, build_registry


class ServerPolicy:
    def __init__(self, settings: Settings, registry: ProviderRegistry | None = None) -> None:
        self.settings = settings
        self.registry = registry or build_registry(settings)

    def validate_request(self, request: DownloadRequest) -> str:
        provider = self.validate_source_url(request.source_url)

        if request.output_format.value not in self.settings.output_formats:
            raise PolicyViolation(f"Output format '{request.output_format.value}' is not enabled")

        if (
            request.video_quality
            and request.video_quality.lower() not in self.settings.video_qualities
        ):
            raise PolicyViolation(f"Video quality '{request.video_quality}' is not enabled")

        if (
            request.audio_bitrate
            and request.audio_bitrate.upper() not in self.settings.audio_bitrates
        ):
            raise PolicyViolation(f"Audio bitrate '{request.audio_bitrate}' is not enabled")

        if getattr(request, "media_selection", None) is not None and provider != "instagram":
            raise PolicyViolation("Media selection is only valid for Instagram")

        return provider

    def validate_source_url(self, source_url: object) -> str:
        hostname = source_url.host.lower().rstrip(".")
        provider = self.registry.provider_for_host(hostname)
        if provider is None:
            raise PolicyViolation("Only YouTube and Instagram URLs are supported")
        if not self.registry.has(provider):
            raise PolicyViolation("Instagram is not configured on this server")
        return provider

    def ensure_disk_capacity(self) -> None:
        self.settings.download_directory.mkdir(parents=True, exist_ok=True)
        free_bytes = shutil.disk_usage(self.settings.download_directory).free
        required_bytes = self.settings.min_free_disk_mb * 1024 * 1024
        if free_bytes < required_bytes:
            raise InsufficientStorage("The server does not have enough free disk space")

    def ensure_file_size(self, file_size_bytes: int) -> None:
        max_bytes = self.settings.max_file_size_mb * 1024 * 1024
        if file_size_bytes > max_bytes:
            raise PolicyViolation("The downloaded file exceeds the configured size limit")
