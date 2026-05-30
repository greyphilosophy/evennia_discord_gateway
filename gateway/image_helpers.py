"""Image URL extraction and local file resolution for the gateway.

The MUD (Evennia) stores generated images in a local `generated/` directory
and references them via URLs like:
  https://game.test/media/generated/room_desc_abc123.png

When these URLs appear in telnet output (sent to Discord), we:
1. Extract the URLs from the text
2. Resolve them to local files
3. Send the images as Discord attachments
4. Strip the URLs from the text so they don't appear as plain text
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Matches image URLs in telnet output.
# Evennia outputs: |yImage: https://game.test/media/generated/file.png|n
# Also handles plain text URLs.
_IMAGE_URL_RE = re.compile(
    r"(?i)image:\s*(https?://[^|\s]+\.(?:png|jpg|jpeg|webp|gif))"
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
    # Filter out "generating..." placeholders
    return [url for url in matches if not _IMAGE_GENERATING_RE.match(url)]


def resolve_local_image(
    image_url: str,
    generated_dir: Path,
) -> Optional[Path]:
    """Resolve an image URL to a local file path.

    Given a URL like 'https://game.test/media/generated/room_desc_abc123.png',
    maps it to the local file in the generated_images_dir.

    Returns None if the file doesn't exist.
    """
    # Extract the filename from the URL
    filename = Path(image_url).name
    if not filename:
        return None

    gen = Path(generated_dir)
    if not gen.exists():
        return None

    file_path = gen / filename
    return file_path if file_path.is_file() else None


def strip_image_references(text: str) -> str:
    """Remove image URL references and placeholders from text.

    Removes lines containing image URLs so they don't appear as plain text
    when we send them as Discord attachments.
    """
    if not text:
        return text
    # Remove lines that contain image URLs or generating... placeholders
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        if _IMAGE_URL_RE.search(line):
            continue
        if _IMAGE_GENERATING_RE.search(line):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)
