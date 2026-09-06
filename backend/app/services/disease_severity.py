"""
Triage grading: how dangerous is this presentation?

Two independent signals are combined, and the worse one wins:

  1. **The classifier's differential.** ``severity_for(disease)`` gives a
     disease its intrinsic tier; ``aggregate_severity`` weighs the RF's
     top-K candidates against each other.
  2. **The patient's own presentation.** ``clinical_flags.assess`` reads the
     symptoms accumulated across the conversation and the patient's own
     words — chest pain with sweating, "I can't breathe", a 9/10 pain score.
     See ``app/services/clinical_flags.py``.

Then ``apply_vulnerability`` bumps one tier for patients whose age or medical
history makes the same illness more dangerous.

Design notes
------------
*Shares, not raw probabilities.* The RF has 754 classes, so a confident
prediction still comes back as p≈0.06 and a vague one as p≈0.003. Absolute
thresholds are meaningless against numbers like that (they graded a textbook
heart attack as "low"). What matters is how much of the *shortlist* is
dangerous, so probabilities are normalised across the candidates first.

*The leading candidate sets a floor.* Shares alone are not enough: the top
candidate is the condition actually named back to the patient, and the reply
is written around it. A shortlist of [pneumonia 40%, common cold 35%, sinusitis
25%] carries no "critical" weight and only 0.40 of "moderate", which the share
thresholds graded "low" — so the assistant said "get this looked at" while the
badge said "minor, self-care usually fine". The leading candidate's own tier is
now a floor under the grade, which is what keeps the number and the words
agreeing. "Low" means the most likely condition is itself harmless.

*Noise guard.* When every candidate is near the 1/754 floor, the differential
is not evidence of anything. In that case the disease signal is capped at
"moderate" — but the symptom signal is never capped, so someone describing a
stroke still gets "critical" even when the classifier is lost.

*Word-boundary matching.* Keywords are matched as whole words. Plain substring
matching silently graded every "systemic ..." disease as critical (it contains
"stemi") and "corneal abrasion" / "lung contusion" as low.

The keyword tables are backed by explicit entries for the diseases in the
trained model's class list. Anything unrecognised defaults to "moderate";
``backend/data/disease_severity.json`` (built by ``scripts/grade_diseases.py``)
can override any of it without a code change.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from datetime import date
from pathlib import Path
from typing import Any

from app.services import clinical_flags
from app.services.clinical_flags import rank, worst

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CACHE_PATH = DATA_DIR / "disease_severity.json"

VALID_TIERS = clinical_flags.TIERS  # ("low", "moderate", "critical")


# ---------------------------------------------------------------------------
# Explicit per-disease grades, written against the trained model's class list.
# Anything here wins over the keyword scan below.
# ---------------------------------------------------------------------------

CRITICAL_DISEASES: frozenset[str] = frozenset({
    # Cardiac / vascular
    "heart attack", "cardiac arrest", "angina", "endocarditis",
    "heart block", "paroxysmal ventricular tachycardia",
    "paroxysmal supraventricular tachycardia",
    "hypertrophic obstructive cardiomyopathy (hocm)", "malignant hypertension",
    "abdominal aortic aneurysm", "thoracic aortic aneurysm",
    "deep vein thrombosis (dvt)", "pulmonary embolism",
    "peripheral arterial embolism", "heart contusion", "pulmonary congestion",
    # Neuro
    "stroke", "transient ischemic attack", "hemiplegia", "moyamoya disease",
    "vertebrobasilar insufficiency", "cerebral edema", "hydrocephalus",
    "intracranial abscess", "epidural hemorrhage", "subdural hemorrhage",
    "intracerebral hemorrhage", "intracranial hemorrhage",
    "subarachnoid hemorrhage", "meningitis", "encephalitis",
    "hepatic encephalopathy", "guillain barre syndrome", "myasthenia gravis",
    "delirium", "wernicke korsakoff syndrome",
    # Respiratory
    "acute respiratory distress syndrome (ards)", "pneumothorax",
    "abscess of the lung", "empyema", "foreign body in the throat",
    "acute bronchospasm",
    # Infection
    "sepsis", "septic arthritis", "necrotizing fasciitis", "osteomyelitis",
    "peritonitis", "peritonsillar abscess", "abscess of the pharynx",
    "mastoiditis", "orbital cellulitis", "ascending cholangitis",
    "malaria", "dengue fever", "toxic shock", "lymphangitis",
    # Abdominal emergencies
    "appendicitis", "cholecystitis", "acute pancreatitis",
    "intestinal obstruction", "volvulus", "intussusception",
    "ischemia of the bowel", "gastrointestinal hemorrhage",
    "esophageal varices", "pyloric stenosis", "hirschsprung disease",
    "ileus",
    # Renal / metabolic
    "acute kidney injury", "kidney failure", "diabetic ketoacidosis",
    "hyperosmotic hyperketotic state", "hypoglycemia", "hyperkalemia",
    "hyponatremia", "hypercalcemia", "rhabdomyolysis", "hypovolemia",
    "pyelonephritis", "urinary tract obstruction", "hypothermia",
    # Obstetric / urogenital
    "ectopic pregnancy", "placental abruption", "placenta previa",
    "preeclampsia", "hypertension of pregnancy",
    "acute fatty liver of pregnancy (aflp)",
    "premature rupture of amniotic membrane", "uterine atony",
    "spontaneous abortion", "missed abortion", "threatened pregnancy",
    "hydatidiform mole", "testicular torsion", "ovarian torsion",
    "priapism",
    # Eyes (sight-threatening)
    "acute glaucoma", "retinal detachment",
    "central retinal artery or vein occlusion", "endophthalmitis",
    "optic neuritis", "vitreous hemorrhage", "cornea infection",
    # Trauma
    "injury to the spinal cord", "injury to internal organ", "crushing injury",
    "head injury", "fracture of the skull", "fracture of the neck",
    "fracture of the vertebra", "fracture of the pelvis",
    "dislocation of the vertebra", "burn", "envenomation from spider or animal bite",
    # Haematology / oncology
    "leukemia", "lymphoma", "multiple myeloma", "myelodysplastic syndrome",
    "aplastic anemia", "sickle cell crisis", "metastatic cancer",
    # Toxicology
    "insulin overdose", "carbon monoxide poisoning",
    "drug poisoning due to medication", "alcohol withdrawal",
})

LOW_DISEASES: frozenset[str] = frozenset({
    # Skin / hair / nails
    "acne", "athlete's foot", "callus", "bunion", "hammer toe",
    "contact dermatitis", "dermatitis due to sun exposure",
    "seborrheic dermatitis", "seborrheic keratosis", "eczema", "dyshidrosis",
    "intertrigo (skin condition)", "skin pigmentation disorder", "scar",
    "sebaceous cyst", "skin polyp", "lipoma", "molluscum contagiosum",
    "viral warts", "lice", "scabies", "impetigo", "insect bite",
    "onychomycosis", "paronychia", "ingrown toe nail", "pityriasis rosea",
    "alopecia", "hirsutism", "hyperhidrosis", "acanthosis nigricans",
    "fungal infection of the hair", "fungal infection of the skin",
    "diaper rash", "cold sore", "rosacea",
    # Eyes / ears / mouth / throat
    "stye", "chalazion", "blepharitis", "dry eye of unknown cause",
    "conjunctivitis", "conjunctivitis due to allergy",
    "conjunctivitis due to virus", "conjunctivitis due to bacteria",
    "pinguecula", "presbyopia", "myopia", "hyperopia", "astigmatism",
    "ear wax impaction", "otitis externa (swimmer's ear)",
    "aphthous ulcer", "dental caries", "gum disease", "teething syndrome",
    "oral thrush (yeast infection)", "laryngitis", "pharyngitis",
    "seasonal allergies (hay fever)", "allergy", "allergy to animals",
    "acute sinusitis", "chronic sinusitis", "common cold",
    # Musculoskeletal
    "sprain or strain", "muscle spasm", "lumbago", "plantar fasciitis",
    "bone spur of the calcaneous", "trigger finger (finger disorder)",
    "ganglion cyst", "flat feet",
    # General
    "tension headache", "indigestion", "heartburn",
    "gastroesophageal reflux disease (gerd)", "lactose intolerance",
    "flatulence", "hemorrhoids", "varicose veins",
    "mittelschmerz", "premenstrual tension syndrome", "menopause",
    "vaginal yeast infection", "yeast infection",
    "benign vaginal discharge (leukorrhea)", "gynecomastia",
    "itching of unknown cause", "tinnitus of unknown cause",
    "pinworm infection", "cat scratch disease",
})


def _build_explicit() -> dict[str, str]:
    table = {name: "critical" for name in CRITICAL_DISEASES}
    table.update({name: "low" for name in LOW_DISEASES})
    # A handful of names the keyword scan would otherwise over-call.
    table.update({
        "subconjunctival hemorrhage": "low",      # a harmless red patch on the eye
        "avascular necrosis": "moderate",
        "lymphedema": "moderate",
        "anemia due to malignancy": "critical",
        "premature ovarian failure": "moderate",
        "systemic lupus erythematosis (sle)": "moderate",
        "panic attack": "moderate",
        "panic disorder": "moderate",
        "lung contusion": "moderate",
        "corneal abrasion": "moderate",
        "corneal disorder": "moderate",
        "chronic kidney disease": "moderate",
        "chronic pancreatitis": "moderate",
        "epilepsy": "moderate",
        "concussion": "moderate",
    })
    return table


EXPLICIT_SEVERITY: dict[str, str] = _build_explicit()


# ---------------------------------------------------------------------------
# Keyword fallback for disease names not listed above (matched as whole words).
# ---------------------------------------------------------------------------

CRITICAL_KEYWORDS: tuple[str, ...] = (
    # Oncology
    "cancer", "carcinoma", "sarcoma", "lymphoma", "leukemia", "melanoma",
    "neoplasm", "malignant", "malignancy", "metastatic", "metastasis",
    # Cardiac
    "myocardial infarction", "heart attack", "cardiac arrest", "tamponade",
    "aortic dissection", "aneurysm",
    # Vascular / neuro
    "hemorrhage", "haemorrhage", "stroke", "embolism", "embolus",
    "intracranial",
    # Infection / inflammation
    "anaphylaxis", "sepsis", "septicemia", "meningitis", "encephalitis",
    "necrotizing", "gangrene", "fulminant", "ebola", "rabies", "tetanus",
    # Respiratory / metabolic emergencies
    "pulmonary edema", "pulmonary oedema", "respiratory failure",
    "ketoacidosis", "hyperosmolar", "shock",
    # GI emergencies
    "perforation", "perforated", "ischemic bowel", "ischaemic bowel",
    # Obstetric
    "ectopic pregnancy", "placental abruption", "eclampsia", "preeclampsia",
    # Organ failure
    "liver failure", "kidney failure", "renal failure", "heart failure",
    "respiratory arrest",
    # Toxicology / self-harm
    "overdose", "poisoning", "suicide", "self-harm",
)

LOW_KEYWORDS: tuple[str, ...] = (
    "common cold", "viral rhinitis", "viral pharyngitis", "tension headache",
    "dermatitis", "eczema", "acne", "tinea", "athlete's foot",
    "wart", "warts", "verruca", "callus",
    "indigestion", "heartburn", "hangover",
    "stye", "blepharitis", "head lice", "lice", "scabies",
    "earwax", "cerumen", "ear wax impaction",
)


def _compile(keywords: tuple[str, ...]) -> tuple[tuple[str, re.Pattern[str]], ...]:
    """Whole-word (or whole-phrase) matchers, tolerant of hyphens/underscores."""
    out = []
    for kw in keywords:
        body = re.escape(kw).replace(r"\ ", r"[\s_\-]+")
        out.append((kw, re.compile(rf"(?<![a-z0-9]){body}(?![a-z0-9])", re.IGNORECASE)))
    return tuple(out)


_CRITICAL_RES = _compile(CRITICAL_KEYWORDS)
_LOW_RES = _compile(LOW_KEYWORDS)


# ---------------------------------------------------------------------------
# Specialty mapping. First matching specialty wins, so order is significant
# (more specific organ systems before generalists).
# ---------------------------------------------------------------------------

SPECIALTY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("cardiology", (
        "heart", "cardiac", "cardiomyopathy", "myocardial", "angina",
        "arrhythmia", "hypertension", "tachycardia", "bradycardia", "valve",
        "endocarditis", "pericarditis", "atrial", "ventricular", "aortic",
    )),
    ("neurology", (
        "stroke", "epilepsy", "seizure", "migraine", "neuropathy", "neuritis",
        "parkinson", "alzheimer", "dementia", "meningitis", "encephalitis",
        "multiple sclerosis", "cerebral", "intracranial", "neuralgia",
        "hemiplegia", "ataxia", "myelopathy",
    )),
    ("pulmonology", (
        "pulmonary", "respiratory", "lung", "asthma", "bronchitis",
        "bronchiolitis", "bronchospasm", "pneumonia", "copd", "emphysema",
        "tuberculosis", "sleep apnea", "pleural", "pneumothorax",
    )),
    ("gastroenterology", (
        "gastric", "gastritis", "gastroenteritis", "intestinal", "colitis",
        "colon", "colorectal", "stomach", "liver", "hepatitis", "cirrhosis",
        "gallstone", "gallbladder", "cholecystitis", "pancreatitis", "ulcer",
        "gerd", "reflux", "appendicitis", "diverticulitis", "irritable bowel",
        "esophageal", "esophagitis", "bowel", "anal", "rectal", "hemorrhoids",
    )),
    ("urology", (
        "urinary", "bladder", "kidney", "renal", "prostate", "pyelonephritis",
        "urethral", "urethritis", "ureter", "testicular", "testicle",
        "scrotum", "penis", "erectile",
    )),
    ("dermatology", (
        "skin", "rash", "eczema", "psoriasis", "acne", "dermatitis",
        "tinea", "wart", "warts", "scabies", "melanoma", "cellulitis",
        "impetigo", "alopecia", "rosacea", "nail",
    )),
    ("ent", (
        "ear", "sinus", "sinusitis", "tonsil", "tonsillitis", "pharyngitis",
        "laryngitis", "rhinitis", "otitis", "nasal", "throat", "hearing",
        "vocal cord", "mastoiditis",
    )),
    ("ophthalmology", (
        "eye", "ocular", "retina", "retinal", "glaucoma", "cataract",
        "conjunctivitis", "uveitis", "cornea", "corneal", "vision",
        "eyelid", "vitreous", "optic",
    )),
    ("orthopedics", (
        "fracture", "bone", "joint", "arthritis", "osteoarthritis",
        "osteoporosis", "sprain", "strain", "dislocation", "tendinitis",
        "bursitis", "meniscus", "ligament", "spinal", "spondylitis",
        "scoliosis", "rotator cuff",
    )),
    ("psychiatry", (
        "depression", "depressive", "anxiety", "bipolar", "schizophrenia",
        "psychotic", "psychosis", "addiction", "abuse", "suicide", "panic",
        "ptsd", "ocd", "eating disorder", "personality disorder",
    )),
    ("endocrinology", (
        "diabetes", "diabetic", "thyroid", "thyroiditis", "hyperthyroid",
        "hypothyroidism", "adrenal", "pituitary", "parathyroid", "cushing",
    )),
    ("hematology", (
        "anemia", "anaemia", "leukemia", "lymphoma", "thrombocytopenia",
        "thrombophlebitis", "hemophilia", "haemophilia", "myeloma",
        "sickle cell", "coagulation", "spherocytosis",
    )),
    ("rheumatology", (
        "rheumatoid", "rheumatic", "lupus", "gout", "fibromyalgia",
        "vasculitis", "scleroderma", "sjogren", "polymyalgia", "sarcoidosis",
    )),
    ("oncology", (
        "cancer", "carcinoma", "sarcoma", "metastatic", "malignant", "tumor",
    )),
    ("infectious_disease", (
        "sepsis", "tuberculosis", "malaria", "dengue", "typhoid", "hiv",
        "syphilis", "gonorrhea", "chlamydia", "abscess", "infection",
    )),
    ("gynecology", (
        "pregnancy", "pregnant", "menstrual", "menstruation", "uterine",
        "ovarian", "cervical", "endometriosis", "endometrial", "pcos",
        "vaginal", "vaginitis", "vulvar", "placenta", "placental",
        "eclampsia", "abortion", "breast",
    )),
]

_SPECIALTY_RES: list[tuple[str, tuple[re.Pattern[str], ...]]] = [
    (name, tuple(p for _, p in _compile(kws))) for name, kws in SPECIALTY_KEYWORDS
]


# ---------------------------------------------------------------------------
# Patient-vulnerability triggers.
# ---------------------------------------------------------------------------

# Conditions that make the same illness materially more dangerous.
RISK_CONDITIONS: tuple[tuple[str, str], ...] = (
    (r"pregnan", "you're pregnant"),
    (r"immunocompromis|immunosuppress|immune deficien", "a weakened immune system"),
    (r"\bhiv\b|\baids\b", "a weakened immune system"),
    (r"transplant", "a transplant"),
    (r"chemotherapy|chemo\b|radiation therapy", "cancer treatment"),
    (r"dialysis|kidney failure|renal failure|chronic kidney", "kidney disease"),
    (r"heart failure|cardiomyopathy|coronary|previous heart attack|\bmi\b",
     "an existing heart condition"),
    (r"\bcopd\b|emphysema|pulmonary fibrosis|severe asthma", "a chronic lung condition"),
    (r"cirrhosis|liver failure", "liver disease"),
    (r"lupus|rheumatoid", "an autoimmune condition"),
    (r"diabet", "diabetes"),
    (r"sickle cell", "sickle cell disease"),
    (r"blood thinner|warfarin|anticoagul|apixaban|rivaroxaban", "blood-thinning medication"),
    (r"steroid|prednis", "long-term steroids"),
    (r"cancer|chemo|tumou?r", "a cancer diagnosis"),
)

_RISK_RES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(p, re.IGNORECASE), label) for p, label in RISK_CONDITIONS
)

INFANT_AGE = 2
ELDERLY_AGE = 70


# ---------------------------------------------------------------------------
# JSON cache (optional; built by scripts/grade_diseases.py).
# ---------------------------------------------------------------------------

_cache: dict[str, str] | None = None
_cache_lock = threading.Lock()


def _load_cache() -> dict[str, str]:
    global _cache
    if _cache is not None:
        return _cache
    with _cache_lock:
        if _cache is not None:
            return _cache
        if CACHE_PATH.exists():
            try:
                raw = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
                _cache = {
                    str(k).lower().strip(): str(v).lower().strip()
                    for k, v in raw.items()
                    if str(v).lower().strip() in VALID_TIERS
                }
                log.info(
                    "Loaded %d disease severity entries from %s", len(_cache), CACHE_PATH
                )
            except Exception as e:
                log.warning("Failed to read %s: %s — using heuristics only.", CACHE_PATH, e)
                _cache = {}
        else:
            _cache = {}
    return _cache


# ---------------------------------------------------------------------------
# Public lookups.
# ---------------------------------------------------------------------------

def severity_for(disease: str) -> str:
    """Return "low" | "moderate" | "critical" for a disease name."""
    name = (disease or "").lower().strip()
    if not name:
        return "moderate"

    if name in EXPLICIT_SEVERITY:
        return EXPLICIT_SEVERITY[name]

    cache = _load_cache()
    if name in cache:
        return cache[name]

    for _, pattern in _CRITICAL_RES:
        if pattern.search(name):
            return "critical"
    for _, pattern in _LOW_RES:
        if pattern.search(name):
            return "low"
    return "moderate"


def specialty_for(disease: str) -> str:
    """Best-guess medical specialty for a disease name."""
    name = (disease or "").lower().strip()
    if not name:
        return "internal_medicine"
    for specialty, patterns in _SPECIALTY_RES:
        for pattern in patterns:
            if pattern.search(name):
                return specialty
    return "internal_medicine"


# ---------------------------------------------------------------------------
# Aggregation over RF candidates.
# ---------------------------------------------------------------------------

# Fractions of the *shortlist*, not raw model probabilities — see module docs.
CRITICAL_SHARE = 0.40   # dangerous diseases dominate the differential
CRITICAL_PRESENT = 0.15  # a dangerous disease is a real contender
ATTENTION_SHARE = 0.50   # critical + moderate combined

# Below this raw probability the model is barely above its 1/n_classes floor,
# so the shortlist is noise rather than evidence.
LOW_CONFIDENCE_PROB = 0.02


def _shares(candidates: list[dict[str, Any]]) -> list[tuple[str, float, float]]:
    """(disease, raw_probability, share_of_shortlist) for each candidate."""
    raw = [
        (str(c.get("disease", "")), max(float(c.get("probability", 0.0) or 0.0), 0.0))
        for c in candidates
    ]
    total = sum(p for _, p in raw)
    if total <= 0:
        even = 1.0 / len(raw) if raw else 0.0
        return [(d, p, even) for d, p in raw]
    return [(d, p, p / total) for d, p in raw]


def severity_weights(candidates: list[dict[str, Any]]) -> dict[str, float]:
    """How much of the shortlist sits in each severity tier."""
    weights = {"low": 0.0, "moderate": 0.0, "critical": 0.0}
    for disease, _, share in _shares(candidates):
        weights[severity_for(disease)] += share
    return weights


def leading_candidate(
    candidates: list[dict[str, Any]],
) -> tuple[str, float, float] | None:
    """(disease, probability, share) of the most likely candidate, or None.

    This is the condition the patient is told about, so it is also the one the
    grade has to stay consistent with.
    """
    shares = _shares(candidates)
    if not shares:
        return None
    return max(shares, key=lambda item: item[1])


def aggregate_severity(candidates: list[dict[str, Any]]) -> str:
    """Severity implied by the classifier's shortlist.

    Tips toward the more dangerous tier — clinically we want over-triage, not
    under-triage — but refuses to shout "critical" off a shortlist that is
    statistically indistinguishable from noise.
    """
    if not candidates:
        return "moderate"

    leading = leading_candidate(candidates)
    if leading is None:
        return "moderate"
    top_disease, top_prob, _ = leading

    weights = severity_weights(candidates)
    if weights["critical"] >= CRITICAL_SHARE:
        spread_tier = "critical"
    elif weights["critical"] >= CRITICAL_PRESENT:
        spread_tier = "moderate"
    elif (weights["critical"] + weights["moderate"]) >= ATTENTION_SHARE:
        spread_tier = "moderate"
    else:
        spread_tier = "low"

    # The shortlist as a whole, but never gentler than the condition at the top
    # of it — see "The leading candidate sets a floor" in the module docstring.
    tier = worst(spread_tier, severity_for(top_disease))

    # Noise guard: near the 1/n_classes floor the differential is not evidence
    # of an emergency. Capped here only; the symptom signal is graded
    # separately and is never capped.
    if tier == "critical" and top_prob < LOW_CONFIDENCE_PROB:
        return "moderate"
    return tier


def aggregate_specialty(candidates: list[dict[str, Any]]) -> str:
    """Share-weighted majority vote for the medical specialty.

    A dangerous candidate carries more weight than a harmless one — if the
    shortlist is "tension headache" and "meningitis", the referral should be
    aimed at the one that matters.
    """
    if not candidates:
        return "internal_medicine"
    tier_weight = {"low": 1.0, "moderate": 1.5, "critical": 3.0}
    votes: dict[str, float] = {}
    for disease, _, share in _shares(candidates):
        specialty = specialty_for(disease)
        votes[specialty] = votes.get(specialty, 0.0) + share * tier_weight[severity_for(disease)]
    if not votes:
        return "internal_medicine"
    return max(votes.items(), key=lambda kv: kv[1])[0]


# ---------------------------------------------------------------------------
# Patient-context bump.
# ---------------------------------------------------------------------------

def age_from_dob(dob: date | None) -> int | None:
    if not dob:
        return None
    today = date.today()
    years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return years if 0 <= years <= 130 else None


def risk_factors(user_history: dict | None, age: int | None = None) -> list[str]:
    """Plain-English reasons this patient is more vulnerable than average."""
    found: list[str] = []
    if user_history:
        parts: list[str] = []
        for key in ("conditions", "medications", "allergies"):
            values = user_history.get(key) or []
            if isinstance(values, (list, tuple)):
                parts.extend(str(v) for v in values)
            elif values:
                parts.append(str(values))
        parts.append(str(user_history.get("notes") or ""))
        haystack = " ".join(parts)
        for pattern, label in _RISK_RES:
            if pattern.search(haystack) and label not in found:
                found.append(label)
    if age is not None:
        if age < INFANT_AGE:
            found.append("how young the patient is")
        elif age >= ELDERLY_AGE:
            found.append("age")
    return found


def bump_for_history(
    severity: str, user_history: dict | None, age: int | None = None
) -> tuple[str, bool]:
    """Bump up one tier if the patient's history or age flags elevated risk."""
    severity, factors = apply_vulnerability(severity, user_history, age)
    return severity, bool(factors)


