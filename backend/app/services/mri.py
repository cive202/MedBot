from __future__ import annotations

from typing import Any

from app.services.document_ocr import IMAGE_MIME, UnsupportedMediaError, sniff
from app.services.medgemma import vision_json
from app.services.severity import VALID as VALID_SEVERITY
from app.services.severity import _coerce_severity

MRI_PROMPT = """You are a careful radiology explainer reviewing a single MRI slice for a \
patient (non-clinician) audience. The image is one frame from what is normally a 3-D stack \
of dozens of slices, so be especially conservative and call out that limitation.

Produce STRICT JSON with this exact shape:

{
  "body_region": "<brain | spine_cervical | spine_thoracic | spine_lumbar | knee | shoulder | hip | ankle | wrist | abdomen | pelvis | breast | cardiac | unknown>",
  "sequence_guess": "<t1 | t2 | flair | dwi | t1_contrast | stir | proton_density | unknown>",
  "plane": "<axial | sagittal | coronal | oblique | unknown>",
  "anatomy_visible": ["<short noun phrase>", "..."],
  "findings": ["<plain-language description of what's seen>", "..."],
  "impressions": ["<short clinical-ish impression in plain language>", "..."],
  "severity": "low" | "moderate" | "critical",
  "recommended_followup": "<one short sentence about the appropriate next step>",
  "limitations": "<one or two short sentences naming the most important limits: single slice from a stack, no DICOM metadata, AI image review is not a radiology read>"
}

Severity scale (use exactly these three values):
- "critical"  — findings suggest a fatal or potentially fatal condition needing IMMEDIATE professional consultation.
- "moderate"  — findings can potentially be harmful and warrant a near-term clinician visit.
- "low"       — minor or no concerning findings; routine follow-up only.

Guidance:
  - If the image is not actually an MRI (e.g. it's a photo, an X-ray, or a CT), set body_region="unknown", sequence_guess="unknown", plane="unknown", findings=[], impressions=["Image does not appear to be an MRI."], and severity="low".
  - Distinguish T1 vs T2 by the appearance of cerebrospinal fluid: dark on T1, bright on T2. FLAIR suppresses CSF (dark) while keeping lesions bright. Use "unknown" if you cannot tell.
  - Do not invent measurements, lesion sizes, or laterality you cannot derive from the image.
  - Use plain everyday language in findings and impressions; avoid jargon unless you can immediately gloss it.
  - When in doubt about severity, choose "moderate" and recommend in-person review.
"""


async def analyze_mri(filename: str, raw: bytes) -> dict[str, Any]:
    mime = sniff(filename, raw)
    if mime not in IMAGE_MIME:
        raise UnsupportedMediaError(f"MRI must be PNG/JPEG/WebP. Got {mime}.")

    result = await vision_json(prompt=MRI_PROMPT, image_bytes=raw)
    return {
        "mime": mime,
        "body_region": str(result.get("body_region", "unknown")),
        "sequence_guess": str(result.get("sequence_guess", "unknown")),
        "plane": str(result.get("plane", "unknown")),
        "anatomy_visible": [
            str(x).strip() for x in (result.get("anatomy_visible") or []) if str(x).strip()
        ],
        "findings": [
            str(x).strip() for x in (result.get("findings") or []) if str(x).strip()
        ],
        "impressions": [
            str(x).strip() for x in (result.get("impressions") or []) if str(x).strip()
        ],
        "severity": _coerce_severity(str(result.get("severity", ""))),
        "recommended_followup": str(result.get("recommended_followup", "")).strip(),
        "limitations": str(result.get("limitations", "")).strip(),
    }


__all__ = ["analyze_mri", "VALID_SEVERITY"]
