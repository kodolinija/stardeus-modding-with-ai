"""Reads image sizes from file headers (enough to check ModCover.jpg)."""
from __future__ import annotations

from pathlib import Path

_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def image_info(path: Path):
    """Returns (format, width, height); format is "jpeg", "png" or None."""
    data = path.read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        return "png", int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data[:2] != b"\xff\xd8":
        return None, 0, 0
    i = 2
    while i + 4 <= len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        i += 2
        if marker == 0x01 or 0xD0 <= marker <= 0xD8 or marker == 0xFF:
            continue
        if marker in (0xD9, 0xDA):
            break
        length = int.from_bytes(data[i:i + 2], "big")
        if marker in _SOF and i + 7 <= len(data):
            height = int.from_bytes(data[i + 3:i + 5], "big")
            width = int.from_bytes(data[i + 5:i + 7], "big")
            return "jpeg", width, height
        i += length
    return "jpeg", 0, 0