def apply_vulnerability(
    severity: str, user_history: dict | None, age: int | None = None
) -> tuple[str, list[str]]:
    """Raise severity one tier for vulnerable patients.

    Returns (severity, the risk factors that caused the bump). An empty list
    means nothing was found, or the grade was already at the top.
    """
    factors = risk_factors(user_history, age)
    if not factors or severity == "critical":
        return severity, []
    return ("moderate" if severity == "low" else "critical"), factors


# ---------------------------------------------------------------------------
# Public entry point.
# ---------------------------------------------------------------------------

def _join(items: list[str], limit: int = 2) -> str:
    shown = items[:limit]
    if len(shown) == 1:
        return shown[0]
    return f"{', '.join(shown[:-1])} and {shown[-1]}"


def grade_from_candidates(
    candidates: list[dict[str, Any]],
    user_history: dict | None,
    symptom_count: int,
    symptoms: list[str] | None = None,
    text: str = "",
    age: int | None = None,
) -> dict[str, Any]:
    """Compute {severity, specialty, reasoning} for a triage turn.

    ``symptoms`` are the canonical symptoms accumulated across the
    conversation and ``text`` is what the patient actually wrote — together
    they let a clear-cut emergency outrank a hesitant classifier.
    """
    flags = clinical_flags.assess(symptoms, text)

    if not candidates:
        severity = worst("low", flags.tier)
        severity, factors = apply_vulnerability(severity, user_history, age)
        pieces: list[str] = []
        if flags.reasons:
            pieces.append(clinical_flags.describe(flags))
        else:
            severity = worst(severity, "moderate")
            pieces.append(
                "There isn't enough detail yet to narrow this down, so it's being "
                "treated cautiously."
            )
        if factors:
            pieces.append(f"Weighted up because of {_join(factors)}.")
        return {
            "severity": severity,
            "specialty": "internal_medicine",
            "reasoning": " ".join(pieces),
            "severity_sources": {
                "diseases": "low",
                "symptoms": flags.tier,
                "pain": flags.pain,
                "risk_factors": factors,
            },
        }

    disease_tier = aggregate_severity(candidates)
    specialty = aggregate_specialty(candidates)
    combined = worst(disease_tier, flags.tier)
    severity, factors = apply_vulnerability(combined, user_history, age)

    top_disease, top_prob, top_share = leading_candidate(candidates)  # type: ignore[misc]
    lead_tier = severity_for(top_disease)
    pieces = [
        f"Based on {symptom_count} symptom(s) you've described across this conversation."
    ]
    if top_prob < LOW_CONFIDENCE_PROB:
        pieces.append(
            f"Nothing stands out clearly yet — {top_disease} is the nearest fit, "
            f"but more detail would sharpen this."
        )
    elif top_share >= 0.35:
        pieces.append(
            f"The closest match is {top_disease} ({top_share:.0%} of the shortlist)."
        )
    else:
        pieces.append(f"Several conditions fit similarly well, {top_disease} among them.")
    # Say out loud why a named condition rules out a "self-care" grade, so the
    # badge and the written reply can't read as contradicting each other. Only
    # when the leader is believable — a noise-level leader is capped anyway.
    if top_prob >= LOW_CONFIDENCE_PROB and rank(lead_tier) >= rank(flags.tier):
        if lead_tier == "critical":
            pieces.append(
                f"{top_disease.capitalize()} needs ruling out in person, so this "
                f"isn't being graded any lower."
            )
        elif lead_tier == "moderate":
            pieces.append(
                f"{top_disease.capitalize()} isn't something to manage alone, so "
                f"this is graded at least moderate."
            )
    if flags.reasons and rank(flags.tier) >= rank(disease_tier):
        pieces.append(clinical_flags.describe(flags))
    if factors:
        pieces.append(f"Graded one step higher because of {_join(factors)}.")

    return {
        "severity": severity,
        "specialty": specialty,
        "reasoning": " ".join(pieces),
        "severity_sources": {
            "diseases": disease_tier,
            "leading_disease": top_disease,
            "leading_disease_tier": lead_tier,
            "symptoms": flags.tier,
            "pain": flags.pain,
            "risk_factors": factors,
        },
    }


