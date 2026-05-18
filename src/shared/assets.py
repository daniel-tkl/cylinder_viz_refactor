from __future__ import annotations

import base64
from pathlib import Path


def read_text_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def read_file_base64(path: str) -> str:
    data = Path(path).read_bytes()
    return base64.b64encode(data).decode("utf-8")
