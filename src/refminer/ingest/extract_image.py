from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass
class ImageMetadata:
    width: int
    height: int
    mode: str


def extract_image_metadata(path: Path) -> ImageMetadata:
    with Image.open(path) as image:
        return ImageMetadata(width=image.width, height=image.height, mode=image.mode)