def escalate_grade(
    triage: dict[str, Any],
    symptoms: list[str] | None = None,
    text: str = "",
    user_history: dict | None = None,
    age: int | None = None,
) -> dict[str, Any]:
    """Raise an externally-produced grade (e.g. MedGemma's) to meet the floor
    set by the patient's own symptoms and risk factors.

    Used when the classifier returned nothing and the LLM graded the turn on
    its own — the language model is allowed to be more worried than the
    symptom rules, never less.
    """
    flags = clinical_flags.assess(symptoms, text)
    severity = worst(str(triage.get("severity", "moderate")), flags.tier)
    severity, factors = apply_vulnerability(severity, user_history, age)

    reasoning = str(triage.get("reasoning", "")).strip()
    extra = clinical_flags.describe(flags)
    if extra and rank(flags.tier) >= rank(str(triage.get("severity", "low"))):
        reasoning = f"{reasoning} {extra}".strip()
    if factors:
        reasoning = f"{reasoning} Graded one step higher because of {_join(factors)}.".strip()

    return {
        **triage,
        "severity": severity,
        "reasoning": reasoning,
        "severity_sources": {
            "diseases": str(triage.get("severity", "moderate")),
            "symptoms": flags.tier,
            "pain": flags.pain,
            "risk_factors": factors,
        },
    }
