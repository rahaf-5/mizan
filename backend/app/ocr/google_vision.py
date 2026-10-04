"""Google Cloud Vision adapter (DOCUMENT_TEXT_DETECTION) via REST + API key.

Official docs used:
  - POST https://vision.googleapis.com/v1/images:annotate (API key or OAuth)
  - image.content = base64 image; JSON request limit 10 MB; image file limit 20 MB
  - fullTextAnnotation.text; confidence (0–1) on pages/blocks/paragraphs/words/symbols
  - pages[].property.detectedLanguages
  - Errors use the google.rpc.Status shape: {"error": {"code", "message", "status", "details"}}
The API key is read on the backend only and sent in the `x-goog-api-key` header.
Diagnostics: development logs record HTTP status, Google error status/reason and
message (with the key redacted). Never logged: the key, image bytes, OCR text.
"""

from __future__ import annotations

import base64

import httpx
from pydantic import ValidationError

from app.core_logging import get_logger, redact
from app.domain.enums import PipelineStage
from app.domain.errors import OcrNotConfiguredError, OcrProviderError, OcrTimeoutError
from app.ocr.base import OcrImage, OcrProvider, ProviderOcrResult, ProviderWord

#: Default global endpoint (LOCKED for the MVP; regional EU/US endpoints not used).
ENDPOINT = "https://vision.googleapis.com/v1/images:annotate"
_STAGE = PipelineStage.USER_INPUT
log = get_logger("ocr.google_vision")


def _google_error_summary(err: dict) -> tuple[str, str | None, str]:
    """(status, reason, message) from a google.rpc.Status error object."""
    status = str(err.get("status") or err.get("code") or "UNKNOWN")
    reason = None
    for d in err.get("details") or []:
        if isinstance(d, dict) and d.get("reason"):
            reason = str(d["reason"])
            break
    return status, reason, str(err.get("message") or "")


class GoogleVisionOcrProvider(OcrProvider):
    name = "google_vision"

    def __init__(
        self,
        *,
        api_key: str | None,
        timeout_seconds: float = 30,
        language_hints: list[str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        config_problem: str | None = None,
    ) -> None:
        self._api_key = api_key or None
        self._timeout = timeout_seconds
        self._hints = [h for h in (language_hints or []) if h]
        self._transport = transport
        self._config_problem = config_problem

    @property
    def config_problem(self) -> str | None:
        if self._config_problem:
            return self._config_problem
        if not self._api_key:
            return "GOOGLE_VISION_API_KEY is not set"
        return None

    def is_configured(self) -> bool:
        return self.config_problem is None

    def _body(self, image: OcrImage) -> dict:
        request: dict = {
            "image": {"content": base64.b64encode(image.content).decode("ascii")},
            "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
        }
        if self._hints:
            request["imageContext"] = {"languageHints": self._hints}
        return {"requests": [request]}

    def _redact(self, text: str) -> str:
        return redact(text, [self._api_key])

    async def extract_text(self, image: OcrImage) -> ProviderOcrResult:
        problem = self.config_problem
        if problem:
            log.warning("OCR not configured: %s", problem)
            raise OcrNotConfiguredError(problem, stage=_STAGE)
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                resp = await client.post(
                    ENDPOINT,
                    json=self._body(image),
                    headers={"x-goog-api-key": self._api_key or ""},
                )
        except httpx.TimeoutException as exc:
            log.warning("Google Vision timed out after %ss", self._timeout)
            raise OcrTimeoutError("OCR provider timed out", stage=_STAGE) from exc
        except httpx.HTTPError as exc:
            log.warning("Google Vision unreachable: %s", type(exc).__name__)
            raise OcrProviderError(
                f"OCR provider unreachable: {type(exc).__name__}", stage=_STAGE
            ) from exc
        except (UnicodeError, ValueError, TypeError) as exc:
            # e.g. a non-ASCII character in a header value: the request could not be built.
            log.error("Could not build Google Vision request: %s", type(exc).__name__)
            raise OcrProviderError(
                f"OCR request could not be built: {type(exc).__name__}", stage=_STAGE
            ) from exc

        try:
            payload = resp.json()
        except ValueError:
            payload = None

        if resp.status_code != 200:
            err = (payload or {}).get("error") if isinstance(payload, dict) else None
            if isinstance(err, dict):
                status, reason, message = _google_error_summary(err)
            else:
                status, reason, message = "UNKNOWN", None, "non-JSON error body"
            log.warning(
                "Google Vision rejected the request: http=%s status=%s reason=%s message=%s",
                resp.status_code,
                status,
                reason,
                self._redact(message),
            )
            exc = OcrProviderError(
                f"OCR provider rejected the request: HTTP {resp.status_code} {status}"
                + (f" ({reason})" if reason else ""),
                stage=_STAGE,
            )
            exc.retryable = resp.status_code == 429 or resp.status_code >= 500
            raise exc

        if not isinstance(payload, dict):
            log.warning("Google Vision returned an invalid (non-JSON) 200 response")
            raise OcrProviderError("OCR provider returned an invalid response", stage=_STAGE)
        items = payload.get("responses") or [{}]
        item = items[0] if isinstance(items, list) and items else {}
        if not isinstance(item, dict):
            raise OcrProviderError("OCR provider returned an invalid response", stage=_STAGE)
        if item.get("error"):
            status, reason, message = _google_error_summary(item["error"])
            log.warning(
                "Google Vision image error: status=%s reason=%s message=%s",
                status,
                reason,
                self._redact(message),
            )
            raise OcrProviderError(
                f"OCR provider could not process the image: {status}", stage=_STAGE
            )
        try:
            return parse_annotation(item)
        except (ValidationError, TypeError, ValueError, AttributeError) as exc:
            log.warning(
                "Google Vision response did not match the expected shape: %s",
                type(exc).__name__,
            )
            raise OcrProviderError(
                "OCR provider response did not match the expected format", stage=_STAGE
            ) from exc


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
