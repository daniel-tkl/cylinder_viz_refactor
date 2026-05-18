from __future__ import annotations


def highlight_ng(value: object) -> str:
    color = "red" if "NG" in str(value) else ""
    return f"color: {color}"
