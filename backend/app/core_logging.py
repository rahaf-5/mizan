"""Development-safe logging helpers.

Logs must never contain API keys, image bytes or user content. `redact()`
removes any configured secret value from text before it is logged.
"""

from __future__ import annotations

import logging
import traceback

LOGGER_NAME = "mizan"


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{name}")


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger(LOGGER_NAME)
    if getattr(root, "_mizan_configured", False):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
    root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False
    root._mizan_configured = True  # type: ignore[attr-defined]


def redact(text: str, secrets: list[str | None]) -> str:
    for s in secrets:
        if s and len(s) >= 4:
            text = text.replace(s, "[REDACTED]")
    return text


def format_exception_safely(exc: BaseException, secrets: list[str | None]) -> str:
    """Traceback (no local variables) with secrets redacted."""
    return redact("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)), secrets)
