"""Validate uploaded image CONTENT (not just the name/extension)."""

from __future__ import annotations

import io
import warnings

from PIL import Image, UnidentifiedImageError

from app.domain.ocr import MAX_IMAGE_PIXELS, MAX_UPLOAD_BYTES, OcrInputErrorCode
from app.ocr.base import OcrImage

_SIGNATURES = {
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/jpeg": b"\xff\xd8\xff",
}
_PIL_FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg"}


class OcrInputError(ValueError):
    def __init__(self, code: OcrInputErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


def sniff_mime(data: bytes) -> str | None:
    for mime, sig in _SIGNATURES.items():
        if data.startswith(sig):
            return mime
    return None


def validate_image(data: bytes) -> OcrImage:
    if not data:
        raise OcrInputError(OcrInputErrorCode.EMPTY_FILE, "empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise OcrInputError(OcrInputErrorCode.FILE_TOO_LARGE, "file exceeds the upload limit")
    mime = sniff_mime(data)
    if mime is None:
        raise OcrInputError(
            OcrInputErrorCode.UNSUPPORTED_TYPE, "only JPG or PNG images are accepted"
        )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as img:
                fmt, (width, height) = img.format, img.size
                img.verify()
    except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise OcrInputError(
            OcrInputErrorCode.IMAGE_TOO_MANY_PIXELS, "image has too many pixels"
        ) from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise OcrInputError(
            OcrInputErrorCode.UNREADABLE_IMAGE, "image could not be decoded"
        ) from exc
    if _PIL_FORMATS.get(fmt or "") != mime:
        raise OcrInputError(
            OcrInputErrorCode.UNSUPPORTED_TYPE, "image content does not match JPG/PNG"
        )
    if width * height > MAX_IMAGE_PIXELS:
        raise OcrInputError(OcrInputErrorCode.IMAGE_TOO_MANY_PIXELS, "image has too many pixels")
    return OcrImage(content=data, mime_type=mime, width=width, height=height)
