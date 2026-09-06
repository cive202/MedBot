"""
Orchestrates symptom-extraction → RF → RAG (Chroma via LangChain) → MedGemma.

Conversation-aware triage:
  * Symptoms are extracted from EVERY prior user turn in the conversation
    plus the new message, unioned, and passed to the RF classifier so the
    candidate set reflects the full picture, not just the latest sentence.
  * Severity comes from the RF candidates' intrinsic disease severity,
    weighted by their probabilities, with a bump for high-risk patient
    history. See app/services/disease_severity.py.
  * MedGemma severity is only used as a fallback when RF returns no
    candidates at all.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from app.safety.disclaimer import DISCLAIMER
from app.services import disease_severity, specialists
from app.services.medgemma import chat_stream
from app.services.patient_context import PatientContext
from app.services.rag import format_context, retrieve
from app.services.rf import get_predictor
from app.services.severity import grade, needs_referral
from app.services.symptom_extractor import extract_symptoms

SYSTEM_PROMPT = """You are MedAssist, a careful, conservative health-information assistant powered by MedGemma. \
You explain possibilities to a patient in plain language without giving definitive diagnoses.
Always reply in English, using warm, everyday vocabulary.

For every patient message you receive, the application will append a structured context block containing:
  - The patient's demographic profile and medical history.
  - Canonical symptoms accumulated across the conversation.
  - Top candidate diseases from a Random Forest classifier (with probabilities).
  - A severity grade (low / moderate / critical) derived from the candidate diseases and a suggested specialty.
  - Reference snippets retrieved from a medical knowledge base when available.

How to reply:
  1. Acknowledge what the patient just told you. Reference earlier turns when relevant.
  2. Explain the candidate conditions in everyday language, noting overlap of symptoms.
  3. Suggest reasonable next steps consistent with the severity grade:
       - "low"      → self-care, watchful waiting, simple measures.
       - "moderate" → see a clinician this week / soon.
       - "critical" → seek immediate professional care or call emergency services.
     The grade is shown to the patient next to your reply, so your advice must match it.
     Do not tell someone graded "low" that they need to be seen — if the picture really
     warrants a visit, that belongs in the grade, not only in your prose.
  4. Be explicit about uncertainty. Never invent numbers.

Conversation style — important:
  - Treat this as an ongoing conversation. The patient may add details over multiple turns.
  - Always end your reply with ONE short, targeted follow-up question that would help you narrow things
    down. Pick the question that most changes your differential. Phrase it warmly.
  - If the patient already answered a SOCRATES-style intake, don't re-ask those questions — pick a new angle.
  - If they say "no, that's all" or similar, stop asking and gently close.

