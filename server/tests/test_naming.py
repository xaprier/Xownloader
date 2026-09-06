from xownloader_server.models import OutputFormat
from xownloader_server.naming import build_display_name

MP4 = OutputFormat.MP4


def test_uses_sanitised_title_with_format_extension():
    assert (
        build_display_name(
            "Rick Astley - Never Gonna Give You Up", MP4, fallback="x.mp4"
        )
        == "Rick Astley - Never Gonna Give You Up.mp4"
    )


def test_strips_path_separators_and_control_characters():
    assert build_display_name("a/b\\c\tdef", MP4, fallback="x.mp4") == "a b c def.mp4"


def test_strips_leading_dots_and_surrounding_space():
    assert build_display_name("  ...hidden", MP4, fallback="x.mp4") == "hidden.mp4"


def test_truncates_to_120_characters():
    name = build_display_name("A" * 300, MP4, fallback="x.mp4")
    assert name == "A" * 120 + ".mp4"


def test_falls_back_when_title_is_empty_or_missing():
    assert build_display_name(None, MP4, fallback="job.mp4") == "job.mp4"
    assert build_display_name("   ", MP4, fallback="job.mp4") == "job.mp4"
    assert build_display_name("///", MP4, fallback="job.mp4") == "job.mp4"
