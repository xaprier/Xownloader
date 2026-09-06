import re

from xownloader_server.models import OutputFormat

_UNSAFE = re.compile(r"[/\\\x00-\x1f]")
_WHITESPACE = re.compile(r"\s+")
_MAX_LENGTH = 120


def build_display_name(
    title: str | None,
    output_format: OutputFormat,
    *,
    fallback: str,
) -> str:
    """Return a user-facing download filename derived from a media title."""
    if not title:
        return fallback
    cleaned = _UNSAFE.sub(" ", title)
    cleaned = _WHITESPACE.sub(" ", cleaned).strip()
    cleaned = cleaned.lstrip(".").strip()
    cleaned = cleaned[:_MAX_LENGTH].rstrip(" .")
    if not cleaned:
        return fallback
    return f"{cleaned}.{output_format.value}"
