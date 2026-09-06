"""
MedGemma-driven SOCRATES-style symptom intake.

Hard rules enforced server-side regardless of what MedGemma returns:
  - Maximum of MAX_QUESTIONS questions.
  - Always ends with a structured composed_message even if MedGemma drifts.
  - Letter field is sanitised to S/O/C/R/A/T/E/S or '-'.
  - Refuses to repeat a question key that has already been answered.
"""
from __future__ import annotations

from typing import Any

from app.services.medgemma import MedGemmaError, chat_json

MAX_QUESTIONS = 6  # capped lower than full SOCRATES to feel snappier.

VALID_LETTERS = {"S", "O", "C", "R", "A", "T", "E", "-"}

# Letter → human label. Used as a fallback when MedGemma's letter_label is wrong.
LETTER_LABELS = {
    "S": "Site / Severity",
    "O": "Onset",
    "C": "Character",
    "R": "Radiation",
    "A": "Associated symptoms",
    "T": "Time course",
    "E": "Exacerbating / Relieving",
    "-": "Question",
}

INTAKE_SYSTEM_PROMPT = """You are conducting a focused SOCRATES-style symptom intake for a health-information chatbot. \
Goal: ask the FEWEST possible questions needed to write a clean structured summary that another assistant can act on. \
Do NOT diagnose or reassure here — just ask one good question, then stop.

SOCRATES letters you may use in the "letter" field:
  S — Site
  O — Onset
  C — Character (sharp / dull / burning / pressure / etc.)
  R — Radiation (does it spread)
  A — Associated symptoms
  T — Time course (duration, pattern over the day)
  E — Exacerbating / Relieving factors
  S — Severity (0-10)
Use "-" if the question is free-form (e.g. asking for chief complaint or follow-up).

RULES (follow exactly):
  1. Ask EXACTLY ONE question per turn. The next question must give the highest clinical value GIVEN what is already known.
  2. NEVER re-ask a SOCRATES letter the patient has already answered.
  3. SKIP letters that don't apply (Site / Radiation are usually irrelevant for mental-health or systemic complaints — \
ask Onset/Severity/Associated instead).
  4. STOP and return done=true when ANY of these is true:
       - The patient has provided: chief complaint + onset + character (or associated symptoms) + severity.
       - The patient says they have nothing else to add ("no", "that's all", etc.).
       - You have asked %(max)d questions in total.
  5. When you stop, output a concise plain-English summary of what the patient told you, ready to send to the main chat.

OUTPUT — strict JSON only, no prose around it.

If you still need to ask, return:
{
  "done": false,
  "question": "<one warm, plain-English question — no SOCRATES code shown to the patient>",
  "key": "<short snake_case identifier, e.g. site, onset, character, radiation, associated, time_course, exacerbating, severity, anything_else>",
  "letter": "<one of S O C R A T E or - >",
  "letter_label": "<short label like 'Site' or 'Severity' or 'Chief complaint'>",
  "hint": "<short example to help the patient answer, or empty string>"
}

If you have enough, return:
{
  "done": true,
  "composed_message": "<3-6 sentence plain-English summary of what the patient told you, in their own words. Only include what they said; do not infer or diagnose.>"
}
""" % {"max": MAX_QUESTIONS}


def _answers_block(answers: list[dict[str, Any]]) -> str:
    if not answers:
        return "(none yet — start by asking the chief complaint.)"
    lines = []
    for i, a in enumerate(answers, 1):
        letter = a.get("letter") or "-"
        label = a.get("letter_label") or a.get("key") or "?"
        q = (a.get("question") or "").strip()
        ans = (a.get("answer") or "").strip()
        lines.append(f"  {i}. [{letter}] {label}: Q={q!r} A={ans!r}")
    return "\n".join(lines)


def _sanitize_letter(raw: str | None) -> str:
    if not raw:
        return "-"
    letter = str(raw).strip().upper()[:1]
    return letter if letter in VALID_LETTERS else "-"


def _essentials_covered(answers: list[dict[str, Any]]) -> bool:
    """At least: chief complaint + onset + (character or associated) + severity."""
    keys = {a.get("key") for a in answers}
    has_chief = "chief_complaint" in keys
    has_onset = "onset" in keys
    has_char_or_assoc = "character" in keys or "associated" in keys
    has_severity = "severity" in keys
    return has_chief and has_onset and has_char_or_assoc and has_severity


