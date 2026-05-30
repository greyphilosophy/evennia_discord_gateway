"""Tests for image_helpers module."""
from pathlib import Path

from gateway.image_helpers import (
    extract_image_urls,
    resolve_local_image,
)


class TestExtractImageUrls:
    def test_extracts_single_url(self) -> None:
        text = "You see a room.\n\n|yImage: https://game.test/media/generated/room_abc.png|n"
        urls = extract_image_urls(text)
        assert urls == ["https://game.test/media/generated/room_abc.png"]

    def test_extracts_multiple_urls(self) -> None:
        text = "|yImage: https://game.test/media/generated/room.png|n\n|yImage: https://game.test/media/generated/obj.png|n"
        urls = extract_image_urls(text)
        assert len(urls) == 2
        assert urls[0] == "https://game.test/media/generated/room.png"
        assert urls[1] == "https://game.test/media/generated/obj.png"

    def test_extracts_http_and_https(self) -> None:
        text = "Image: http://game.test/media/generated/test.png"
        urls = extract_image_urls(text)
        assert urls == ["http://game.test/media/generated/test.png"]

    def test_ignores_generating_placeholder(self) -> None:
        text = "A room.\n\n|yImage: generating...|n"
        urls = extract_image_urls(text)
        assert urls == []

    def test_empty_text(self) -> None:
        assert extract_image_urls("") == []

    def test_no_image_url(self) -> None:
        assert extract_image_urls("Just plain text with no URLs.") == []

    def test_ignores_url_without_image_prefix(self) -> None:
        text = "Check out https://game.test/media/generated/test.png"
        assert extract_image_urls(text) == []


class TestResolveLocalImage:
    def test_resolves_generated_image(self, tmp_path: Path) -> None:
        gen_dir = tmp_path / "generated"
        gen_dir.mkdir()
        img_file = gen_dir / "room_abc.png"
        img_file.write_bytes(b"\x89PNG")

        result = resolve_local_image(
            "https://game.test/media/generated/room_abc.png",
            Path(str(gen_dir)),
        )
        assert result == img_file

    def test_resolves_object_image(self, tmp_path: Path) -> None:
        gen_dir = tmp_path / "generated"
        gen_dir.mkdir()
        img_file = gen_dir / "object_Catgirl_77bf53a1db33.png"
        img_file.write_bytes(b"\x89PNG")

        result = resolve_local_image(
            "https://game.test/media/generated/object_Catgirl_77bf53a1db33.png",
            Path(str(gen_dir)),
        )
        assert result == img_file

    def test_returns_none_when_file_missing(self, tmp_path: Path) -> None:
        gen_dir = tmp_path / "generated"
        gen_dir.mkdir()

        result = resolve_local_image(
            "https://game.test/media/generated/missing.png",
            Path(str(gen_dir)),
        )
        assert result is None

    def test_returns_none_when_dir_missing(self, tmp_path: Path) -> None:
        result = resolve_local_image(
            "https://game.test/media/generated/test.png",
            Path(str(tmp_path / "nonexistent")),
        )
        assert result is None