Format the response as friendly markdown. Do not output JSON. Do not include the structured context block in your reply.
"""

# How many of the patient's own turns the triage flag rules read back through.
MAX_TRIAGE_TURNS = 8


def _profile_block(patient: PatientContext) -> str:
    parts = [
        f"- Name: {patient.full_name or 'unknown'}",
        f"- Sex: {patient.sex or 'unknown'}",
        f"- Date of birth: "
        f"{patient.date_of_birth.isoformat() if patient.date_of_birth else 'unknown'}",
    ]
    if patient.history:
        h = patient.history
        if h.get("conditions"):
            parts.append(f"- Pre-existing conditions: {', '.join(h['conditions'])}")
        if h.get("medications"):
            parts.append(f"- Current medications: {', '.join(h['medications'])}")
        if h.get("allergies"):
            parts.append(f"- Allergies: {', '.join(h['allergies'])}")
        if h.get("blood_group"):
            parts.append(f"- Blood group: {h['blood_group']}")
        if h.get("notes"):
            parts.append(f"- Notes: {h['notes']}")
    return "\n".join(parts)


def _candidates_block(candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return "(none — RF model unavailable or no symptoms matched its vocabulary)"
    return "\n".join(
        f"- {c['disease']}: probability {c['probability']:.0%}" for c in candidates
    )


def _patient_text(message: str, history: list[dict[str, str]]) -> str:
    """Everything the patient has said this conversation, newest first.

    The triage flag rules read this for the things people say that no symptom
    vocabulary captures — "I can't breathe", "worst pain of my life", a 9/10
    severity answer from the SOCRATES intake.
    """
    said = [message.strip()] + [
        (h.get("content") or "").strip()
        for h in reversed(history)
        if h.get("role") == "user" and (h.get("content") or "").strip()
    ]
    return "\n".join(said[:MAX_TRIAGE_TURNS])


async def _extract_all_symptoms(
    message: str, history: list[dict[str, str]]
) -> tuple[list[str], list[str]]:
    """Extract symptoms from the new message + every prior user message in
    parallel. Returns (current_message_symptoms, accumulated_unique_symptoms).
    """
    prior_user_msgs = [
        (h.get("content") or "").strip()
        for h in history
        if h.get("role") == "user" and (h.get("content") or "").strip()
    ]

    tasks = [extract_symptoms(m) for m in prior_user_msgs] + [extract_symptoms(message)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    symptom_lists: list[list[str]] = []
    for r in results:
        if isinstance(r, list):
            symptom_lists.append(r)
        else:
            symptom_lists.append([])

    current_symptoms = symptom_lists[-1] if symptom_lists else []

    seen: set[str] = set()
    accumulated: list[str] = []
    for lst in reversed(symptom_lists):
        for s in lst:
            if s not in seen:
                seen.add(s)
                accumulated.append(s)

    return current_symptoms, accumulated


async def predict_and_explain(
    patient: PatientContext,
    message: str,
    history: list[dict[str, str]] | None = None,
) -> tuple[AsyncIterator[str], dict[str, Any]]:
    """Returns (stream of MedGemma deltas, structured metadata).

    ``patient`` carries whatever profile details are known — a signed-in user's
    saved record, a guest's one-off details, or nothing at all.
    """
    history = history or []

    # 1. Extract symptoms from latest + every prior user turn in parallel.
    current_symptoms, accumulated_symptoms = await _extract_all_symptoms(message, history)

    # 2. RF predicts top-3 candidate diseases using the FULL accumulated symptom set.
    candidates = await asyncio.to_thread(
        get_predictor().predict, accumulated_symptoms, 3
    )

    # 3. RAG retrieval.
    restrict = [c["disease"] for c in candidates] if candidates else None
    try:
        chunks = await asyncio.wait_for(
            retrieve(message, k=5, restrict_to=restrict), timeout=8.0
        )
    except (asyncio.TimeoutError, Exception):  # noqa: BLE001
        chunks = []
    if not chunks and restrict:
        try:
            chunks = await asyncio.wait_for(retrieve(message, k=5), timeout=4.0)
        except (asyncio.TimeoutError, Exception):  # noqa: BLE001
            chunks = []
    context = format_context(chunks)

    # 4. Triage: the classifier's shortlist and the patient's own presentation,
    #    whichever is worse. MedGemma only grades when the RF returns nothing,
    #    and even then the symptom rules set the floor.
    age = disease_severity.age_from_dob(patient.date_of_birth)
    patient_text = _patient_text(message, history)
    if candidates:
        triage = disease_severity.grade_from_candidates(
            candidates=candidates,
            user_history=patient.history,
            symptom_count=len(accumulated_symptoms),
            symptoms=accumulated_symptoms,
            text=patient_text,
            age=age,
        )
    else:
        triage = disease_severity.escalate_grade(
            await grade(message, accumulated_symptoms, []),
            symptoms=accumulated_symptoms,
            text=patient_text,
            user_history=patient.history,
            age=age,
        )

    # 5. KNN nearest specialists when severity warrants — fast, in a thread.
    nearby: list[dict[str, Any]] = []
    if needs_referral(triage["severity"]) and patient.location:
        try:
            loc = patient.location
            nearby = await asyncio.to_thread(
                specialists.search,
                lat=float(loc["lat"]),
                lon=float(loc["lon"]),
                specialty=triage["specialty"],
                k=5,
            )
        except Exception:
            nearby = []

    # 6. Compose the user-turn payload.
    composed_user = (
        f"{message}\n\n"
        f"---\n"
        f"## Patient profile\n{_profile_block(patient)}\n\n"
        f"## Symptoms accumulated this conversation\n"
        f"{', '.join(accumulated_symptoms) if accumulated_symptoms else '(none extracted)'}\n\n"
        f"## RF candidate diseases\n{_candidates_block(candidates)}\n\n"
        f"## Triage\nSeverity: {triage['severity']}. "
        f"Suggested specialty: {triage['specialty']}. "
        f"{triage['reasoning']}\n\n"
        f"## Knowledge-base context\n{context}\n"
    )

    # 7. Replay conversation history (without context blocks).
    history_msgs: list[dict[str, str]] = []
    for h in history[-8:]:
        role = h.get("role")
        content = (h.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            history_msgs.append({"role": role, "content": content})

    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + history_msgs
        + [{"role": "user", "content": composed_user}]
    )

    metadata = {
        "symptoms": current_symptoms,
        "symptoms_accumulated": accumulated_symptoms,
        "candidates": candidates,
        "retrieved": [
            {"disease": c.get("disease", ""), "section": c.get("section", "")}
            for c in chunks
        ],
        "severity": triage["severity"],
        "specialty": triage["specialty"],
        "severity_reasoning": triage["reasoning"],
        "severity_sources": triage.get("severity_sources", {}),
        "nearby_specialists": nearby,
    }

    async def stream() -> AsyncIterator[str]:
        async for delta in chat_stream(messages=messages, temperature=0.3):
            yield delta
        yield DISCLAIMER

    return stream(), metadata