def _patient_said_no_more(answers: list[dict[str, Any]]) -> bool:
    if not answers:
        return False
    last = (answers[-1].get("answer") or "").strip().lower()
    if not last:
        return False
    no_phrases = (
        "no",
        "nope",
        "thats all",
        "that's all",
        "nothing else",
        "no more",
        "no, that",
        "i'm done",
        "im done",
        "no thanks",
    )
    return any(last.startswith(p) or last == p for p in no_phrases) or "no, that" in last


async def next_step(answers: list[dict[str, Any]]) -> dict[str, Any]:
    """Ask MedGemma for the next intake question (or a final composed_message)."""

    # 1. Server-side hard stops — never trust the LLM to finish on its own.
    if len(answers) >= MAX_QUESTIONS or _essentials_covered(answers) or _patient_said_no_more(answers):
        return {"done": True, "composed_message": _compose_from_answers(answers)}

    # 2. Build the user payload, including how many questions are still allowed.
    user_payload = (
        f"Questions already asked: {len(answers)} of {MAX_QUESTIONS} allowed.\n\n"
        "Patient's responses so far (chronological):\n"
        f"{_answers_block(answers)}\n\n"
        "Pick the next question, or finish the intake. Return strict JSON per the system prompt."
    )

    try:
        result = await chat_json(
            messages=[
                {"role": "system", "content": INTAKE_SYSTEM_PROMPT},
                {"role": "user", "content": user_payload},
            ],
            temperature=0.1,  # low — we want consistent ordering, not creativity.
        )
    except MedGemmaError:
        return _fallback(answers)

    # 3. Defensive normalisation — repair anything MedGemma got wrong.
    if result.get("done") is True:
        return {"done": True, "composed_message": _compose_from_answers(answers)}

    question = str(result.get("question") or "").strip()
    if not question:
        return _fallback(answers)

    key = str(result.get("key") or "").strip().lower() or "anything_else"

    # Never re-ask a key we've already answered. If MedGemma tried to,
    # use the deterministic fallback to pick the next missing one.
    answered_keys = {a.get("key") for a in answers}
    if key in answered_keys:
        return _fallback(answers)

    letter = _sanitize_letter(result.get("letter"))
    label = str(result.get("letter_label") or LETTER_LABELS.get(letter, "Question")).strip()
    return {
        "done": False,
        "step": len(answers) + 1,
        "question": question,
        "key": key,
        "letter": letter,
        "letter_label": label,
        "hint": str(result.get("hint") or "").strip(),
    }


def _fallback(answers: list[dict[str, Any]]) -> dict[str, Any]:
    """If MedGemma is unreachable or invalid, walk a deterministic SOCRATES script."""
    fixed = [
        ("chief_complaint", "What's bothering you today?", "-", "Chief complaint", ""),
        ("onset", "When did it start, and was it sudden or gradual?", "O", "Onset", "e.g. 2 hours ago, suddenly"),
        ("character", "How would you describe how it feels?", "C", "Character", "sharp, dull, burning…"),
        ("associated", "Any other symptoms along with it?", "A", "Associated", "e.g. nausea, sweating"),
        ("time_course", "How long has this been going on, and is there a pattern over the day?", "T", "Time course", ""),
        ("severity", "On a scale of 0 to 10, how severe is it right now?", "S", "Severity", "0-10"),
    ]
    asked = {a.get("key") for a in answers}
    for key, q, letter, label, hint in fixed:
        if key in asked:
            continue
        return {
            "done": False,
            "step": len(answers) + 1,
            "question": q,
            "key": key,
            "letter": letter,
            "letter_label": label,
            "hint": hint,
        }
    return {"done": True, "composed_message": _compose_from_answers(answers)}


def _compose_from_answers(answers: list[dict[str, Any]]) -> str:
    """Deterministic composer — used as the final summary regardless of MedGemma."""
    if not answers:
        return "Patient opened the symptom intake but didn't provide any details."
    lines = ["Structured symptom intake (SOCRATES):"]
    for a in answers:
        label = a.get("letter_label") or a.get("key") or "Response"
        ans = (a.get("answer") or "").strip() or "—"
        lines.append(f"- {label}: {ans}")
    return "\n".join(lines)
