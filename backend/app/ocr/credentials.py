"""Validate the OCR API key format without ever revealing it.

Google API keys are plain ASCII. Invisible characters (e.g. U+200F
RIGHT-TO-LEFT MARK, often picked up when copying in an RTL interface),
whitespace or quotes make the key unusable in an HTTP header. We report the
problem precisely (character name + position) and never echo the key.
"""

from __future__ import annotations

import unicodedata


def describe_key_problem(key: str | None) -> str | None:
    if key is None:
        return None
    problems: list[str] = []
    for i, ch in enumerate(key):
        if ord(ch) > 126 or ord(ch) < 33:
            name = unicodedata.name(ch, "UNKNOWN")
            problems.append(f"U+{ord(ch):04X} {name} at position {i}")
    if key[:1] in "\"'" and key[-1:] == key[:1] and len(key) > 1:
        problems.append("value is wrapped in quotes inside the value")
    if not problems:
        return None
    shown = "; ".join(problems[:5]) + ("; …" if len(problems) > 5 else "")
    return (
        "GOOGLE_VISION_API_KEY contains characters that are not allowed in an API key "
        f"({shown}). Re-enter the key in backend/.env as plain ASCII with no spaces, "
        "quotes or invisible characters."
    )
