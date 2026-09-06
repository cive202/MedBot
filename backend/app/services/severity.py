from __future__ import annotations

from typing import Any, Literal

from app.services.medgemma import MedGemmaError, chat_json

Severity = Literal["low", "moderate", "critical"]

SEVERITY_PROMPT = """You are a triage assistant. Given the patient's message, extracted symptoms, \
and candidate diseases from a classifier, return STRICT JSON with this exact shape:

{
  "severity": "low" | "moderate" | "critical",
  "specialty": "<one specialty string, e.g. cardiology, dermatology, gastroenterology, neurology, internal_medicine, emergency_medicine, ent, ophthalmology, orthopedics, psychiatry, pulmonology, urology>",
  "reasoning": "<one short sentence>"
}

Severity scale (use exactly these three values):
- "critical"  — disease is fatal or potentially fatal and the patient needs an IMMEDIATE in-person professional consultation (e.g. crushing chest pain, signs of stroke, severe breathing difficulty, anaphylaxis, suicide intent, major trauma, severe bleeding, signs of sepsis).
- "moderate"  — disease can potentially be harmful and warrants a near-term clinician visit, even if not the same day (e.g. persistent fever, worsening infection, untreated chronic condition flare, moderate pain that interferes with daily life).
- "low"       — minor, self-limited, or simple outcomes amenable to self-care or routine follow-up (e.g. common cold, mild headache, minor abrasions, transient indigestion).

Specialty rules:
- Choose the most appropriate single specialty. Use "internal_medicine" if unclear.
- Use lowercase snake_case for specialty.
- For any "critical" case where the dominant feature isn't clearly a single organ system, prefer "emergency_medicine".
"""


VALID: tuple[Severity, ...] = ("low", "moderate", "critical")


def _coerce_severity(raw: str) -> Severity:
    """
    Accept the new 3-level vocabulary and gracefully map legacy 4-level values
    coming from old stored data or stale prompts.
    """
    s = raw.lower().strip()
    if s in VALID:
        return s  # type: ignore[return-value]
    # Legacy 4-level → 3-level fallback.
    legacy = {
        "mild": "low",
        "severe": "critical",
        "emergency": "critical",
    }
    return legacy.get(s, "moderate")  # type: ignore[return-value]


async def grade(
    user_message: str, symptoms: list[str], candidates: list[dict[str, Any]]
) -> dict[str, Any]:
    composed = (
        f"## Patient message\n{user_message}\n\n"
        f"## Extracted symptoms\n{', '.join(symptoms) if symptoms else '(none)'}\n\n"
        f"## RF candidate diseases\n"
        + ("\n".join(f"- {c['disease']}: {c['probability']:.0%}" for c in candidates) or "(none)")
    )
    try:
        result = await chat_json(
            messages=[
                {"role": "system", "content": SEVERITY_PROMPT},
                {"role": "user", "content": composed},
            ],
            temperature=0.0,
        )
    except MedGemmaError:
        return {
            "severity": "moderate",
            "specialty": "internal_medicine",
            "reasoning": "grader unavailable; defaulting",
        }

    severity = _coerce_severity(str(result.get("severity", "")))
    specialty = (
        str(result.get("specialty", "internal_medicine")).lower().strip()
        or "internal_medicine"
    )
    reasoning = str(result.get("reasoning", "")).strip()
    return {"severity": severity, "specialty": specialty, "reasoning": reasoning}


def needs_referral(severity: str) -> bool:
    """True when the patient should be shown a list of nearby specialists."""
    return _coerce_severity(severity) == "critical"
