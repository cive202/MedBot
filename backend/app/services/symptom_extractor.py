"""
Fast, deterministic symptom extraction.

The RF model's feature_names list (377 entries from the Kaggle dataset) is our
canonical vocabulary. For each feature, we check if its significant words
(stop-words removed) appear in the user message:

- Single-word features must appear verbatim (after normalization).
- Multi-word features require >= 2 word overlap AND >= 2/3 coverage so we
  don't match "anxiety and nervousness" on a message that just says "I have".

Words are reduced to a crude stem on both sides first, because patients write
"my ankle is swollen" and the feature is called "ankle swelling", "my back
hurts" and the feature is "back pain". Without that, real complaints extracted
to nothing and the classifier — and the triage grade built on it — had nothing
to work with.

Finally, everyday phrasings that never resemble the canonical name at all
("throwing up", "can't catch my breath") come from ``clinical_flags``.

This is ~20 ms wall time on 377 features, needs no MedGemma call, and gives
the RF model a clean canonical vocabulary every time.
"""
from __future__ import annotations

import asyncio
import re
from functools import lru_cache

from app.services.clinical_flags import symptoms_from_text
from app.services.rf import get_predictor

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'-]+")

_STOPWORDS = frozenset({
    "a", "an", "and", "any", "are", "as", "at", "be", "been", "being",
    "but", "by", "do", "does", "did", "for", "from", "had", "has", "have",
    "having", "he", "her", "him", "his", "i", "in", "is", "it", "its",
    "just", "me", "my", "no", "not", "of", "on", "or", "our", "really",
    "she", "so", "some", "such", "than", "that", "the", "their", "them",
    "then", "there", "these", "they", "this", "those", "to", "too", "very",
    "was", "we", "were", "what", "when", "where", "which", "who", "with",
    "would", "you", "your", "yours", "ive", "im", "id", "cant", "wont",
    "since", "lot", "lots", "feel", "feeling", "felt", "much", "more",
    "less", "still", "now", "today", "yesterday", "ago", "got",
})


# Words patients use vs. words the dataset uses. Applied to the feature names
# too, so both sides meet in the middle.
_IRREGULAR: dict[str, str] = {
    "hurt": "pain", "hurts": "pain", "hurting": "pain", "hurted": "pain",
    "ache": "pain", "aches": "pain", "aching": "pain", "achy": "pain",
    "sore": "pain", "soreness": "pain", "painful": "pain", "pains": "pain",
    "swollen": "swell", "swelling": "swell", "swells": "swell",
    "puffy": "swell", "puffed": "swell",
    "stiff": "stiff", "stiffness": "stiff", "tight": "tight", "tightness": "tight",
    "weak": "weak", "weakness": "weak", "weakened": "weak",
    "itchy": "itch", "itching": "itch", "itches": "itch", "itchiness": "itch",
    "bleed": "bleed", "bleeding": "bleed", "bled": "bleed", "bloody": "blood",
    "breathe": "breath", "breathing": "breath", "breaths": "breath",
    "breathless": "breath", "breathlessness": "breath",
    "vomit": "vomit", "vomiting": "vomit", "vomited": "vomit", "puking": "vomit",
    "dizzy": "dizzy", "dizziness": "dizzy",
    "sleepy": "sleep", "sleepiness": "sleep", "drowsy": "sleep",
    "numb": "numb", "numbness": "numb",
    "cramp": "cramp", "cramps": "cramp", "cramping": "cramp",
    "spasm": "spasm", "spasms": "spasm",
    "feverish": "fever", "temperature": "fever",
    "sneezing": "sneeze", "sneezes": "sneeze",
    "coughing": "cough", "coughs": "cough",
    "burning": "burn", "burns": "burn", "burnt": "burn",
    "discharging": "discharge", "bruising": "bruise", "bruised": "bruise",
    "tired": "fatigue", "tiredness": "fatigue", "exhausted": "fatigue",
}


def _stem(word: str) -> str:
    """Crude, deliberately conservative stemmer — enough to bridge
    "swollen"/"swelling" and "hurts"/"pain" without collapsing real words."""
    if word in _IRREGULAR:
        return _IRREGULAR[word]
    if len(word) > 6 and word.endswith("ness"):
        return word[:-4]
    if len(word) > 5 and word.endswith("ing"):
        return word[:-3]
    if len(word) > 4 and word.endswith("ed"):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def _norm_words(text: str) -> set[str]:
    """Significant, stemmed lowercase words from a free-text string."""
    return {
        _stem(w) for w in _TOKEN_RE.findall(text.lower())
        if w not in _STOPWORDS and len(w) >= 2
    }


@lru_cache(maxsize=1)
def _feature_word_index() -> list[tuple[str, frozenset[str]]]:
    """Cache the (feature_name, significant_words) list once per process."""
    rf = get_predictor()
    out: list[tuple[str, frozenset[str]]] = []
    for f in rf.feature_names:
        words = frozenset(_norm_words(f.replace("_", " ")))
        if words:
            out.append((f, words))
    return out


def _extract_sync(message: str) -> list[str]:
    msg_words = _norm_words(message)
    if not msg_words:
        return []

    matched: list[str] = []
    for feature, feat_words in _feature_word_index():
        overlap = feat_words & msg_words
        if not overlap:
            continue
        if len(feat_words) == 1:
            # Single-word feature: that one word must be in the message.
            matched.append(feature)
        elif len(overlap) >= 2 and len(overlap) / len(feat_words) >= 0.66:
            # Multi-word feature: require >=2 overlapping words and >=66% coverage.
            matched.append(feature)

    # Everyday phrasings the word-overlap test can't reach.
    known = {f for f, _ in _feature_word_index()}
    for symptom in symptoms_from_text(message):
        if symptom in known and symptom not in matched:
            matched.append(symptom)
    return matched


async def extract_symptoms(user_message: str) -> list[str]:
    """Return the canonical RF symptom names the user mentioned in their message."""
    return await asyncio.to_thread(_extract_sync, user_message)
