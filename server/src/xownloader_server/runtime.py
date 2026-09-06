import importlib.util
import shutil
from pathlib import Path
from typing import TypedDict

from xownloader_server.config import Settings


class RuntimeStatus(TypedDict):
    ready: bool
    yt_dlp: bool
    ffmpeg: bool
    ffprobe: bool
    output_directory: bool
    disk_reserve: bool


def check_runtime(settings: Settings) -> RuntimeStatus:
    output_directory_ready = _directory_is_writable(settings.download_directory)
    disk_reserve_ready = _has_disk_reserve(settings)
    yt_dlp_ready = importlib.util.find_spec("yt_dlp") is not None
    ffmpeg_ready = shutil.which("ffmpeg") is not None
    ffprobe_ready = shutil.which("ffprobe") is not None
    return {
        "ready": all(
            [
                output_directory_ready,
                disk_reserve_ready,
                yt_dlp_ready,
                ffmpeg_ready,
                ffprobe_ready,
            ]
        ),
        "yt_dlp": yt_dlp_ready,
        "ffmpeg": ffmpeg_ready,
        "ffprobe": ffprobe_ready,
        "output_directory": output_directory_ready,
        "disk_reserve": disk_reserve_ready,
    }


def _directory_is_writable(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".xownloader-write-check"
        probe.touch()
        probe.unlink()
        return True
    except OSError:
        return False


def _has_disk_reserve(settings: Settings) -> bool:
    try:
        free_bytes = shutil.disk_usage(settings.download_directory).free
    except OSError:
        return False
    return free_bytes >= settings.min_free_disk_mb * 1024 * 1024
