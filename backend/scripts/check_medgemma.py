"""
End-to-end smoke test for the MedGemma integration.

  python -m scripts.check_medgemma                    # text + JSON
  python -m scripts.check_medgemma --image path.jpg   # also vision

Exit codes:
  0 — everything works
  1 — Ollama unreachable, model missing, or call returned an error

Run this once after `ollama pull medgemma:4b` to confirm the backend can
actually talk to the model and that GPU offload is engaged.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.medgemma import (  # noqa: E402
    MedGemmaError,
    chat_json,
    chat_stream,
    is_ready,
    vision_json,
)


def _fmt(label: str, secs: float) -> str:
    return f"  {label:<28s} {secs * 1000:7.0f} ms"


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, default=None,
                        help="Optional image file to exercise vision_json().")
    args = parser.parse_args()

    print("[check_medgemma] checking /api/tags ...")
    t0 = time.monotonic()
    status = await is_ready()
    print(_fmt("is_ready()", time.monotonic() - t0))
    print(f"    {status}")
    if not status.get("ollama_running"):
        print("\nOllama is not reachable. Start it (Ollama Desktop / `ollama serve`) and retry.")
        return 1
    if not status.get("model_ready"):
        model = status.get("model")
        print(f"\nModel '{model}' is not pulled. Run: ollama pull {model}")
        return 1

    print("\n[check_medgemma] chat_json (severity grader prompt) ...")
    t0 = time.monotonic()
    try:
        result = await chat_json(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a triage assistant. Return strict JSON with this shape: "
                        '{"severity": "mild|moderate|severe|emergency", '
                        '"specialty": "<lowercase snake_case>", '
                        '"reasoning": "<one short sentence>"}.'
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Patient message: crushing chest pain radiating to left arm, sweating, "
                        "shortness of breath for 20 minutes."
                    ),
                },
            ],
            temperature=0.0,
        )
        print(_fmt("chat_json()", time.monotonic() - t0))
        print(f"    {result}")
    except MedGemmaError as e:
        print(f"  chat_json failed: {e}")
        return 1

    print("\n[check_medgemma] chat_stream (5 token preview) ...")
    t0 = time.monotonic()
    first_token_at = None
    n = 0
    try:
        async for delta in chat_stream(
            messages=[
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": "List three common cold symptoms."},
            ],
            temperature=0.3,
        ):
            if first_token_at is None:
                first_token_at = time.monotonic() - t0
            n += len(delta)
            print(delta, end="", flush=True)
            if time.monotonic() - t0 > 8:
                break
        print()
        print(_fmt("first-token latency", first_token_at or 0))
        print(_fmt("total streamed bytes", n / 1))
    except MedGemmaError as e:
        print(f"  chat_stream failed: {e}")
        return 1

    if args.image is not None:
        if not args.image.exists():
            print(f"\n[check_medgemma] image {args.image} not found, skipping vision check.")
        else:
            print(f"\n[check_medgemma] vision_json on {args.image.name} ...")
            t0 = time.monotonic()
            try:
                result = await vision_json(
                    'Describe this image in JSON: {"modality_guess": "...", "findings": ["..."]}.',
                    args.image.read_bytes(),
                )
                print(_fmt("vision_json()", time.monotonic() - t0))
                print(f"    {result}")
            except MedGemmaError as e:
                print(f"  vision_json failed: {e}")
                return 1

    print("\n[check_medgemma] all OK.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
