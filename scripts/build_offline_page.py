"""
Build the standalone offline page from the frozen fallback answers.

The in-app fallback (frontend/src/components/FallbackSuggestions.tsx) only helps
when the pod is up but the model is not. When the pod is stopped entirely there
is no site at all, because FastAPI serves the frontend — so this emits a single
self-contained HTML file you can host anywhere (Vercel, Netlify, GitHub Pages).

    python scripts/build_offline_page.py

Reads  frontend/src/data/fallbackAnswers.json
Writes offline/index.html
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "src" / "data" / "fallbackAnswers.json"
OUT = ROOT / "offline" / "index.html"

SEVERITY_LABEL = {
    "low": "Routine",
    "moderate": "See a clinician soon",
    "critical": "Urgent",
}


def format_answer(text: str) -> str:
    """Escape, then render the model's light markdown: **bold** and * bullets."""
    out: list[str] = []
    bullets: list[str] = []

    def flush() -> None:
        if bullets:
            out.append("<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>")
            bullets.clear()

    for line in text.split("\n"):
        esc = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(line))
        stripped = esc.strip()
        if stripped.startswith("* "):
            bullets.append(stripped[2:].strip())
        elif stripped == "---":
            flush()
            out.append("<hr>")
        else:
            flush()
            out.append(esc)
    flush()
    return "\n".join(out).strip()


def render(entries: list[dict]) -> str:
    items = []
    for i, e in enumerate(entries):
        q = html.escape(e["question"])
        a = format_answer(e["answer"])
        sev = (e.get("severity") or "").lower()
        badge = (
            f'<span class="sev sev-{html.escape(sev)}">'
            f"{html.escape(SEVERITY_LABEL.get(sev, sev))}</span>"
            if sev
            else ""
        )
        items.append(
            f'<details name="qa" id="q{i}">'
            f"<summary>{q}{badge}</summary>"
            f'<div class="answer">{a}</div>'
            f"</details>"
        )
    return TEMPLATE.replace("__ITEMS__", "\n  ".join(items)).replace(
        "__COUNT__", str(len(entries))
    )


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MedAssist — Offline Answers</title>
<style>
  :root {
    color-scheme: light dark;
    --bg: #f7f7f5; --surface: #ffffff; --text: #1a1a1a; --muted: #6b6b6b;
    --border: #e3e3df; --accent: #2f6f6b; --warn-bg: #fff8e6; --warn-br: #e8c56a;
    --warn-tx: #6b4e00;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #16181a; --surface: #1e2124; --text: #ececec; --muted: #9aa0a6;
      --border: #2e3235; --accent: #6fbcb6; --warn-bg: #2a2416; --warn-br: #6b5a2a;
      --warn-tx: #e8c56a;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 0 1rem 4rem;
    background: var(--bg); color: var(--text);
    font: 15px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }
  .wrap { max-width: 46rem; margin: 0 auto; }
  header { padding: 2.5rem 0 1.25rem; }
  h1 { margin: 0 0 .35rem; font-size: 1.6rem; letter-spacing: -.01em; }
  .sub { color: var(--muted); margin: 0; }
  .notice {
    margin: 1.25rem 0; padding: .85rem 1rem; border-radius: .6rem;
    background: var(--warn-bg); border: 1px solid var(--warn-br); color: var(--warn-tx);
    font-size: .875rem;
  }
  .notice strong { display: block; margin-bottom: .2rem; }
  details {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: .6rem; margin-bottom: .6rem; overflow: hidden;
  }
  summary {
    cursor: pointer; padding: .85rem 1rem; font-weight: 500;
    display: flex; align-items: center; gap: .6rem; list-style: none;
  }
  summary::-webkit-details-marker { display: none; }
  summary::before {
    content: "+"; color: var(--accent); font-weight: 700; flex: none; width: .9rem;
  }
  details[open] summary::before { content: "–"; }
  details[open] summary { border-bottom: 1px solid var(--border); }
  .sev {
    margin-left: auto; flex: none; font-size: .7rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: .04em;
    padding: .15rem .5rem; border-radius: 999px; border: 1px solid var(--border);
    color: var(--muted);
  }
  .sev-moderate { color: #a86a00; border-color: #d9a441; }
  .sev-critical { color: #b3261e; border-color: #e08c86; }
  .answer { padding: 1rem; white-space: pre-wrap; }
  .answer ul { margin: .4rem 0; padding-left: 1.2rem; white-space: normal; }
  .answer li { margin: .25rem 0; }
  .answer hr { border: none; border-top: 1px solid var(--border); margin: 1rem 0; }
  footer { margin-top: 2rem; color: var(--muted); font-size: .8rem; }
  code { font-size: .95em; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>MedAssist — Offline Answers</h1>
    <p class="sub">The live assistant is not running. Here are __COUNT__ saved answers to common questions.</p>
  </header>

  <div class="notice">
    <strong>These are saved, general answers.</strong>
    They were produced earlier by this assistant for the questions below — not for your
    situation. MedAssist is an educational project and is not a substitute for a
    qualified medical professional. If symptoms are severe or getting worse, contact
    local emergency services or a clinician now.
  </div>

  __ITEMS__

  <footer>
    Captured from the MedAssist model (MedGemma 4B with retrieval over the built-in
    disease knowledge base). Regenerate with
    <code>python scripts/generate_fallback_answers.py</code> then
    <code>python scripts/build_offline_page.py</code>.
  </footer>
</div>
</body>
</html>
"""


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing {SRC} — run scripts/generate_fallback_answers.py first")
    entries = json.loads(SRC.read_text(encoding="utf-8"))
    if not entries:
        raise SystemExit(f"{SRC} is empty")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(entries), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(entries)} answers)")


if __name__ == "__main__":
    main()
