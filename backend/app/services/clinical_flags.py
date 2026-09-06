"""
Symptom-level ("human pain") triage layer.

Why this exists
---------------
``disease_severity`` grades how dangerous the *classifier's candidate
diseases* are. That misses the other half of real triage: how bad the
*patient* actually is right now. A 754-class RF spreads its probability mass
so thinly that a genuine emergency can come back as three low-confidence
guesses, while the patient is plainly describing crushing chest pain.

This module reads what the person said — the canonical symptoms extracted
across the conversation plus their raw words — and produces an independent
severity floor:

  * ``EMERGENCY_SYMPTOMS``  — one is enough to mean "go now" (coughing up
    blood, a seizure, one-sided weakness, slurred speech).
  * ``URGENT_SYMPTOMS``     — one is enough to mean "get seen soon".
  * ``COMBO_RULES``         — patterns that are only dangerous together
    (chest pain *with* sweating; headache *with* stiff neck *and* fever).
  * ``EMERGENCY_PHRASES``   — how people actually phrase emergencies in free
    text ("I can't breathe", "worst headache of my life", "I want to die").
  * ``pain_score``          — the SOCRATES 0-10 severity answer, or the words
    people use instead ("unbearable", "a bit sore").

The result is combined with the disease-derived tier by taking the *worse*
of the two — see ``disease_severity.grade_from_candidates``.

Symptom names here must match the RF model's canonical feature vocabulary
(``rf.get_predictor().feature_names``), which is lowercase with spaces.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Tier ordering shared with disease_severity.
TIERS = ("low", "moderate", "critical")
_RANK = {t: i for i, t in enumerate(TIERS)}


def rank(severity: str) -> int:
    return _RANK.get((severity or "").lower().strip(), 1)


def worst(*severities: str) -> str:
    """Return the most dangerous of the given tiers."""
    return TIERS[max((rank(s) for s in severities), default=1)]


# ---------------------------------------------------------------------------
# Single symptoms that carry their own weight.
# Value = the plain-English reason shown back to the patient.
# ---------------------------------------------------------------------------

EMERGENCY_SYMPTOMS: dict[str, str] = {
    # Chest *pain* is the canonical don't-under-triage symptom: it is usually
    # nothing, and the times it isn't, hours matter. Chest *tightness* on its
    # own is left in the urgent tier — it is far more often anxiety or asthma.
    "sharp chest pain": "chest pain",
    "burning chest pain": "chest pain",
    "seizures": "a seizure",
    "vomiting blood": "vomiting blood",
    "melena": "black or tarry stools (a sign of internal bleeding)",
    "hemoptysis": "coughing up blood",
    "difficulty breathing": "difficulty breathing",
    "apnea": "pauses in breathing",
    "throat swelling": "swelling in the throat",
    "throat feels tight": "a tightening throat",
    "focal weakness": "weakness affecting one part or one side of the body",
    "difficulty speaking": "difficulty speaking",
    "slurring words": "slurred speech",
    "blindness": "loss of vision",
    "pupils unequal": "unequal pupils",
}

URGENT_SYMPTOMS: dict[str, str] = {
    "chest tightness": "chest tightness",
    "hurts to breath": "pain when breathing",
    "shortness of breath": "shortness of breath",
    "breathing fast": "rapid breathing",
    "irregular heartbeat": "an irregular heartbeat",
    "decreased heart rate": "an unusually slow heart rate",
    "fainting": "fainting",
    "delusions or hallucinations": "hallucinations or delusions",
    "blood in stool": "blood in the stool",
    "rectal bleeding": "rectal bleeding",
    "blood in urine": "blood in the urine",
    "vomiting blood": "vomiting blood",
    "jaundice": "yellowing of the skin or eyes",
    "low urine output": "passing very little urine",
    "neck stiffness or tightness": "a stiff neck",
    "difficulty in swallowing": "difficulty swallowing",
    "loss of sensation": "loss of sensation",
    "recent weight loss": "unexplained weight loss",
    "swollen lymph nodes": "swollen lymph nodes",
    "problems with movement": "trouble moving normally",
    "spotting or bleeding during pregnancy": "bleeding during pregnancy",
    "pain during pregnancy": "pain during pregnancy",
    "problems during pregnancy": "a problem during pregnancy",
    "double vision": "double vision",
    "diminished vision": "reduced vision",
    "difficulty eating": "difficulty eating",
    "infant feeding problem": "an infant feeding problem",
}

# Symptom groups reused by the combination rules below.
_CHEST_PAIN = (
    "sharp chest pain", "burning chest pain", "chest tightness",
    "hurts to breath", "rib pain",
)
_CARDIAC_COMPANIONS = (
    "shortness of breath", "difficulty breathing", "sweating", "palpitations",
    "increased heart rate", "irregular heartbeat", "nausea", "vomiting",
    "dizziness", "fainting", "arm pain", "jaw pain", "shoulder pain", "pallor",
)
_HEADACHE = ("headache", "frontal headache")
_FEVERISH = ("fever", "chills", "feeling hot", "feeling hot and cold", "flu-like syndrome")
_ABDO_PAIN = (
    "sharp abdominal pain", "lower abdominal pain", "upper abdominal pain",
    "burning abdominal pain", "side pain", "suprapubic pain",
    "abdominal pain",  # generic, contributed by PHRASE_SYMPTOMS
)
_SHOCK_SIGNS = (
    "increased heart rate", "breathing fast", "low urine output", "dizziness",
    "pallor", "fainting", "sweating", "feeling ill", "weakness",
)
_AIRWAY = (
    "throat swelling", "throat feels tight", "swollen tongue", "lip swelling",
    "difficulty breathing", "wheezing", "shortness of breath",
)


@dataclass(frozen=True)
class ComboRule:
    """Fires when EVERY group has at least one symptom present."""

    label: str
    tier: str
    groups: tuple[tuple[str, ...], ...]


COMBO_RULES: tuple[ComboRule, ...] = (
    ComboRule(
        "chest pain together with symptoms that can point to the heart",
        "critical",
        (_CHEST_PAIN, _CARDIAC_COMPANIONS),
    ),
    ComboRule(
        "an allergic reaction affecting the airway",
        "critical",
        (("allergic reaction", "skin rash", "itching of skin"), _AIRWAY),
    ),
    ComboRule(
        "headache with a stiff neck and fever",
        "critical",
        (_HEADACHE, ("neck stiffness or tightness", "neck pain"), _FEVERISH),
    ),
    ComboRule(
        "fever alongside signs the body is struggling to cope",
        "critical",
        (_FEVERISH, _SHOCK_SIGNS, ("confusion", "feeling ill", "sleepiness", "weakness", "low urine output")),
    ),
    ComboRule(
        "severe abdominal pain with fever and vomiting",
        "critical",
        (_ABDO_PAIN, _FEVERISH, ("vomiting", "nausea", "swollen abdomen", "constipation")),
    ),
    ComboRule(
        "abdominal pain during pregnancy",
        "critical",
        (_ABDO_PAIN + ("pelvic pain",),
         ("recent pregnancy", "pain during pregnancy", "problems during pregnancy",
          "spotting or bleeding during pregnancy", "uterine contractions")),
    ),
    ComboRule(
        "sudden testicular pain with nausea",
        "critical",
        (("pain in testicles", "swelling of scrotum"), ("nausea", "vomiting", "sharp abdominal pain")),
    ),
    ComboRule(
        "eye pain together with changed vision",
        "critical",
        (("pain in eye", "eye redness"), ("diminished vision", "blindness", "spots or clouds in vision", "double vision")),
    ),
    ComboRule(
        "excessive thirst and urination with vomiting",
        "critical",
        (("polyuria", "frequent urination", "excessive urination at night"),
         ("thirst",), ("vomiting", "nausea", "breathing fast", "weakness", "sleepiness")),
    ),
    ComboRule(
        "abdominal pain with vomiting",
        "moderate",
        (_ABDO_PAIN, ("vomiting", "nausea", "diarrhea")),
    ),
    ComboRule(
        "a persistent cough with fever",
        "moderate",
        (("cough", "coughing up sputum", "congestion in chest"), _FEVERISH),
    ),
    ComboRule(
        "a headache with vision changes",
        "moderate",
        (_HEADACHE, ("spots or clouds in vision", "diminished vision", "double vision", "pain in eye")),
    ),
)


# ---------------------------------------------------------------------------
# Free-text patterns. People rarely use clinical vocabulary — these catch the
# words they do use, including phrasings the symptom extractor can't map onto
# the RF vocabulary at all (self-harm, collapse, uncontrolled bleeding).
# ---------------------------------------------------------------------------

EMERGENCY_PHRASES: tuple[tuple[str, str], ...] = (
    (r"can'?t breathe|cannot breathe|unable to breathe|struggling (?:to|for) breathe?|gasping for air",
     "you said you can't breathe"),
    (r"crushing (?:chest )?(?:pain|pressure)|(?:chest|pain) feels? like (?:an? )?(?:elephant|weight|vice|band)",
     "you described crushing chest pain"),
    (r"chest pain[^.]{0,40}(?:radiat|spread|shoot|travel)[^.]{0,30}(?:arm|jaw|shoulder|neck|back)",
     "chest pain spreading to your arm, jaw or back"),
    (r"worst (?:headache|pain)[^.]{0,25}(?:of my life|i'?ve ever|ever had)|thunderclap",
     "you called it the worst pain of your life"),
    (r"kill myself|killing myself|end my life|ending my life|take my own life|want to die|"
     r"don'?t want to (?:live|be here)|no reason to live|suicid|harm myself|hurt myself|self[- ]harm",
     "you mentioned thoughts of harming yourself"),
    (r"cough(?:ing)? up blood|vomit(?:ing|ed)? blood|blood in (?:my )?vomit|throwing up blood|"
     r"spitting up blood|blood when i cough",
     "you mentioned bringing up blood"),
    (r"passed out|blacked out|black(?:ed)? out|unconscious|unresponsive|collapsed|won'?t wake|not waking",
     "you mentioned losing consciousness"),
    (r"(?:lips|face|fingers|nails)[^.]{0,15}(?:turning )?blue|turning blue|going blue",
     "you mentioned a blue colour to the lips or skin"),
    (r"face (?:is )?droop|one side of (?:my|his|her|their) (?:face|body|mouth)[^.]{0,20}(?:droop|numb|weak|dead)|"
     r"slurred speech|can'?t (?:move|feel) (?:my|his|her|their) (?:arm|leg|face|side|hand)",
     "you described one-sided weakness or slurred speech — possible stroke signs"),
    (r"(?:won'?t|will not|can'?t|cannot) stop bleeding|bleeding heavily|gushing blood|"
     r"soaked? through|losing a lot of blood",
     "you described bleeding that won't stop"),
    (r"seizure|convulsion|fitting|fits?\b(?= *(?:again|today|last))|shaking uncontrollably",
     "you mentioned a seizure"),
    (r"throat (?:is )?clos|swollen (?:throat|tongue)|tongue (?:is )?swell|anaphyla|epipen",
     "you described your throat closing up"),
    (r"overdos|took (?:too many|a (?:bunch|handful|load) of|all (?:my|the)) (?:pills|tablets|medication)|"
     r"swallowed (?:bleach|poison|chemicals)",
     "you mentioned an overdose or poisoning"),
    (r"stiff neck[^.]{0,40}(?:fever|light hurts|bright light)|"
     r"(?:fever|temperature)[^.]{0,40}stiff neck",
     "a stiff neck with fever"),
    (r"rash (?:that )?(?:doesn'?t|does not|won'?t) fade|glass test",
     "a rash that doesn't fade under pressure"),
    (r"severe (?:allergic )?reaction|hives all over|swelling all over",
     "a severe allergic reaction"),
)

URGENT_PHRASES: tuple[tuple[str, str], ...] = (
    (r"high fever|fever (?:of|over|above) (?:10[2-9]|3[89]|4[01])|temperature (?:of|over) (?:10[2-9]|3[89]|4[01])",
     "a high fever"),
    (r"fever for (?:\d+|several|many|a few) (?:days|weeks)|fever (?:that )?(?:won'?t|hasn'?t) (?:go|gone)",
     "a fever that isn't settling"),
    (r"getting (?:much |a lot )?worse|worsening|worse (?:every|each) day|keeps getting worse",
     "symptoms that are getting worse"),
    (r"for (?:\d+ )?(?:weeks|months)|(?:weeks|months) now|hasn'?t gone away|won'?t go away|"
     r"(?:still|keeps) (?:there|coming back)",
     "symptoms lasting a long time"),
    (r"los(?:ing|t) weight without|los(?:ing|t) weight for no|unexplained weight loss",
     "unexplained weight loss"),
    (r"(?:a |new )?lump|swelling that (?:isn'?t|is not|won'?t)",
     "a lump or swelling"),
    (r"pregnan(?:t|cy)", "that you're pregnant"),
    (r"can'?t (?:keep|hold) (?:anything|food|water|fluids) down|haven'?t eaten (?:in|for)",
     "not being able to keep food or fluids down"),
    (r"can'?t sleep|not sleeping|haven'?t slept", "not being able to sleep"),
    (r"(?:can'?t|cannot|hard to) (?:walk|stand|work|move)|stopping me (?:from )?(?:working|sleeping)",
     "pain that's stopping you doing normal things"),
)

# ---------------------------------------------------------------------------
# Everyday phrasing → canonical symptom.
#
# The symptom extractor only matches the RF's own vocabulary, so "my neck is
# stiff" never becomes "neck stiffness or tightness" and the meningitis
# combination silently fails to fire. These patterns feed the combination
# rules above with the words people actually use.
# ---------------------------------------------------------------------------

PHRASE_SYMPTOMS: tuple[tuple[str, str], ...] = (
    (r"stiff neck|neck (?:is|feels|has been|was) (?:really |very |so )?stiff|neck stiffness|"
     r"(?:can'?t|cannot|hard to) (?:turn|move) my neck",
     "neck stiffness or tightness"),
    (r"chest (?:pain|hurts?|ache|aching)|pain in (?:my|the) chest", "sharp chest pain"),
    (r"chest (?:pressure|tightness|tight)|tightness in (?:my|the) chest|"
     r"weight on (?:my|the) chest",
     "chest tightness"),
    (r"(?:can'?t|cannot|struggling to) catch my breath|out of breath|short(?:ness)? of breath|"
     r"breathless|winded|puffed out|hard to breathe|difficulty breathing",
     "shortness of breath"),
    (r"throw(?:ing|n)? up|threw up|vomit|puk(?:e|ed|ing)|being sick|been sick",
     "vomiting"),
    (r"feel(?:ing)? sick|nauseous|nausea|queasy", "nausea"),
    (r"fever|temperature|feverish|burning up|hot and cold|shivering|chills",
     "fever"),
    (r"headache|head (?:is )?(?:hurt|pound|throb)|migraine", "headache"),
    (r"sweat(?:ing|y)|clammy|drenched", "sweating"),
    (r"dizzy|dizziness|light[- ]?headed|room (?:is )?spinning|vertigo", "dizziness"),
    (r"(?:stomach|tummy|belly|abdominal|abdomen|gut)[^.]{0,12}(?:pain|ache|hurt|cramp)|"
     r"pain in (?:my|the) (?:stomach|tummy|belly|abdomen|side)|stomachache|bellyache",
     "abdominal pain"),
    (r"diarrh|loose (?:motions|stools)|the runs", "diarrhea"),
    (r"cough", "cough"),
    (r"wheez", "wheezing"),
    (r"heart (?:is )?(?:racing|pounding|fluttering)|palpitation|skipped? a beat",
     "palpitations"),
    (r"passed out|fainted|blacked out|nearly fainted", "fainting"),
    (r"blood in (?:my |the )?(?:stool|poo|poop|faeces|feces)|bloody stool",
     "blood in stool"),
    (r"blood in (?:my |the )?(?:urine|pee|wee)|peeing blood|bloody urine",
     "blood in urine"),
    (r"rash|hives|spots on my skin", "skin rash"),
    (r"pregnan(?:t|cy)|expecting a baby", "recent pregnancy"),
    (r"allergic|allergy|epipen|reaction to", "allergic reaction"),
    (r"weak(?:ness)? (?:in|down) (?:my|one) (?:arm|leg|side)|one side (?:of my body )?(?:is )?weak",
     "focal weakness"),
    (r"jaundice|yellow(?:ing)? (?:skin|eyes)|skin (?:has )?turn(?:ed|ing) yellow", "jaundice"),
    (r"swollen (?:glands|lymph nodes)", "swollen lymph nodes"),
    (r"(?:can'?t|cannot|hard to|painful to) swallow|trouble swallowing",
     "difficulty in swallowing"),
    (r"seeing double|double vision", "double vision"),
    (r"blurred vision|vision (?:is )?(?:blurry|blurred|going)|can'?t see (?:properly|clearly)",
     "diminished vision"),
    (r"(?:eye|eyes) (?:hurt|ache|painful)|pain in my eye", "pain in eye"),
    (r"very sleepy|so sleepy|hard to (?:wake|rouse)|drowsy|lethargic|won'?t wake",
     "sleepiness"),
    (r"not feeding|won'?t feed|refusing (?:milk|food|to feed)", "infant feeding problem"),
    (r"(?:barely|hardly|not) (?:peeing|passing urine)|no wet nappies|haven'?t (?:peed|urinated)",
     "low urine output"),
    (r"burn(?:s|ing)? when i (?:pee|wee|urinate)|burning (?:pee|wee|urination)|"
     r"sting(?:s|ing)? when i (?:pee|wee)|hurts to (?:pee|wee|urinate)|painful (?:pee|wee)",
     "painful urination"),
    (r"(?:pee|wee|urinat)\w*[^.]{0,15}(?:all the time|constantly|so often|every \w+ minutes)|"
     r"need to (?:pee|wee|go)[^.]{0,15}(?:all the time|constantly|often)|going (?:to the (?:toilet|loo)|for a pee) a lot",
     "frequent urination"),
    (r"runny nose|nose (?:is |keeps )?running|dripping nose|snotty", "coryza"),
    (r"blocked nose|stuffy nose|bunged up|congested|nasal congestion", "nasal congestion"),
    (r"sore throat|throat (?:is |feels )?(?:sore|raw|scratchy)|throat hurts", "sore throat"),
    (r"ear ?ache|ear (?:is |feels )?(?:sore|painful)|(?:my|the) ear hurts", "ear pain"),
    (r"tooth ?ache|tooth hurts|(?:my|the) teeth hurt", "toothache"),
    (r"can'?t sleep|not sleeping|haven'?t slept|insomnia|awake all night", "insomnia"),
    (r"no appetite|not hungry|lost my appetite|can'?t face food|off my food",
     "decreased appetite"),
    (r"lost weight|losing weight|dropped a lot of weight", "recent weight loss"),
    (r"exhausted|no energy|so tired|shattered|wiped out|fatigued", "fatigue"),
    (r"back (?:pain|hurts?|ache)|(?:my|the) back is (?:killing|sore)", "back pain"),
    (r"joints? (?:hurt|ache|are sore|are painful)|aching joints", "joint pain"),
    (r"constipated|can'?t (?:poo|go to the toilet)|haven'?t (?:pooed|been) (?:in|for)",
     "constipation"),
    (r"heart ?burn|acid reflux|burning in my chest after eating", "heartburn"),
    (r"night sweats|sweating (?:at night|through the night)", "sweating"),
)

_PHRASE_SYMPTOM_RES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(p), s) for p, s in PHRASE_SYMPTOMS
)


# Negation cues — looked for in the ~40 characters before a match so that
# "no chest pain" and "denies any bleeding" don't escalate anybody.
_NEGATION_RE = re.compile(
    r"\b(?:no|not|never|without|denies|denied|deny|isn'?t|aren'?t|wasn'?t|don'?t|doesn'?t|didn'?t|"
    r"free of|negative for|any)\b[^.!?;]{0,20}$"
)

_NEGATION_WINDOW = 40


def _negated(text: str, start: int) -> bool:
    return bool(_NEGATION_RE.search(text[max(0, start - _NEGATION_WINDOW):start]))


# ---------------------------------------------------------------------------
# Pain intensity.
# ---------------------------------------------------------------------------

# "8/10", "8 out of 10", "severity: 8", "rated it 9"
_NUMERIC_PAIN_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(\d{1,2})\s*(?:/|out of|outta|on a scale of|on)\s*(?:10|ten)\b"),
    re.compile(r"\bseverity\b[^\n:]{0,20}[:\-]\s*(?:about\s*|around\s*)?(\d{1,2})\b"),
    re.compile(r"\b(?:pain|it)\s+(?:is|was|'s)\s+(?:about\s+|around\s+)?(?:a\s+)?(\d{1,2})\b"),
    re.compile(r"\brate(?:d)?\s+(?:it\s+)?(?:a\s+)?(\d{1,2})\b"),
)

# Words people use instead of a number, mapped onto the same 0-10 scale.
_QUALITATIVE_PAIN: tuple[tuple[str, int], ...] = (
    (r"unbearable|excruciating|agonis|agoniz|blinding|worst pain|can'?t take it|"
     r"want to scream|screaming|10 out of 10|beyond words", 10),
    (r"severe|intense|extreme|terrible|awful|horrible|really bad|very bad|"
     r"crippling|debilitating|so much pain", 8),
    (r"bad pain|quite painful|really hurts|pretty bad|strong pain", 6),
    (r"moderate|uncomfortable|annoying|noticeable|sore", 5),
    (r"mild|slight|a (?:little|bit)|minor|barely|hardly|not (?:too |that )?bad|manageable|dull ache", 2),
)


def pain_score(text: str) -> int | None:
    """Best estimate of the patient's own 0-10 pain rating, or None.

    A number the patient gave (including the SOCRATES severity answer) always
    beats descriptive words. Returns the *highest* number found, because
    people often quote both a baseline and a peak ("usually 4, but it hit 9").
    """
    if not text:
        return None
    low = text.lower()

    numbers: list[int] = []
    for pattern in _NUMERIC_PAIN_RES:
        for m in pattern.finditer(low):
            try:
                value = int(m.group(1))
            except (TypeError, ValueError):
                continue
            if 0 <= value <= 10:
                numbers.append(value)
    if numbers:
        return max(numbers)

    for pattern, value in _QUALITATIVE_PAIN:
        m = re.search(pattern, low)
        if m and not _negated(low, m.start()):
            return value
    return None


# Pain that maps to each tier on its own.
PAIN_CRITICAL = 9  # "the worst I've ever felt" — needs looking at now
PAIN_URGENT = 6    # interferes with normal life
PAIN_REASSURING = 3  # allows a "low" grade to stand


# ---------------------------------------------------------------------------
# Assessment.
# ---------------------------------------------------------------------------


@dataclass
class FlagResult:
    tier: str = "low"
    reasons: list[str] = field(default_factory=list)
    pain: int | None = None

    @property
    def is_emergency(self) -> bool:
        return self.tier == "critical"


def symptoms_from_text(text: str) -> set[str]:
    """Canonical symptoms implied by everyday phrasing, skipping negated ones."""
    low = (text or "").lower()
    found: set[str] = set()
    for pattern, symptom in _PHRASE_SYMPTOM_RES:
        for m in pattern.finditer(low):
            if not _negated(low, m.start()):
                found.add(symptom)
                break
    return found


def _present(symptoms: set[str], group: tuple[str, ...]) -> str | None:
    for s in group:
        if s in symptoms:
            return s
    return None


def assess(symptoms: list[str] | None, text: str = "") -> FlagResult:
    """Grade the patient's own presentation, independent of the classifier.

    ``symptoms`` are canonical RF feature names accumulated across the
    conversation; ``text`` is what the patient actually wrote (current message
    plus earlier turns and any SOCRATES intake summary).
    """
    present = {(s or "").lower().strip() for s in (symptoms or []) if s}
    low_text = (text or "").lower()
    present |= symptoms_from_text(low_text)

    tier = "low"
    reasons: list[str] = []

    def escalate(new_tier: str, reason: str) -> None:
        nonlocal tier
        tier = worst(tier, new_tier)
        if reason and reason not in reasons:
            reasons.append(reason)

    # 1. Single symptoms that speak for themselves.
    for symptom, reason in EMERGENCY_SYMPTOMS.items():
        if symptom in present:
            escalate("critical", reason)
    for symptom, reason in URGENT_SYMPTOMS.items():
        if symptom in present:
            escalate("moderate", reason)

    # 2. Combinations that are only dangerous together.
    for rule in COMBO_RULES:
        if all(_present(present, group) for group in rule.groups):
            escalate(rule.tier, rule.label)

    # 3. The patient's own words.
    for pattern, reason in EMERGENCY_PHRASES:
        m = re.search(pattern, low_text)
        if m and not _negated(low_text, m.start()):
            escalate("critical", reason)
    for pattern, reason in URGENT_PHRASES:
        m = re.search(pattern, low_text)
        if m and not _negated(low_text, m.start()):
            escalate("moderate", reason)

    # 4. How much it hurts. Severe pain is a triage signal in its own right,
    #    and severe pain on top of an already-urgent picture is an emergency.
    pain = pain_score(low_text)
    if pain is not None:
        if pain >= PAIN_CRITICAL:
            escalate("critical", f"pain you rated {pain}/10")
        elif pain >= PAIN_URGENT:
            # Test the picture as it stood *before* this rule ran. Reading
            # ``tier`` after the escalation below made the check trivially
            # true, so any 6/10 stomach ache came out "critical".
            already_urgent = rank(tier) >= _RANK["moderate"]
            escalate("moderate", f"pain you rated {pain}/10")
            if already_urgent and _present(present, _CHEST_PAIN + _ABDO_PAIN + _HEADACHE):
                escalate("critical", f"severe pain ({pain}/10) in an area that needs ruling out")

    return FlagResult(tier=tier, reasons=reasons, pain=pain)


def describe(result: FlagResult, limit: int = 3) -> str:
    """One plain-English sentence explaining the escalation, or ''."""
    if not result.reasons:
        return ""
    shown = result.reasons[:limit]
    if len(shown) == 1:
        listed = shown[0]
    elif len(shown) == 2:
        listed = f"{shown[0]} and {shown[1]}"
    else:
        listed = f"{', '.join(shown[:-1])}, and {shown[-1]}"
    lead = "This was treated as urgent because of" if result.is_emergency else "Weighed up alongside"
    return f"{lead} {listed}."
