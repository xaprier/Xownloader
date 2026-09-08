from __future__ import annotations

from xownloader_server.config import Settings
from xownloader_server.providers import ProviderAdapter, YtDlpAdapter

_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}
_INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com"}


class ProviderRegistry:
    def __init__(
        self,
        adapters: dict[str, ProviderAdapter],
        hosts: dict[str, str],
    ) -> None:
        self._adapters = adapters
        self._hosts = hosts

    @classmethod
    def with_adapters(cls, adapters: dict[str, ProviderAdapter]) -> "ProviderRegistry":
        return cls(adapters, _default_hosts())

    def provider_for_host(self, host: str) -> str | None:
        return self._hosts.get(host.lower().rstrip("."))

    def has(self, provider: str) -> bool:
        return provider in self._adapters

    def adapter_for(self, provider: str) -> ProviderAdapter:
        return self._adapters[provider]


def _default_hosts() -> dict[str, str]:
    hosts = {host: "youtube" for host in _YOUTUBE_HOSTS}
    hosts.update({host: "instagram" for host in _INSTAGRAM_HOSTS})
    return hosts


def build_registry(settings: Settings) -> ProviderRegistry:
    adapters: dict[str, ProviderAdapter] = {"youtube": YtDlpAdapter()}
    if settings.instagram_username and settings.instagram_password:
        from xownloader_server.instagram import InstagramAdapter

        adapters["instagram"] = InstagramAdapter(
            settings.instagram_username,
            settings.instagram_password.get_secret_value(),
            settings.instagram_session_path,
            totp_seed=(
                settings.instagram_totp_seed.get_secret_value()
                if settings.instagram_totp_seed
                else None
            ),
            delay_seconds=settings.instagram_download_delay_seconds,
        )
    return ProviderRegistry(adapters, _default_hosts())
