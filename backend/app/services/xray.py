from __future__ import annotations

from typing import Any

from app.services.document_ocr import IMAGE_MIME, UnsupportedMediaError, sniff
from app.services.medgemma import vision_json
from app.services.severity import VALID as VALID_SEVERITY
from app.services.severity import _coerce_severity

XRAY_PROMPT = """You are a careful radiology explainer. Examine the chest/limb/dental X-ray image \
provided and produce STRICT JSON for a patient (non-clinician) audience:

{
  "modality_guess": "<chest_xray | abdominal_xray | extremity_xray | dental_xray | unknown>",
  "findings": ["<finding 1>", "<finding 2>", ...],
  "impressions": ["<impression 1>", ...],
  "severity": "low" | "moderate" | "critical",
  "recommended_followup": "<one short sentence>",
  "limitations": "<one short sentence on the limits of AI image review>"
}

Severity scale:
- "critical"  — findings suggest a fatal or potentially fatal condition needing IMMEDIATE professional consultation.
- "moderate"  — findings can potentially be harmful and warrant a near-term clinician visit.
- "low"       — minor or no concerning findings; routine follow-up only.

Be conservative. If the image is not actually a medical X-ray, set modality_guess="unknown", \
findings=[], impressions=["Image does not appear to be a medical X-ray."], and severity="low". \
Do not invent specific measurements you cannot derive from the image.
"""


async def analyze_xray(filename: str, raw: bytes) -> dict[str, Any]:
    mime = sniff(filename, raw)
    if mime not in IMAGE_MIME:
        raise UnsupportedMediaError(f"X-ray must be PNG/JPEG/WebP. Got {mime}.")

    result = await vision_json(prompt=XRAY_PROMPT, image_bytes=raw)
    return {
        "mime": mime,
        "modality_guess": str(result.get("modality_guess", "unknown")),
        "findings": [str(x).strip() for x in (result.get("findings") or []) if str(x).strip()],
        "impressions": [str(x).strip() for x in (result.get("impressions") or []) if str(x).strip()],
        "severity": _coerce_severity(str(result.get("severity", ""))),
        "recommended_followup": str(result.get("recommended_followup", "")).strip(),
        "limitations": str(result.get("limitations", "")).strip(),
    }


__all__ = ["analyze_xray", "VALID_SEVERITY"]
