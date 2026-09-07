import re

from xownloader_server.models import OutputFormat

_UNSAFE = re.compile(r"[/\\\x00-\x1f]")
_WHITESPACE = re.compile(r"\s+")
_MAX_LENGTH = 120

_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif", "heic"}
_AUDIO_EXTENSIONS = {"mp3", "m4a", "aac", "opus", "ogg", "wav"}


def _clean_title(title: str | None) -> str | None:
    if not title:
        return None
    cleaned = _UNSAFE.sub(" ", title)
    cleaned = _WHITESPACE.sub(" ", cleaned).strip()
    cleaned = cleaned.lstrip(".").strip()
    cleaned = cleaned[:_MAX_LENGTH].rstrip(" .")
    return cleaned or None


def build_display_name(
    title: str | None,
    output_format: OutputFormat,
    *,
    fallback: str,
) -> str:
    """Return a user-facing download filename derived from a media title."""
    cleaned = _clean_title(title)
    if not cleaned:
        return fallback
    return f"{cleaned}.{output_format.value}"


def build_artifact_display_name(
    title: str | None,
    extension: str,
    index: int,
    total: int,
    *,
    fallback: str,
) -> str:
    """Filename for one artifact of a possibly multi-file job."""
    cleaned = _clean_title(title)
    if not cleaned:
        return fallback
    if total <= 1:
        return f"{cleaned}.{extension}"
    return f"{cleaned} ({index + 1}).{extension}"


def media_type_for_extension(extension: str) -> str:
    ext = extension.lower().lstrip(".")
    if ext in _IMAGE_EXTENSIONS:
        return "image"
    if ext in _AUDIO_EXTENSIONS:
        return "audio"
    return "video"
