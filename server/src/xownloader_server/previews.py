from pydantic import HttpUrl

from xownloader_server.config import Settings
from xownloader_server.errors import PolicyViolation, PreviewUnavailable
from xownloader_server.models import PreviewRequest, PreviewResponse
from xownloader_server.policy import ServerPolicy
from xownloader_server.providers import ProviderAdapter, YtDlpAdapter
from xownloader_server.rate_limit import RateLimiter


class PreviewService:
    def __init__(self, settings: Settings, adapter: ProviderAdapter | None = None) -> None:
        self.settings = settings
        self.policy = ServerPolicy(settings)
        self.adapter = adapter or YtDlpAdapter()
        self.rate_limiter = RateLimiter(settings.preview_rate_limit_requests_per_minute)

    async def inspect(self, request: PreviewRequest, client_key: str) -> PreviewResponse:
        self.rate_limiter.check(client_key)
        self.policy.validate_source_url(request.source_url)
        try:
            metadata = await self.adapter.inspect(request.source_url)
        except Exception as error:  # noqa: BLE001
            raise PreviewUnavailable("The provider metadata could not be loaded") from error

        return PreviewResponse(
            source_url=request.source_url,
            provider="youtube",
            title=str(metadata.get("title") or "Untitled media"),
            thumbnail=self._thumbnail(metadata.get("thumbnail")),
            uploader=self._optional_text(metadata.get("uploader")),
            duration_seconds=self._duration(metadata.get("duration")),
            allowed_output_formats=sorted(self.settings.output_formats),
            allowed_video_qualities=sorted(self.settings.video_qualities),
            allowed_audio_bitrates=sorted(self.settings.audio_bitrates),
        )

    @staticmethod
    def _optional_text(value: object) -> str | None:
        return str(value) if value else None

    @staticmethod
    def _duration(value: object) -> int | None:
        return int(value) if isinstance(value, (int, float)) else None

    @staticmethod
    def _thumbnail(value: object) -> HttpUrl | None:
        if not value:
            return None
        try:
            return HttpUrl(str(value))
        except ValueError as error:
            raise PolicyViolation("Provider returned an invalid thumbnail URL") from error