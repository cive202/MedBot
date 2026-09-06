"""
Interactive terminal tool to test the Random Forest disease classifier.

Usage (from backend/ directory):
    python -m scripts.predict_symptoms

You will be prompted to enter symptoms one by one, then the model
will predict the most likely diseases with confidence scores.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib
import numpy as np

MODEL_PATH = Path(__file__).resolve().parents[1] / "data" / "rf_model.joblib"


def load_model():
    print("Loading model... (this may take a moment for the large model)")
    bundle = joblib.load(MODEL_PATH)
    return bundle["model"], bundle["features"], bundle["classes"]


def fuzzy_match(query: str, features: list[str]) -> list[str]:
    """Return symptoms that contain the query string (case-insensitive)."""
    q = query.lower().strip()
    return [f for f in features if q in f.lower()]


def run():
    if not MODEL_PATH.exists():
        sys.exit(f"Model not found at {MODEL_PATH}\nRun: python -m scripts.train_kaggle_rf")

    model, features, classes = load_model()
    print(f"\n✅ Model loaded! Knows {len(features)} symptoms and {len(classes)} diseases.\n")

    while True:
        print("=" * 60)
        print("🩺  MEDASSIST Disease Predictor - Symptom Checker")
        print("=" * 60)
        print("Type symptoms one at a time. Type 'done' when finished.")
        print("Type 'list <keyword>' to search available symptoms.")
        print("Type 'quit' to exit.\n")

        selected_symptoms: list[str] = []

        while True:
            prompt = f"[{len(selected_symptoms)} symptoms selected] Enter symptom: "
            try:
                entry = input(prompt).strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                return

            if entry == "quit":
                print("Goodbye!")
                return

            if entry == "done":
                if not selected_symptoms:
                    print("⚠  Please enter at least one symptom first.\n")
                    continue
                break

            if entry.startswith("list"):
                keyword = entry[4:].strip()
                if not keyword:
                    print("Usage: list <keyword>  e.g. list fever")
                    continue
                matches = fuzzy_match(keyword, features)
                if matches:
                    print(f"\nSymptoms matching '{keyword}':")
                    for m in matches[:30]:
                        marker = "✓ " if m in selected_symptoms else "  "
                        print(f"  {marker}{m}")
                    if len(matches) > 30:
                        print(f"  ... and {len(matches) - 30} more")
                else:
                    print(f"  No symptoms found matching '{keyword}'")
                print()
                continue

            if not entry:
                continue

            # Try exact match first
            if entry in features:
                if entry in selected_symptoms:
                    print(f"  ℹ  '{entry}' is already added.")
                else:
                    selected_symptoms.append(entry)
                    print(f"  ✓ Added: '{entry}'")
            else:
                # Fuzzy match
                matches = fuzzy_match(entry, features)
                if not matches:
                    print(f"  ✗ No symptom found matching '{entry}'. Try 'list {entry}' to search.")
                elif len(matches) == 1:
                    sym = matches[0]
                    if sym in selected_symptoms:
                        print(f"  ℹ  '{sym}' is already added.")
                    else:
                        selected_symptoms.append(sym)
                        print(f"  ✓ Auto-matched and added: '{sym}'")
                else:
                    print(f"\n  Multiple matches for '{entry}'. Pick one:")
                    for i, m in enumerate(matches[:10], 1):
                        marker = "✓" if m in selected_symptoms else " "
                        print(f"    {i}. [{marker}] {m}")
                    try:
                        choice = input("  Enter number (or press Enter to skip): ").strip()
                        if choice.isdigit():
                            idx = int(choice) - 1
                            if 0 <= idx < len(matches[:10]):
                                sym = matches[idx]
                                if sym in selected_symptoms:
                                    print(f"  ℹ  '{sym}' is already added.")
                                else:
                                    selected_symptoms.append(sym)
                                    print(f"  ✓ Added: '{sym}'")
                    except (EOFError, KeyboardInterrupt):
                        pass
                    print()

        # Build feature vector
        print(f"\n📋 Your symptoms: {', '.join(selected_symptoms)}")
        print("\nPredicting...\n")

        x = np.zeros(len(features), dtype=np.int8)
        for sym in selected_symptoms:
            if sym in features:
                x[features.index(sym)] = 1

        proba = model.predict_proba([x])[0]
        top_n = 5
        top_indices = np.argsort(proba)[::-1][:top_n]

        print(f"🏆 Top {top_n} predicted diseases:")
        print("-" * 50)
        for rank, idx in enumerate(top_indices, 1):
            disease = classes[idx]
            confidence = proba[idx] * 100
            bar = "█" * int(confidence / 5)
            print(f"  {rank}. {disease.title()}")
            print(f"     Confidence: {confidence:.1f}%  {bar}")
        print()

        try:
            again = input("🔄 Check another set of symptoms? (y/n): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            again = "n"

        if again != "y":
            print("\nGoodbye! Stay healthy 🌿")
            break
        print()


if __name__ == "__main__":
    run()
