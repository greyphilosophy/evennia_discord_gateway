"""Image URL extraction and local file resolution for the gateway.

The MUD (Evennia) stores generated images in a local `generated/` directory
and references them via URLs like:
  https://game.test/media/generated/room_desc_abc123.png

When these URLs appear in telnet output (sent to Discord), we:
1. Extract the URLs from the text
2. Resolve them to local files (if generated_images_dir is configured)
3. Send the images as Discord attachments
4. Strip only the *successfully delivered* URLs from the text
   (unsent URLs remain visible as fallback links)
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable, List, Optional

logger = logging.getLogger(__name__)

# Matches image URLs in telnet output.
# Evennia outputs: |yImage: https://game.test/media/generated/file.png|n
# Also handles plain text URLs.
_IMAGE_URL_RE = re.compile(
    r"(?i)image:\s*(https?://[^|\x1b]*?\.(?:png|jpg|jpeg|webp|gif))"
)

# Matches "Image: generating..." placeholder
_IMAGE_GENERATING_RE = re.compile(
    r"(?i)image:\s*generating\s*\.\.\..*"
)


def extract_image_urls(text: str) -> List[str]:
    """Extract image URLs from telnet output text.

    Returns a list of image URLs found in the text, filtering out
    the "generating..." placeholder.
    """
    if not text:
        return []
    matches = _IMAGE_URL_RE.findall(text)
    return [url for url in matches if not _IMAGE_GENERATING_RE.match(url)]


def resolve_local_image(
    image_url: str,
    generated_dir: Optional[str],
) -> Optional[Path]:
    """Resolve an image URL to a local file path.

    Given a URL like 'https://game.test/media/generated/room_desc_abc123.png',
    maps it to the local file in the generated_images_dir.

    Returns None if the file doesn't exist or no directory is configured.
    """
    if not generated_dir:
        return None
    filename = Path(image_url).name
    if not filename:
        return None

    gen = Path(generated_dir)
    if not gen.exists():
        return None

    file_path = gen / filename
    return file_path if file_path.is_file() else None


def strip_image_references(text: str, urls_to_strip: Optional[Iterable[str]] = None) -> str:
    """Remove image URL references from text.

    If ``urls_to_strip`` is provided, only those specific URLs are removed
    from the text. This ensures that images which failed to deliver are
    left visible as fallback links.

    If ``urls_to_strip`` is None or empty, *all* image references are stripped.
    """
    if not text:
        return text

    if urls_to_strip:
        for url in urls_to_strip:
            text = text.replace(url, "")
        # Remove "generating..." placeholder lines
        lines = text.split("\n")
        cleaned = []
        for line in lines:
            if _IMAGE_GENERATING_RE.search(line):
                continue
            cleaned.append(line)
        return "\n".join(cleaned)

    # Legacy: strip all image references
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        if _IMAGE_URL_RE.search(line):
            continue
        if _IMAGE_GENERATING_RE.search(line):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)
