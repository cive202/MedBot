"""Freeze real MedGemma answers from the live pod into a fallback bundle.

Shells out to curl: this machine's network intercepts TLS, so Python's cert
store rejects the RunPod proxy certificate while curl accepts it.
"""
import json, subprocess, time
from pathlib import Path

import os

# Point at whichever pod is live when you regenerate.
BASE = os.environ.get("MEDBOT_URL", "https://b9opmtc497vl0v-8000.proxy.runpod.net").rstrip("/")
OUT = Path(__file__).resolve().parents[1] / "frontend" / "src" / "data" / "fallbackAnswers.json"

QUESTIONS = [
    "What is the difference between a common cold and the flu?",
    "I have had a sore throat for two days. What could be causing it?",
    "When does a fever become serious enough to see a doctor?",
    "I have a persistent cough that will not go away. What could it be?",
    "What can cause a headache that lasts several days?",
    "I have stomach pain and nausea. What might be causing this?",
    "What are the classic warning signs that someone needs emergency care?",
    "What causes shortness of breath, and when is it urgent?",
    "I feel dizzy and lightheaded when I stand up. Why might that happen?",
    "What can I do at home for body aches and tiredness?",
]


def ask(q: str) -> dict:
    body = json.dumps({"message": q, "conversation_id": None, "history": []})
    raw = subprocess.run(
        ["curl", "-sN", "-X", "POST", f"{BASE}/api/chat",
         "-H", "Content-Type: application/json", "-d", body, "--max-time", "300"],
        capture_output=True, check=True,
    ).stdout.decode("utf-8", "replace")

    text, meta = [], {}
    for frame in raw.split("\n\n"):
        event, data = "message", []
        for line in frame.split("\n"):
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].strip())
        if not data:
            continue
        try:
            payload = json.loads("\n".join(data))
        except json.JSONDecodeError:
            continue
        if event == "meta":
            meta = payload
        elif event == "delta":
            text.append(payload.get("text", ""))
        elif event == "error":
            text.append(f"\n[error: {payload.get('message')}]")

    return {
        "question": q,
        "answer": "".join(text).strip(),
        "severity": meta.get("severity"),
        "specialty": meta.get("specialty"),
        "retrieved": sorted({d.get("disease") for d in (meta.get("retrieved") or [])}),
    }


results = []
for i, q in enumerate(QUESTIONS, 1):
    t0 = time.time()
    try:
        item = ask(q)
        results.append(item)
        print(f"[{i}/{len(QUESTIONS)}] {time.time()-t0:5.1f}s {len(item['answer']):5d} chars "
              f"sev={item['severity']} :: {q[:46]}", flush=True)
    except Exception as e:
        print(f"[{i}/{len(QUESTIONS)}] FAILED: {e} :: {q[:46]}", flush=True)

OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nwrote {OUT} ({len(results)}/{len(QUESTIONS)} answers)")
