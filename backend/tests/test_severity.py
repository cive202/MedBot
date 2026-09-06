"""
Triage grading tests.

Runs under pytest, or standalone with ``python -m tests.test_severity`` from
the ``backend`` directory (no pytest install needed).

The scenarios are written the way a patient would actually type them — the
point of the severity layer is that it reacts to the person, not just to the
classifier's shortlist.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import clinical_flags  # noqa: E402
from app.services.disease_severity import (  # noqa: E402
    aggregate_severity,
    aggregate_specialty,
    apply_vulnerability,
    escalate_grade,
    grade_from_candidates,
    severity_for,
    specialty_for,
)


def _cands(*pairs: tuple[str, float]) -> list[dict]:
    return [{"disease": d, "probability": p} for d, p in pairs]


# ---------------------------------------------------------------------------
# Disease lookup
# ---------------------------------------------------------------------------

def test_dangerous_diseases_are_critical():
    for disease in (
        "heart attack", "stroke", "pulmonary embolism", "sepsis", "meningitis",
        "diabetic ketoacidosis", "appendicitis", "ectopic pregnancy",
        "testicular torsion", "lung cancer", "retinal detachment",
    ):
        assert severity_for(disease) == "critical", disease


def test_everyday_complaints_are_low():
    for disease in (
        "common cold", "tension headache", "acne", "athlete's foot",
        "sprain or strain", "seasonal allergies (hay fever)", "indigestion",
        "conjunctivitis", "ear wax impaction",
    ):
        assert severity_for(disease) == "low", disease


def test_word_boundary_matching():
    """Substring matching used to mis-grade these three."""
    # "systemic" contains "stemi"; not a heart attack.
    assert severity_for("systemic lupus erythematosis (sle)") == "moderate"
    # "corneal" contains "corn"; a scratched cornea is not a foot callus.
    assert severity_for("corneal abrasion") == "moderate"
    # "contusion" is not automatically minor when it is the heart.
    assert severity_for("heart contusion") == "critical"
    assert severity_for("lung contusion") == "moderate"
    # A red patch on the white of the eye is harmless despite "hemorrhage".
    assert severity_for("subconjunctival hemorrhage") == "low"


def test_specialty_routing():
    assert specialty_for("heart attack") == "cardiology"
    assert specialty_for("stroke") == "neurology"
    assert specialty_for("retinal detachment") == "ophthalmology"
    assert specialty_for("ectopic pregnancy") == "gynecology"


# ---------------------------------------------------------------------------
# Aggregation over the classifier's shortlist
# ---------------------------------------------------------------------------

def test_dominant_dangerous_candidate_is_critical():
    """The regression that started this: real RF probabilities are tiny.

    A 754-class model calls a confident heart attack at p≈0.06. Absolute
    thresholds graded that "low".
    """
    candidates = _cands(
        ("heart attack", 0.06), ("pericarditis", 0.03),
        ("gastroesophageal reflux disease (gerd)", 0.02),
    )
    assert aggregate_severity(candidates) == "critical"
    assert aggregate_specialty(candidates) == "cardiology"


def test_harmless_shortlist_stays_low():
    candidates = _cands(
        ("common cold", 0.21), ("seasonal allergies (hay fever)", 0.09),
        ("acute sinusitis", 0.04),
    )
    assert aggregate_severity(candidates) == "low"


def test_dangerous_longshot_still_warrants_a_visit():
    candidates = _cands(
        ("tension headache", 0.30), ("migraine", 0.10), ("meningitis", 0.08),
    )
    assert aggregate_severity(candidates) == "moderate"


def test_leading_candidate_sets_a_floor():
    """The reported bug: the named condition needed a clinician, badge said "low".

    No critical weight at all, and "moderate" weight below the share
    threshold — the old share-only rule graded this "low" while the reply
    talked about pneumonia.
    """
    candidates = _cands(
        ("pneumonia", 0.08), ("common cold", 0.07), ("acute sinusitis", 0.05),
    )
    assert severity_for("pneumonia") == "moderate"
    assert aggregate_severity(candidates) == "moderate"


def test_leading_dangerous_candidate_is_never_low():
    """A critical leader can hold less than CRITICAL_SHARE of the shortlist."""
    candidates = _cands(
        ("appendicitis", 0.05), ("indigestion", 0.045), ("heartburn", 0.04),
    )
    assert aggregate_severity(candidates) == "critical"


def test_grade_explains_a_non_self_care_verdict():
    result = grade_from_candidates(
        candidates=_cands(("pneumonia", 0.08), ("common cold", 0.07)),
        user_history=None,
        symptom_count=3,
        symptoms=["cough", "fever"],
        text="coughing and a bit of a temperature for a few days",
    )
    assert result["severity"] == "moderate"
    assert "pneumonia" in result["reasoning"].lower()
    assert result["severity_sources"]["leading_disease_tier"] == "moderate"


def test_adding_a_harmless_candidate_cannot_downgrade():
    """Diluting the shortlist used to flip a moderate leader down to "low"."""
    lead_only = _cands(("acute bronchitis", 0.06))
    diluted = lead_only + _cands(("common cold", 0.05), ("laryngitis", 0.04))
    assert aggregate_severity(lead_only) == aggregate_severity(diluted) == "moderate"


def test_moderate_pain_alone_is_not_an_emergency():
    """6/10 belly pain with nothing else: urgent, not critical."""
    assert clinical_flags.assess(["abdominal pain"], "stomach ache, about 6/10").tier == "moderate"
    # …but 6/10 on top of an already-urgent picture still is.
    assert clinical_flags.assess(
        ["sharp chest pain", "sweating"],
        "chest pain and sweating, about 6 out of 10",
    ).tier == "critical"


def test_noise_shortlist_is_not_an_emergency():
    """Near-uniform output over 754 classes is not evidence of anything."""
    candidates = _cands(
        ("lung cancer", 0.004), ("bone cancer", 0.003), ("melanoma", 0.003),
    )
    assert aggregate_severity(candidates) == "moderate"


# ---------------------------------------------------------------------------
# The patient's own presentation
# ---------------------------------------------------------------------------

def test_patient_words_outrank_a_hesitant_classifier():
    result = grade_from_candidates(
        candidates=_cands(("indigestion", 0.004), ("gastritis", 0.003)),
        user_history=None,
        symptom_count=4,
        symptoms=["sharp chest pain", "sweating", "shortness of breath"],
        text="crushing pain in my chest going down my left arm, I'm sweating and it's 9/10",
    )
    assert result["severity"] == "critical"
    assert "chest" in result["reasoning"].lower()


def test_stroke_words_are_critical_with_no_candidates_at_all():
    result = grade_from_candidates(
        candidates=[],
        user_history=None,
        symptom_count=0,
        symptoms=[],
        text="my face is drooping on one side and I can't move my right arm",
    )
    assert result["severity"] == "critical"


def test_self_harm_is_always_critical():
    result = grade_from_candidates(
        candidates=_cands(("depression", 0.05)),
        user_history=None,
        symptom_count=2,
        symptoms=["depression", "insomnia"],
        text="I've been low for months and I've started thinking about ending my life",
    )
    assert result["severity"] == "critical"


def test_severe_pain_score_escalates():
    assert clinical_flags.pain_score("it's about an 8 out of 10") == 8
    assert clinical_flags.pain_score("- Site / Severity: 9") == 9
    assert clinical_flags.pain_score("the pain is unbearable") == 10
    assert clinical_flags.pain_score("just a mild ache") == 2
    assert clinical_flags.pain_score("my ear hurts") is None

    bad = grade_from_candidates(
        candidates=_cands(("gastritis", 0.05), ("indigestion", 0.03)),
        user_history=None, symptom_count=3,
        symptoms=["sharp abdominal pain", "nausea"],
        text="stomach pain, I'd say 9 out of 10",
    )
    assert bad["severity"] == "critical"


def test_mild_presentation_stays_low():
    result = grade_from_candidates(
        candidates=_cands(("common cold", 0.18), ("pharyngitis", 0.06)),
        user_history=None,
        symptom_count=3,
        symptoms=["cough", "sore throat", "nasal congestion"],
        text="runny nose and a slightly sore throat since yesterday, it's mild",
    )
    assert result["severity"] == "low"


def test_negated_red_flags_do_not_escalate():
    result = grade_from_candidates(
        candidates=_cands(("common cold", 0.18), ("pharyngitis", 0.06)),
        user_history=None,
        symptom_count=2,
        symptoms=["sore throat", "cough"],
        text="sore throat and a mild cough. No chest pain and I'm not short of breath.",
    )
    assert result["severity"] == "low"


def test_symptom_combination_beats_either_symptom_alone():
    alone = clinical_flags.assess(["headache"], "my head hurts")
    assert alone.tier == "low"
    together = clinical_flags.assess(
        ["headache", "neck stiffness or tightness", "fever"],
        "bad headache, stiff neck and a fever",
    )
    assert together.tier == "critical"


# ---------------------------------------------------------------------------
# Who the patient is
# ---------------------------------------------------------------------------

def test_risk_history_bumps_one_tier():
    assert apply_vulnerability("low", {"conditions": ["Type 2 diabetes"]}, None)[0] == "moderate"
    assert apply_vulnerability("moderate", {"conditions": ["pregnancy"]}, None)[0] == "critical"
    # Already at the top — nothing to raise, and no spurious reason text.
    assert apply_vulnerability("critical", {"conditions": ["pregnancy"]}, None) == ("critical", [])
    # No risk factors — unchanged.
    assert apply_vulnerability("low", {"conditions": ["hay fever"]}, 30) == ("low", [])


def test_age_extremes_bump():
    assert apply_vulnerability("low", None, 1)[0] == "moderate"
    assert apply_vulnerability("low", None, 82)[0] == "moderate"
    assert apply_vulnerability("low", None, 35) == ("low", [])


def test_llm_fallback_grade_is_raised_never_lowered():
    raised = escalate_grade(
        {"severity": "low", "specialty": "internal_medicine", "reasoning": "seems mild"},
        symptoms=["hemoptysis"],
        text="I coughed up blood this morning",
    )
    assert raised["severity"] == "critical"

    kept = escalate_grade(
        {"severity": "critical", "specialty": "emergency_medicine", "reasoning": "worrying"},
        symptoms=["cough"],
        text="a bit of a cough",
    )
    assert kept["severity"] == "critical"


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_")]


if __name__ == "__main__":
    failures = 0
    for fn in TESTS:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL  {fn.__name__}: {e or '(assertion)'}")
    print(f"\n{len(TESTS) - failures}/{len(TESTS)} passed")
    sys.exit(1 if failures else 0)
