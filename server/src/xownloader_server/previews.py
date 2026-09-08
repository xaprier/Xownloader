import logging

from pydantic import HttpUrl

from xownloader_server.config import Settings
from xownloader_server.errors import (
    PolicyViolation,
    PreviewUnavailable,
    ProviderContentUnavailable,
)
from xownloader_server.models import (
    PreviewMediaItem,
    PreviewRequest,
    PreviewResponse,
)
from xownloader_server.policy import ServerPolicy
from xownloader_server.rate_limit import RateLimiter
from xownloader_server.registry import ProviderRegistry, build_registry

logger = logging.getLogger(__name__)


class PreviewService:
    def __init__(
        self,
        settings: Settings,
        adapter=None,
        registry: ProviderRegistry | None = None,
    ) -> None:
        self.settings = settings
        if registry is not None:
            self.registry = registry
        elif adapter is not None:
            self.registry = ProviderRegistry.with_adapters({adapter.name: adapter})
        else:
            self.registry = build_registry(settings)
        self.policy = ServerPolicy(settings, registry=self.registry)
        self.rate_limiter = RateLimiter(settings.preview_rate_limit_requests_per_minute)

    async def inspect(self, request: PreviewRequest, client_key: str) -> PreviewResponse:
        self.rate_limiter.check(client_key)
        provider = self.policy.validate_source_url(request.source_url)
        adapter = self.registry.adapter_for(provider)
        try:
            metadata = await adapter.inspect(request.source_url)
        except (PreviewUnavailable, ProviderContentUnavailable, PolicyViolation):
            raise
        except Exception as error:  # noqa: BLE001
            logger.exception(
                "preview_inspect_failed",
                extra={"provider": provider, "error_type": type(error).__name__},
            )
            raise PreviewUnavailable("The provider metadata could not be loaded") from error

        if metadata.get("media_items") is not None:
            return self._instagram_response(request.source_url, metadata)
        return self._youtube_response(request.source_url, metadata)

    def _youtube_response(self, source_url, metadata: dict) -> PreviewResponse:
        return PreviewResponse(
            source_url=source_url,
            provider="youtube",
            title=str(metadata.get("title") or "Untitled media"),
            thumbnail=self._thumbnail(metadata.get("thumbnail")),
            uploader=self._optional_text(metadata.get("uploader")),
            duration_seconds=self._int_or_none(metadata.get("duration_seconds")),
            media_items=None,
            allowed_output_formats=sorted(self.settings.output_formats),
            allowed_video_qualities=sorted(self.settings.video_qualities),
            allowed_audio_bitrates=sorted(self.settings.audio_bitrates),
        )

    def _instagram_response(self, source_url, metadata: dict) -> PreviewResponse:
        items = [
            PreviewMediaItem(
                index=item["index"],
                type=item["type"],
                thumbnail=self._thumbnail(item.get("thumbnail")),
                width=self._int_or_none(item.get("width")),
                height=self._int_or_none(item.get("height")),
                duration_seconds=self._int_or_none(item.get("duration_seconds")),
            )
            for item in metadata["media_items"]
        ]
        return PreviewResponse(
            source_url=source_url,
            provider="instagram",
            title=str(metadata.get("title") or "Instagram post"),
            thumbnail=self._thumbnail(metadata.get("thumbnail")),
            uploader=self._optional_text(metadata.get("uploader")),
            duration_seconds=None,
            media_items=items,
            allowed_output_formats=[],
            allowed_video_qualities=[],
            allowed_audio_bitrates=[],
        )

    @staticmethod
    def _optional_text(value: object) -> str | None:
        return str(value) if value else None

    @staticmethod
    def _int_or_none(value: object) -> int | None:
        return int(value) if isinstance(value, (int, float)) else None

    @staticmethod
    def _thumbnail(value: object) -> HttpUrl | None:
        if not value:
            return None
        try:
            return HttpUrl(str(value))
        except ValueError as error:
            raise PolicyViolation("Provider returned an invalid thumbnail URL") from error
