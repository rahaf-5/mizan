"""LOCKED (Task 3): the OCR low-confidence threshold is an OCR review signal only.

It must never influence verification status or Evidence Strength. These tests
fail if any verification-side module starts depending on OCR data or settings.
"""

from __future__ import annotations

import ast
from pathlib import Path

from app.config import Settings
from app.ocr.google_vision import ENDPOINT

APP = Path(__file__).resolve().parents[1] / "app"

VERIFICATION_SIDE = [
    *sorted((APP / "pipeline").glob("*.py")),
    *sorted((APP / "sources").glob("*.py")),
    APP / "domain" / "verification.py",
    APP / "domain" / "validation.py",
    APP / "domain" / "results.py",
    APP / "domain" / "retrieval.py",
    APP / "domain" / "evidence.py",
    APP / "domain" / "routing.py",
]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
        elif isinstance(node, ast.Import):
            mods.update(a.name for a in node.names)
    return mods


def test_verification_modules_do_not_import_ocr():
    for path in VERIFICATION_SIDE:
        bad = {m for m in _imports(path) if m.startswith(("app.ocr", "app.domain.ocr"))}
        assert not bad, f"{path.relative_to(APP)} imports OCR modules: {bad}"


def test_verification_modules_never_read_the_ocr_threshold():
    for path in VERIFICATION_SIDE:
        src = path.read_text(encoding="utf-8")
        assert "ocr_low_confidence_threshold" not in src, path.relative_to(APP)
        assert "low_confidence" not in src, path.relative_to(APP)


def test_threshold_default_is_locked_at_0_6():
    assert Settings().ocr_low_confidence_threshold == 0.6


def test_default_global_vision_endpoint():
    assert ENDPOINT == "https://vision.googleapis.com/v1/images:annotate"
