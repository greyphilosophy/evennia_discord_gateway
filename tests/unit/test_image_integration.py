"""Integration test for image delivery pipeline.

Reproduces the exact flow: raw ANSI telnet output → extract URLs → resolve files → strip.
"""
from pathlib import Path

import pytest

from gateway.image_helpers import (
    _IMAGE_URL_RE,
    extract_image_urls,
    resolve_local_image,
    strip_image_references,
)

# The actual ANSI-formatted output from the MUD (as the telnet session returns it).
ANSI_LOOK_OUTPUT = (
    "\x1b[1m\x1b[36mUncharted Room (#76)\x1b[0m\n"
    "The alcove hums with coastal serenity, its raw timber walls framing a driftwood shelf.\n"
    "\x1b[1m\x1b[33mImage: https://game.test/media/generated/room_Uncharted Room_9744bee27166.png\x1b[0m\n"
    "\x1b[1m\x1b[37mExits:\x1b[0m south and north\n"
)


class TestExtractWithAnsiEscapes:
    """Test that the regex handles ANSI-embedded URLs correctly."""

    def test_extracts_url_from_ansi_line(self) -> None:
        """Regression: ANSI escapes \x1b[1m\x1b[33m before Image: prefix."""
        urls = extract_image_urls(ANSI_LOOK_OUTPUT)
        assert len(urls) == 1
        assert urls[0] == "https://game.test/media/generated/room_Uncharted Room_9744bee27166.png"

    def test_extracts_url_with_spaces_in_room_name(self) -> None:
        """Room names with spaces produce URLs like 'room_Uncharted Room_XYZ.png'."""
        text = "\x1b[33mImage: https://game.test/media/generated/room_Home Base_abc123.png\x1b[0m"
        urls = extract_image_urls(text)
        assert len(urls) == 1
        assert urls[0] == "https://game.test/media/generated/room_Home Base_abc123.png"

    def test_full_ansi_room_output(self) -> None:
        """Full MUD look output (the exact scenario the user sees)."""
        urls = extract_image_urls(ANSI_LOOK_OUTPUT)
        assert urls == ["https://game.test/media/generated/room_Uncharted Room_9744bee27166.png"]

    def test_multiple_images_in_ansi_output(self) -> None:
        text = (
            "\x1b[33mImage: https://game.test/media/generated/room_Test_aaa.png\x1b[0m\n"
            "\x1b[33mImage: https://game.test/media/generated/obj_Bar_bbb.png\x1b[0m\n"
        )
        urls = extract_image_urls(text)
        assert len(urls) == 2


class TestResolveLocalImage:
    def test_resolve_room_with_spaces(self, tmp_path: Path) -> None:
        """Ensure filenames with spaces resolve correctly."""
        gen_dir = tmp_path / "generated"
        gen_dir.mkdir()
        img_file = gen_dir / "room_Uncharted Room_9744bee27166.png"
        img_file.write_bytes(b"\x89PNG")

        result = resolve_local_image(
            "https://game.test/media/generated/room_Uncharted Room_9744bee27166.png",
            gen_dir,
        )
        assert result == img_file


class TestStripImageReferences:
    def test_strips_ansi_image_line(self) -> None:
        """After stripping, the ANSI image line should be removed."""
        cleaned = strip_image_references(ANSI_LOOK_OUTPUT)
        assert "Image:" not in cleaned
        assert "Uncharted Room (#76)" in cleaned  # Room title stays
        assert "Exits:" in cleaned  # Other lines stay

    def test_strips_all_image_lines_keeps_rest(self) -> None:
        text = (
            "Room description.\n"
            "\x1b[33mImage: https://game.test/media/generated/room_Test_abc.png\x1b[0m\n"
            "\x1b[33mImage: https://game.test/media/generated/obj_Bar_def.png\x1b[0m\n"
            "More room text."
        )
        cleaned = strip_image_references(text)
        assert "Image:" not in cleaned
        assert "Room description." in cleaned
        assert "More room text." in cleaned


class TestEndToEndPipeline:
    """Simulate the full gateway pipeline for a single look command."""

    def test_pipeline_extracts_and_strips(self, tmp_path: Path) -> None:
        """Full flow: extract URLs → resolve → strip → no image reference in output."""
        gen_dir = tmp_path / "generated"
        gen_dir.mkdir()
        img_file = gen_dir / "room_Uncharted Room_9744bee27166.png"
        img_file.write_bytes(b"\x89PNG")

        # Step 1: Extract
        urls = extract_image_urls(ANSI_LOOK_OUTPUT)
        assert len(urls) == 1

        # Step 2: Resolve
        img_path = resolve_local_image(urls[0], gen_dir)
        assert img_path == img_file

        # Step 3: Strip
        cleaned = strip_image_references(ANSI_LOOK_OUTPUT)
        assert "Image:" not in cleaned
        assert "Uncharted Room (#76)" in cleaned

    def test_pipeline_no_crash_when_file_missing(self, tmp_path: Path) -> None:
        """Graceful: URL extracted, but file doesn't exist yet (race condition)."""
        gen_dir = tmp_path / "generated"
        gen_dir.mkdir()

        urls = extract_image_urls(ANSI_LOOK_OUTPUT)
        assert len(urls) == 1

        img_path = resolve_local_image(urls[0], gen_dir)
        assert img_path is None

        # Text should still be stripped (so the dangling URL doesn't appear)
        cleaned = strip_image_references(ANSI_LOOK_OUTPUT)
        assert "Image:" not in cleaned
