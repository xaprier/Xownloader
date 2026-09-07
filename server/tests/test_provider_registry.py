from pydantic import SecretStr

from xownloader_server.config import Settings
from xownloader_server.registry import build_registry


def test_youtube_hosts_resolve_without_configuration(tmp_path):
    registry = build_registry(Settings(download_directory=tmp_path, min_free_disk_mb=0))
    assert registry.provider_for_host("youtu.be") == "youtube"
    assert registry.provider_for_host("www.youtube.com") == "youtube"
    assert registry.has("youtube") is True


def test_instagram_host_is_known_but_unconfigured_without_cookie(tmp_path):
    registry = build_registry(Settings(download_directory=tmp_path, min_free_disk_mb=0))
    assert registry.provider_for_host("www.instagram.com") == "instagram"
    assert registry.has("instagram") is False


def test_instagram_is_configured_when_cookie_present(tmp_path):
    registry = build_registry(
        Settings(
            download_directory=tmp_path,
            min_free_disk_mb=0,
            instagram_cookie=SecretStr("sessionid=abc; csrftoken=xyz"),
        )
    )
    assert registry.has("instagram") is True
    assert registry.adapter_for("instagram").name == "instagram"


def test_unknown_host_resolves_to_none(tmp_path):
    registry = build_registry(Settings(download_directory=tmp_path, min_free_disk_mb=0))
    assert registry.provider_for_host("example.com") is None
