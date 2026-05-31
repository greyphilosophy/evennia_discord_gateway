"""Tests for image delivery pipeline — reproduces the user's exact issue.

Regression test: When a 'look' command returns ANSI output containing an image URL
for a room with spaces in its name, the gateway should:
1. Extract the image URL from ANSI text
2. Resolve it to a local file
3. Send it as a Discord attachment
4. Strip the URL from the text output
"""
from pathlib import Path

import pytest

from gateway.image_helpers import (
    extract_image_urls,
    resolve_local_image,
    strip_image_references,
)


# Exact output the user sees from a 'look' command (ANSI-escaped, space in room name)
LOOK_WITH_IMAGE = (
    "\x1b[1m\x1b[36mUncharted Room (#76)\x1b[0m\n"
    "The alcove hums with coastal serenity, its raw timber walls framing a driftwood shelf.\n"
    "\x1b[1m\x1b[33mImage: https://game.test/media/generated/room_Uncharted Room_9744bee27166.png\x1b[0m\n"
    "\x1b[1m\x1b[37mExits:\x1b[0m south and north\n"
    "\x1b[1m\x1b[37mYou see:\x1b[0m a Catgirl Statue, a Cerulean Wave Crystal, a Red Brass Lamp\x1b[0m\n"
)


class TestExtractImageUrlsRegression:
    """Regression tests for the 'look with image' pipeline."""

    def test_extracts_url_from_ansi_output(self) -> None:
        """The regex must extract URLs even when wrapped in ANSI escapes."""
        urls = extract_image_urls(LOOK_WITH_IMAGE)
        assert len(urls) == 1
        assert urls[0] == "https://game.test/media/generated/room_Uncharted Room_9744bee27166.png"

    def test_extracts_url_with_spaces_in_room_name(self) -> None:
        """Room names with spaces produce URLs with spaces (not URL-encoded)."""
        text = "\x1b[33mImage: https://game.test/media/generated/room_Home Base_xyz123.png\x1b[0m"
        urls = extract_image_urls(text)
        assert urls == ["https://game.test/media/generated/room_Home Base_xyz123.png"]

    def test_no_url_when_no_image_line(self) -> None:
        text = "Just a normal room description with no images."
        assert extract_image_urls(text) == []

    def test_generating_placeholder_ignored(self) -> None:
        text = "Looking...\n\n|yImage: generating...|n\nDone."
        assert extract_image_urls(text) == []


class TestResolveLocalImageRegression:
    def test_resolves_image_for_room_with_spaces(self, tmp_path: Path) -> None:
        gen_dir = tmp_path / "generated"
        gen_dir.mkdir()
        (gen_dir / "room_Uncharted Room_9744bee27166.png").write_bytes(b"\x89PNG")

        result = resolve_local_image(
            "https://game.test/media/generated/room_Uncharted Room_9744bee27166.png",
            gen_dir,
        )
        assert result == gen_dir / "room_Uncharted Room_9744bee27166.png"


class TestStripImageReferencesRegression:
    def test_strips_ansi_image_line_preserves_rest(self) -> None:
        cleaned = strip_image_references(LOOK_WITH_IMAGE)
        assert "Image:" not in cleaned
        assert "Uncharted Room (#76)" in cleaned
        assert "Exits:" in cleaned
        assert "You see:" in cleaned

    def test_strips_all_image_lines(self) -> None:
        text = (
            "Room text\n"
            "\x1b[33mImage: https://game.test/media/generated/room_A_xxx.png\x1b[0m\n"
            "\x1b[33mImage: https://game.test/media/generated/obj_B_yyy.png\x1b[0m\n"
            "More text\n"
        )
        cleaned = strip_image_references(text)
        assert "Image:" not in cleaned
        assert "Room text" in cleaned
        assert "More text" in cleaned


class TestEndToEndPipeline:
    """Simulates the full gateway flow: extract → resolve → send → strip."""

    def test_full_pipeline(self, tmp_path: Path) -> None:
        gen_dir = tmp_path / "generated"
        gen_dir.mkdir()
        (gen_dir / "room_Uncharted Room_9744bee27166.png").write_bytes(b"\x89PNG")

        # Step 1: Extract
        urls = extract_image_urls(LOOK_WITH_IMAGE)
        assert len(urls) == 1
        url = urls[0]

        # Step 2: Resolve
        img_path = resolve_local_image(url, gen_dir)
        assert img_path is not None
        assert img_path.exists()

        # Step 3: Strip
        cleaned = strip_image_references(LOOK_WITH_IMAGE)
        assert "Image:" not in cleaned
        assert "Uncharted Room (#76)" in cleaned