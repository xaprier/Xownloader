from xownloader_server.models import OutputFormat
from xownloader_server.naming import (
    build_artifact_display_name,
    build_display_name,
    media_type_for_extension,
)

MP4 = OutputFormat.MP4


def test_media_type_for_extension_maps_known_types():
    assert media_type_for_extension("mp4") == "video"
    assert media_type_for_extension("JPG") == "image"
    assert media_type_for_extension("mp3") == "audio"
    assert media_type_for_extension("bin") == "video"


def test_artifact_display_name_numbers_items_when_more_than_one():
    assert (
        build_artifact_display_name("Trip to Rome", "jpg", 0, 3, fallback="x_0.jpg")
        == "Trip to Rome (1).jpg"
    )
    assert (
        build_artifact_display_name("Trip to Rome", "mp4", 2, 3, fallback="x_2.mp4")
        == "Trip to Rome (3).mp4"
    )


def test_artifact_display_name_falls_back_without_title():
    assert build_artifact_display_name(None, "jpg", 0, 2, fallback="job_0.jpg") == "job_0.jpg"


def test_uses_sanitised_title_with_format_extension():
    assert (
        build_display_name("Rick Astley - Never Gonna Give You Up", MP4, fallback="x.mp4")
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
