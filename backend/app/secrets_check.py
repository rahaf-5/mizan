"""Validate secret *format* without ever revealing the secret.

API keys are plain ASCII. Invisible characters (e.g. U+200F RIGHT-TO-LEFT
MARK, often picked up when copying in an RTL interface), whitespace or quotes
make a key unusable in an HTTP header. Report the character and position only.
"""

from __future__ import annotations

import unicodedata


def describe_secret_problem(name: str, value: str | None) -> str | None:
    if value is None:
        return None
    problems: list[str] = []
    for i, ch in enumerate(value):
        if ord(ch) > 126 or ord(ch) < 33:
            problems.append(f"U+{ord(ch):04X} {unicodedata.name(ch, 'UNKNOWN')} at position {i}")
    if len(value) > 1 and value[0] in "\"'" and value[-1] == value[0]:
        problems.append("value is wrapped in quotes")
    if not problems:
        return None
    shown = "; ".join(problems[:5]) + ("; …" if len(problems) > 5 else "")
    return (
        f"{name} contains characters that are not allowed in an API key ({shown}). "
        "Re-enter it in backend/.env as plain ASCII with no spaces, quotes or invisible characters."
    )
