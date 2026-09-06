"""
Random Forest disease classifier — inference side.

Loads a trained sklearn bundle from ``backend/data/rf_model.joblib`` if
present. Train it with ``python -m scripts.train_rf --csv Training.csv``.

Improvements over v1:
  * **Patient-language synonyms.** A dictionary of everyday phrases maps to
    one or more canonical feature names (e.g. "tummy ache" → both
    ``stomach_pain`` and ``abdominal_pain``). This catches symptoms that
    the fuzzy matcher misses because the surface forms are too different.
  * **Lower fuzz threshold (65 vs 70 previously)** + a normalized-form
    fallback (turn spaces/hyphens into underscores before matching) catches
    more borderline cases without much false-positive cost.
  * **Bundle introspection.** ``metadata`` exposes which algorithm trained
    the model (rf vs hgb), the calibration method, and the CV metrics, so
    the frontend can show that context if desired.

Graceful degradation: if no model is loaded, predict() returns []. The chat
pipeline then relies on MedGemma + Chroma RAG alone.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz, process

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
MODEL_PATH = DATA_DIR / "rf_model.joblib"

# A candidate has to beat blind chance by this much to be worth showing…
MIN_CHANCE_MULTIPLE = 2.0
# …and not be a rounding error next to the leading candidate.
MIN_SHARE_OF_TOP = 0.15

# Patient-language → canonical Kaggle symptom feature names.
# Add entries whenever a real user message contains a phrase the fuzzy
# matcher misses. Right-hand side feature names must exist in the trained
# model's feature_names list; non-existent ones are silently filtered out.
SYNONYMS: dict[str, list[str]] = {
    "tummy ache": ["stomach_pain", "abdominal_pain"],
    "belly ache": ["stomach_pain", "abdominal_pain"],
    "belly pain": ["abdominal_pain"],
    "stomachache": ["stomach_pain"],
    "throwing up": ["vomiting"],
    "puking": ["vomiting"],
    "loose motions": ["diarrhoea"],
    "loose stools": ["diarrhoea"],
    "the runs": ["diarrhoea"],
    "runny nose": ["runny_nose"],
    "blocked nose": ["congestion", "sinus_pressure"],
    "stuffy nose": ["congestion"],
    "out of breath": ["breathlessness"],
    "short of breath": ["breathlessness"],
    "cant breathe": ["breathlessness"],
    "trouble breathing": ["breathlessness"],
    "dry cough": ["cough"],
    "wet cough": ["cough", "mucoid_sputum"],
    "sore throat": ["patches_in_throat", "throat_irritation"],
    "scratchy throat": ["throat_irritation"],
    "fever": ["high_fever", "mild_fever"],
    "feverish": ["high_fever", "mild_fever"],
    "shivers": ["chills", "shivering"],
    "feeling cold": ["chills"],
    "tired": ["fatigue", "lethargy"],
    "exhausted": ["fatigue", "lethargy"],
    "no energy": ["fatigue", "lethargy"],
    "dizzy": ["dizziness"],
    "lightheaded": ["dizziness"],
    "spinning": ["spinning_movements"],
    "rash": ["skin_rash"],
    "itchy skin": ["itching"],
    "yellow skin": ["yellowish_skin"],
    "yellow eyes": ["yellowing_of_eyes"],
    "achy joints": ["joint_pain"],
    "muscle ache": ["muscle_pain"],
    "weak muscles": ["muscle_weakness"],
    "lower back pain": ["back_pain"],
    "migraine": ["headache"],
    "no appetite": ["loss_of_appetite"],
    "losing weight": ["weight_loss"],
    "peeing a lot": ["polyuria"],
    "frequent urination": ["polyuria"],
    "burning pee": ["burning_micturition"],
    "blood in stool": ["bloody_stool"],
    "blood in urine": ["spotting_urination"],
    "fast heartbeat": ["fast_heart_rate", "palpitations"],
    "racing heart": ["fast_heart_rate", "palpitations"],
    "heartburn": ["acidity"],
    "bloating": ["abdominal_pain"],
    "blurry vision": ["blurred_and_distorted_vision"],
    "double vision": ["visual_disturbances"],
    "stiff neck": ["neck_pain", "stiff_neck"],
    "panic": ["anxiety"],
    "trouble sleeping": ["restlessness"],
    "insomnia": ["restlessness"],
    "swollen": ["swelling_joints", "swollen_extremities"],
    "swelling": ["swelling_joints", "swollen_extremities"],
}


def _expand_via_synonyms(
    raw_symptoms: list[str], feature_names: set[str]
) -> tuple[list[str], list[str]]:
    """Walk through the user's symptom list, peeling off any phrases that
    appear verbatim in SYNONYMS. Returns (direct_hits, remaining_raw)."""
    direct: list[str] = []
    remaining: list[str] = []
    for s in raw_symptoms:
        key = _normalize_input(s)
        hits = [t for t in SYNONYMS.get(key, ()) if t in feature_names]
        if hits:
            direct.extend(hits)
        else:
            # Either no synonym entry, or every target it names is absent from
            # this model's vocabulary (the table still carries names from an
            # earlier dataset). Either way the term goes to the fuzzy matcher
            # rather than being dropped on the floor.
            remaining.append(s)
    return direct, remaining


def _normalize_input(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().replace("_", " ").replace("-", " ")).strip()


class RFPredictor:
    def __init__(self) -> None:
        self.model: Any = None
        self.feature_names: list[str] = []
        self.classes: list[str] = []
        self.metadata: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if not MODEL_PATH.exists():
            log.info("RF model not found at %s — pipeline will skip the RF step.", MODEL_PATH)
            return
        try:
            import joblib

            bundle = joblib.load(MODEL_PATH)
            self.model = bundle["model"]
            self.feature_names = list(bundle["features"])
            self.classes = list(bundle["classes"])
            self.metadata = {
                "algo": bundle.get("algo", "rf"),
                "calibration": bundle.get("calibration", "none"),
                "trained_at": bundle.get("trained_at"),
                "metrics": bundle.get("metrics", {}),
            }
            log.info(
                "Loaded classifier (%s, calibration=%s): %d features, %d classes",
                self.metadata["algo"], self.metadata["calibration"],
                len(self.feature_names), len(self.classes),
            )
        except Exception as e:
            log.warning("Failed to load classifier bundle: %s", e)
            self.model = None

    @property
    def ready(self) -> bool:
        return self.model is not None

    def match_symptoms(
        self, raw_symptoms: list[str], score_cutoff: int = 65
    ) -> list[str]:
        """Map free-text symptoms → canonical feature names.

        1. Synonym dictionary first (direct hit, no fuzzy work).
        2. Fuzzy match remaining terms — try the original term, then the
           snake_case-normalized form.
        3. Deduplicate while preserving insertion order.
        """
        if not self.feature_names:
            return []
        feature_set = set(self.feature_names)
        direct, remaining = _expand_via_synonyms(raw_symptoms, feature_set)
        matched: list[str] = list(direct)
        for term in remaining:
            normalized = _normalize_input(term)
            for query in (normalized, normalized.replace(" ", "_")):
                best = process.extractOne(query, self.feature_names, scorer=fuzz.WRatio)
                if best and best[1] >= score_cutoff:
                    matched.append(best[0])
                    break
        return list(dict.fromkeys(matched))

    def predict(self, raw_symptoms: list[str], top_k: int = 3) -> list[dict[str, Any]]:
        if not self.ready or not raw_symptoms:
            return []
        canonical = self.match_symptoms(raw_symptoms)
        if not canonical:
            return []
        vector = [1 if f in canonical else 0 for f in self.feature_names]
        try:
            probs = self.model.predict_proba([vector])[0]
        except Exception as e:
            log.warning("classifier predict failed: %s", e)
            return []
        # Prefer model.classes_ over the bundled list — a calibrated wrapper
        # may have a different ordering than the raw base estimator.
        classes = list(getattr(self.model, "classes_", self.classes))
        ranked = sorted(zip(classes, probs), key=lambda x: x[1], reverse=True)
        if not ranked:
            return []

        # Keep candidates that clear a *relative* bar. With 754 classes even a
        # confident prediction lands around p≈0.06, so the old flat p>0.01 cut
        # threw away the whole shortlist on most real messages and left triage
        # with nothing to grade.
        chance = 1.0 / len(classes)
        top = float(ranked[0][1])
        floor = max(chance * MIN_CHANCE_MULTIPLE, top * MIN_SHARE_OF_TOP)
        out = [{"disease": ranked[0][0], "probability": top}]  # always keep the leader
        out.extend(
            {"disease": d, "probability": float(p)}
            for d, p in ranked[1:top_k]
            if p >= floor
        )
        return out


# Module-level singleton; loads lazily on first import.
_predictor: RFPredictor | None = None


def get_predictor() -> RFPredictor:
    global _predictor
    if _predictor is None:
        _predictor = RFPredictor()
    return _predictor


def get_predictor_if_loaded() -> RFPredictor | None:
    """Return the singleton without triggering a load. For non-blocking status checks."""
    return _predictor
