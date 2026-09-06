"""
Seed the Chroma vector store (LangChain) with a built-in disease KB so the
RAG path has grounding content out of the box.

  python -m scripts.seed_kb            # idempotent, skips if already populated
  python -m scripts.seed_kb --force    # wipe and reseed
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.vectorstore import (  # noqa: E402
    add_documents,
    collection_count,
    reset_collection,
)

CORPUS: list[tuple[str, str, str]] = [
    ("Common cold", "overview",
     "The common cold is a mild viral upper respiratory infection caused most often by rhinoviruses. "
     "It typically resolves in 7–10 days without specific treatment."),
    ("Common cold", "symptoms",
     "Runny or stuffy nose, sore throat, sneezing, cough, mild fever (more common in children), "
     "headache, body aches, fatigue."),
    ("Common cold", "when_to_seek_care",
     "Seek care if symptoms persist beyond 10 days, fever exceeds 38.9 C, breathing difficulty, "
     "severe sinus pain, or sore throat with rash."),

    ("Influenza", "overview",
     "Influenza ('the flu') is a contagious respiratory illness caused by influenza A or B viruses. "
     "Onset is typically abrupt and symptoms are more intense than a cold."),
    ("Influenza", "symptoms",
     "High fever, chills, severe body aches, headache, dry cough, sore throat, marked fatigue, "
     "sometimes nausea or vomiting (more often in children)."),
    ("Influenza", "when_to_seek_care",
     "Urgent care for difficulty breathing, persistent chest pain, confusion, severe dehydration, "
     "or fever above 39.4 C that does not respond to medication. Antivirals are most effective within 48 hours."),

    ("COVID-19", "overview",
     "COVID-19 is caused by SARS-CoV-2. Severity ranges from asymptomatic to life-threatening pneumonia."),
    ("COVID-19", "symptoms",
     "Fever, cough, fatigue, sore throat, congestion, headache, body aches, loss of taste or smell, "
     "shortness of breath."),
    ("COVID-19", "when_to_seek_care",
     "Emergency signs: difficulty breathing, persistent chest pain or pressure, new confusion, "
     "inability to wake, or pale/grey/blue lips or face."),

    ("Strep throat", "overview",
     "Streptococcal pharyngitis is a bacterial throat infection caused by group A Streptococcus, "
     "treatable with antibiotics. Confirmed by rapid antigen test or throat culture."),
    ("Strep throat", "symptoms",
     "Sudden severe sore throat, painful swallowing, fever, tender anterior cervical lymph nodes, "
     "tonsillar exudates, sometimes a fine red rash. Cough is usually absent."),
    ("Strep throat", "when_to_seek_care",
     "See a clinician for testing whenever sore throat is accompanied by fever and absent cough, "
     "especially in children. Untreated cases risk rheumatic fever."),

    ("Migraine", "overview",
     "Migraine is a recurrent primary headache disorder, often unilateral and pulsating, frequently "
     "accompanied by nausea, photophobia, and phonophobia."),
    ("Migraine", "symptoms",
     "Throbbing headache (often one-sided), nausea or vomiting, sensitivity to light and sound, "
     "visual aura, worsening with activity."),
    ("Migraine", "when_to_seek_care",
     "Sudden 'thunderclap' headache, headache with fever and neck stiffness, neurological deficits, "
     "or headache after head trauma require emergency evaluation."),

    ("Tension headache", "overview",
     "Tension-type headache is the most common primary headache, often described as a bilateral pressure "
     "or band-like tightening, usually mild to moderate intensity."),
    ("Tension headache", "symptoms",
     "Bilateral dull aching pain, pressure or tightness around the head, mild scalp/neck tenderness, "
     "no nausea, not aggravated by routine activity."),
    ("Tension headache", "when_to_seek_care",
     "If headaches are frequent (>15 days/month) or progressively worsening, see a clinician. "
     "Sudden severe headache warrants emergency evaluation."),

    ("Type 2 diabetes mellitus", "overview",
     "A chronic metabolic disorder of impaired insulin sensitivity and progressive beta-cell dysfunction "
     "leading to hyperglycemia."),
    ("Type 2 diabetes mellitus", "symptoms",
     "Polyuria, polydipsia, unintentional weight loss, fatigue, blurred vision, recurrent infections, "
     "slow-healing wounds, tingling in feet."),
    ("Type 2 diabetes mellitus", "when_to_seek_care",
     "Routine screening if overweight or family history. Emergency care for very high blood glucose "
     "with confusion, fruity breath odor, rapid breathing, or vomiting (possible DKA / HHS)."),

    ("Hypertension", "overview",
     "Persistently elevated arterial blood pressure (>=130/80 mmHg). Usually asymptomatic until end-organ "
     "damage develops."),
    ("Hypertension", "symptoms",
     "Often silent. When very high: headache, blurred vision, nosebleeds, chest discomfort, shortness of breath."),
    ("Hypertension", "when_to_seek_care",
     "Blood pressure >=180/120 mmHg with symptoms (chest pain, vision change, weakness, severe headache) is "
     "a hypertensive emergency — go to ER."),

    ("Asthma", "overview",
     "Chronic inflammatory airway disease causing variable airflow obstruction, often triggered by allergens, "
     "exercise, cold air, or respiratory infections."),
    ("Asthma", "symptoms",
     "Wheezing, shortness of breath, chest tightness, cough (often worse at night), exacerbations triggered by exposure."),
    ("Asthma", "when_to_seek_care",
     "Severe attack signs: inability to speak in full sentences, blue lips, reliever inhaler ineffective — call emergency services."),

    ("Gastroenteritis", "overview",
     "Inflammation of the stomach and intestines, usually viral but sometimes bacterial. "
     "Self-limited in most adults but dehydration is the main risk."),
    ("Gastroenteritis", "symptoms",
     "Diarrhea, nausea, vomiting, abdominal cramps, low-grade fever, mild dehydration."),
    ("Gastroenteritis", "when_to_seek_care",
     "Bloody stools, high fever, signs of severe dehydration, or symptoms beyond 3 days warrant medical evaluation."),

    ("Urinary tract infection", "overview",
     "Infection of the lower urinary tract, most often by E. coli. More common in women."),
    ("Urinary tract infection", "symptoms",
     "Burning urination, frequency, urgency, suprapubic discomfort, cloudy or foul-smelling urine, mild low-grade fever."),
    ("Urinary tract infection", "when_to_seek_care",
     "Flank pain, fever >38 C, nausea/vomiting, or blood in urine may indicate pyelonephritis and need prompt antibiotic treatment."),

    ("Acute appendicitis", "overview",
     "Inflammation of the vermiform appendix, typically presenting with progressive right lower quadrant pain. "
     "A surgical emergency."),
    ("Acute appendicitis", "symptoms",
     "Initially periumbilical pain migrating to the right lower quadrant, anorexia, nausea, low-grade fever, "
     "tenderness at McBurney's point, rebound tenderness."),
    ("Acute appendicitis", "when_to_seek_care",
     "Suspected appendicitis requires immediate emergency department evaluation; delay risks perforation and peritonitis."),

    ("Myocardial infarction", "overview",
     "A heart attack: blockage of coronary blood flow causing ischemia and necrosis of myocardial tissue."),
    ("Myocardial infarction", "symptoms",
     "Crushing or pressure-like substernal chest pain radiating to left arm, jaw, or back; shortness of breath; sweating; nausea; "
     "lightheadedness. Women, elderly, and diabetics may present atypically."),
    ("Myocardial infarction", "when_to_seek_care",
     "Call emergency services immediately for any chest pain lasting >10 minutes or accompanied by sweating, nausea, or breathlessness. "
     "Chew aspirin if not contraindicated."),

    ("Anxiety disorder", "overview",
     "Anxiety disorders are characterized by excessive worry and physiological arousal disproportionate to the situation."),
    ("Anxiety disorder", "symptoms",
     "Persistent worry, restlessness, racing heart, sweating, trembling, gastrointestinal upset, difficulty concentrating, "
     "sleep disturbance. Panic attacks bring acute intense fear with chest tightness and dyspnea."),
    ("Anxiety disorder", "when_to_seek_care",
     "Symptoms interfering with work, relationships, or daily function warrant mental-health evaluation. Thoughts of self-harm "
     "require immediate crisis support."),

    ("Major depression", "overview",
     "A mood disorder marked by persistent low mood, anhedonia, and neurovegetative symptoms for at least two weeks, "
     "with significant functional impairment."),
    ("Major depression", "symptoms",
     "Sad mood most of the day, loss of interest, appetite or weight change, insomnia or hypersomnia, fatigue, feelings of "
     "worthlessness or guilt, difficulty concentrating, recurrent thoughts of death or suicide."),
    ("Major depression", "when_to_seek_care",
     "Any suicidal thoughts warrant immediate help (local crisis line / ER). Otherwise, a primary-care or mental-health "
     "referral is appropriate for evaluation and treatment."),
]


def _slug(disease: str, section: str) -> str:
    return f"{disease.lower().replace(' ', '_').replace('-', '_')}__{section}"


def main(force: bool = False) -> None:
    existing = collection_count()
    if existing and not force:
        print(f"[seed_kb] {existing} entries already present; nothing to do (use --force to reseed).")
        return
    if force and existing:
        reset_collection()
        print(f"[seed_kb] cleared {existing} existing entries.")

    print(f"[seed_kb] embedding {len(CORPUS)} entries (downloads MiniLM on first run)...")
    add_documents(
        texts=[c[2] for c in CORPUS],
        metadatas=[{"disease": c[0], "section": c[1]} for c in CORPUS],
        ids=[_slug(c[0], c[1]) for c in CORPUS],
    )
    print(f"[seed_kb] inserted {len(CORPUS)} entries into Chroma.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Wipe and reseed.")
    args = parser.parse_args()
    main(force=args.force)
