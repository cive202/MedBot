from __future__ import annotations

import io
from typing import Any

import magic
from pypdf import PdfReader

from app.services.medgemma import MedGemmaError, chat_json, vision_json

PDF_MIME = {"application/pdf"}
IMAGE_MIME = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
MAX_BYTES = 20 * 1024 * 1024  # 20 MB
MAX_PDF_CHARS = 12000


class UnsupportedMediaError(ValueError):
    pass


def sniff(filename: str, raw: bytes) -> str:
    if len(raw) > MAX_BYTES:
        raise UnsupportedMediaError(f"File too large (>{MAX_BYTES // (1024 * 1024)} MB).")
    mime = magic.from_buffer(raw[:4096], mime=True)
    if mime not in PDF_MIME | IMAGE_MIME:
        raise UnsupportedMediaError(f"Unsupported MIME type: {mime} (filename: {filename}).")
    return mime


def extract_pdf_text(raw: bytes) -> str:
    reader = PdfReader(io.BytesIO(raw))
    chunks: list[str] = []
    for page in reader.pages:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:
            continue
    text = "\n\n".join(c.strip() for c in chunks if c.strip())
    return text[:MAX_PDF_CHARS]


SUMMARIZE_PROMPT = """You are a careful medical-document explainer. Summarize the medical document \
text the user provides for a patient (non-clinician) audience. Return STRICT JSON with this shape:

{
  "summary": "<2-4 sentence overview>",
  "key_findings": ["<finding 1>", "<finding 2>", ...],
  "values_of_concern": [{"name": "<measurement>", "value": "<value>", "concern": "<why it's notable>"}],
  "questions_to_ask_doctor": ["<question 1>", ...],
  "plain_language_glossary": [{"term": "<jargon>", "meaning": "<plain explanation>"}]
}

Do not invent diagnoses. If a section has nothing applicable, return an empty list.
"""


async def analyze_document(filename: str, raw: bytes) -> dict[str, Any]:
    mime = sniff(filename, raw)
    if mime in PDF_MIME:
        text = extract_pdf_text(raw)
        if not text:
            raise UnsupportedMediaError(
                "Could not extract text from this PDF (possibly a scanned image). "
                "Save individual pages as PNG/JPEG and try the image flow."
            )
        result = await chat_json(
            messages=[
                {"role": "system", "content": SUMMARIZE_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.2,
        )
        return {"kind": "pdf", "mime": mime, "extracted_chars": len(text), **_normalize(result)}

    # Image path: hand the picture to MedGemma vision.
    result = await vision_json(
        prompt=(
            "This is a medical document (lab report, prescription, discharge summary, etc.). "
            "Read the visible text and " + SUMMARIZE_PROMPT
        ),
        image_bytes=raw,
    )
    return {"kind": "image_document", "mime": mime, **_normalize(result)}


def _normalize(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": str(result.get("summary", "")).strip(),
        "key_findings": _str_list(result.get("key_findings")),
        "values_of_concern": _obj_list(result.get("values_of_concern"), ("name", "value", "concern")),
        "questions_to_ask_doctor": _str_list(result.get("questions_to_ask_doctor")),
        "plain_language_glossary": _obj_list(result.get("plain_language_glossary"), ("term", "meaning")),
    }


def _str_list(v: Any) -> list[str]:
    if not isinstance(v, list):
        return []
    return [str(x).strip() for x in v if isinstance(x, (str, int, float)) and str(x).strip()]


def _obj_list(v: Any, keys: tuple[str, ...]) -> list[dict[str, str]]:
    if not isinstance(v, list):
        return []
    out: list[dict[str, str]] = []
    for item in v:
        if isinstance(item, dict):
            out.append({k: str(item.get(k, "")).strip() for k in keys})
    return out


async def _stub_unused() -> None:
    raise MedGemmaError("stub")  # pragma: no cover
