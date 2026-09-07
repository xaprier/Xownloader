from pathlib import Path
from types import SimpleNamespace

import pytest

from xownloader_server.config import Settings
from xownloader_server.errors import InsufficientStorage, PolicyViolation, RateLimitExceeded
from xownloader_server.models import DownloadRequest
from xownloader_server.policy import ServerPolicy
from xownloader_server.rate_limit import RateLimiter


def test_policy_accepts_configured_youtube_format(tmp_path: Path) -> None:
    settings = Settings(
        download_directory=tmp_path,
        min_free_disk_mb=0,
        allowed_output_formats="mp4",
    )
    policy = ServerPolicy(settings)

    policy.validate_request(
        DownloadRequest.model_validate(
            {"source_url": "https://www.youtube.com/watch?v=example", "output_format": "mp4"}
        )
    )


def test_policy_rejects_non_youtube_provider(tmp_path: Path) -> None:
    policy = ServerPolicy(Settings(download_directory=tmp_path, min_free_disk_mb=0))

    with pytest.raises(PolicyViolation, match="Only YouTube"):
        policy.validate_request(
            DownloadRequest.model_validate({"source_url": "https://example.com/video"})
        )


def test_policy_rejects_disabled_audio_bitrate(tmp_path: Path) -> None:
    policy = ServerPolicy(
        Settings(download_directory=tmp_path, min_free_disk_mb=0, allowed_audio_bitrates="128K")
    )

    with pytest.raises(PolicyViolation, match="Audio bitrate"):
        policy.validate_request(
            DownloadRequest.model_validate(
                {
                    "source_url": "https://youtu.be/example",
                    "audio_bitrate": "320K",
                }
            )
        )


def test_policy_returns_provider_name_for_youtube(tmp_path: Path) -> None:
    policy = ServerPolicy(Settings(download_directory=tmp_path, min_free_disk_mb=0))
    provider = policy.validate_source_url(
        DownloadRequest.model_validate({"source_url": "https://youtu.be/example"}).source_url
    )
    assert provider == "youtube"


def test_policy_rejects_instagram_when_not_configured(tmp_path: Path) -> None:
    policy = ServerPolicy(Settings(download_directory=tmp_path, min_free_disk_mb=0))
    with pytest.raises(PolicyViolation, match="Instagram is not configured"):
        policy.validate_source_url(
            DownloadRequest.model_validate(
                {"source_url": "https://www.instagram.com/p/Cxxxx/"}
            ).source_url
        )


def test_policy_accepts_instagram_when_configured(tmp_path: Path) -> None:
    from pydantic import SecretStr

    policy = ServerPolicy(
        Settings(
            download_directory=tmp_path,
            min_free_disk_mb=0,
            instagram_cookie=SecretStr("sessionid=abc; csrftoken=xyz"),
        )
    )
    provider = policy.validate_source_url(
        DownloadRequest.model_validate(
            {"source_url": "https://www.instagram.com/p/Cxxxx/"}
        ).source_url
    )
    assert provider == "instagram"


def test_rate_limiter_rejects_requests_after_limit() -> None:
    limiter = RateLimiter(requests_per_minute=1)
    limiter.check("127.0.0.1")

    with pytest.raises(RateLimitExceeded, match="Rate limit"):
        limiter.check("127.0.0.1")


def test_policy_rejects_insufficient_disk(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    policy = ServerPolicy(Settings(download_directory=tmp_path, min_free_disk_mb=10))
    monkeypatch.setattr(
        "xownloader_server.policy.shutil.disk_usage",
        lambda _: SimpleNamespace(free=1),
    )

    with pytest.raises(InsufficientStorage, match="free disk"):
        policy.ensure_disk_capacity()
