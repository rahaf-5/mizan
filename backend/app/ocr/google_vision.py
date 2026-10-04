"""Google Cloud Vision adapter (DOCUMENT_TEXT_DETECTION) via REST + API key.

Official docs used:
  - POST https://vision.googleapis.com/v1/images:annotate (API key or OAuth)
  - image.content = base64 image; JSON request limit 10 MB; image file limit 20 MB
  - fullTextAnnotation.text; confidence (0–1) on pages/blocks/paragraphs/words/symbols
  - pages[].property.detectedLanguages
The API key is read on the backend only and sent in the `x-goog-api-key` header.
"""

from __future__ import annotations

import base64

import httpx

from app.domain.enums import PipelineStage
from app.domain.errors import OcrNotConfiguredError, OcrProviderError, OcrTimeoutError
from app.ocr.base import OcrImage, OcrProvider, ProviderOcrResult, ProviderWord

#: Default global endpoint (LOCKED for the MVP; regional EU/US endpoints not used).
ENDPOINT = "https://vision.googleapis.com/v1/images:annotate"
_STAGE = PipelineStage.USER_INPUT


class GoogleVisionOcrProvider(OcrProvider):
    name = "google_vision"

    def __init__(
        self,
        *,
        api_key: str | None,
        timeout_seconds: float = 30,
        language_hints: list[str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key or None
        self._timeout = timeout_seconds
        self._hints = [h for h in (language_hints or []) if h]
        self._transport = transport

    def is_configured(self) -> bool:
        return self._api_key is not None

    def _body(self, image: OcrImage) -> dict:
        request: dict = {
            "image": {"content": base64.b64encode(image.content).decode("ascii")},
            "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
        }
        if self._hints:
            request["imageContext"] = {"languageHints": self._hints}
        return {"requests": [request]}

    async def extract_text(self, image: OcrImage) -> ProviderOcrResult:
        if not self._api_key:
            raise OcrNotConfiguredError("Google Vision API key is not configured", stage=_STAGE)
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                resp = await client.post(
                    ENDPOINT,
                    json=self._body(image),
                    headers={"x-goog-api-key": self._api_key},
                )
        except httpx.TimeoutException as exc:
            raise OcrTimeoutError("OCR provider timed out", stage=_STAGE) from exc
        except httpx.HTTPError as exc:
            raise OcrProviderError(
                f"OCR provider unreachable: {type(exc).__name__}", stage=_STAGE
            ) from exc

        if resp.status_code != 200:
            raise OcrProviderError(f"OCR provider returned HTTP {resp.status_code}", stage=_STAGE)
        try:
            payload = resp.json()
            item = (payload.get("responses") or [{}])[0]
        except (ValueError, AttributeError, IndexError) as exc:
            raise OcrProviderError(
                "OCR provider returned an invalid response", stage=_STAGE
            ) from exc
        if item.get("error"):
            code = item["error"].get("code", "?")
            raise OcrProviderError(f"OCR provider error (code {code})", stage=_STAGE)
        return parse_annotation(item)


def parse_annotation(item: dict) -> ProviderOcrResult:
    """Map an AnnotateImageResponse to ProviderOcrResult without altering the text."""
    full = item.get("fullTextAnnotation") or {}
    text = full.get("text", "")
    words: list[ProviderWord] = []
    page_conf: list[float] = []
    languages: list[str] = []
    for page in full.get("pages", []) or []:
        if isinstance(page.get("confidence"), (int, float)):
            page_conf.append(float(page["confidence"]))
        for lang in (page.get("property") or {}).get("detectedLanguages", []) or []:
            code = lang.get("languageCode")
            if code and code not in languages:
                languages.append(code)
        for block in page.get("blocks", []) or []:
            for para in block.get("paragraphs", []) or []:
                for word in para.get("words", []) or []:
                    w_text = "".join(s.get("text", "") for s in word.get("symbols", []) or [])
                    conf = word.get("confidence")
                    words.append(
                        ProviderWord(
                            text=w_text,
                            confidence=float(conf) if isinstance(conf, (int, float)) else None,
                        )
                    )
    return ProviderOcrResult(
        text=text, words=words, page_confidences=page_conf, detected_languages=languages
    )
