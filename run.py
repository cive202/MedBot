"""
One-command launcher for MedAssist.

What it does (no Docker required):
  1. Ensures backend/.env exists and has a FERNET_KEY.
  2. Installs Python dependencies.
  3. Runs Alembic migrations against the local SQLite file.
  4. Seeds the Chroma vector store with the built-in disease KB.
  5. Checks that Ollama is reachable and pulls MedGemma if missing.
  6. Boots FastAPI on http://localhost:8000.

Frontend is started separately:  cd frontend && npm install && npm run dev
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
ENV_FILE = BACKEND / ".env"
ENV_EXAMPLE = BACKEND / ".env.example"
DATA_DIR = BACKEND / "data"

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MEDGEMMA_MODEL = os.environ.get("MEDGEMMA_MODEL", "medgemma:4b")


def info(msg: str) -> None:
    print(f"[run] {msg}")


def fatal(msg: str) -> None:
    print(f"[run] ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def ensure_env_file() -> None:
    if ENV_FILE.exists():
        return
    if not ENV_EXAMPLE.exists():
        fatal(f"Missing {ENV_EXAMPLE}; cannot bootstrap .env")
    info(f"Creating {ENV_FILE} from .env.example")
    shutil.copyfile(ENV_EXAMPLE, ENV_FILE)


def ensure_fernet_key() -> None:
    from cryptography.fernet import Fernet

    contents = ENV_FILE.read_text(encoding="utf-8")
    has_real_key = False
    for line in contents.splitlines():
        if line.startswith("FERNET_KEY="):
            val = line.split("=", 1)[1].strip()
            if val and not val.startswith("generate"):
                has_real_key = True
                break
    if has_real_key:
        return

    key = Fernet.generate_key().decode()
    new_lines: list[str] = []
    replaced = False
    for line in contents.splitlines():
        if line.startswith("FERNET_KEY="):
            new_lines.append(f"FERNET_KEY={key}")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        new_lines.append(f"FERNET_KEY={key}")
    ENV_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    info("Generated FERNET_KEY in backend/.env")


def install_python_deps() -> None:
    req = BACKEND / "requirements.txt"
    if not req.exists():
        fatal(f"Missing {req}")
    info("Installing Python dependencies (consider running inside a venv)...")
    result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(req)])
    if result.returncode != 0:
        fatal("pip install failed")


def ensure_data_dir() -> None:
    (DATA_DIR / "chroma").mkdir(parents=True, exist_ok=True)


def run_db_migrations() -> None:
    info("Running Alembic migrations against SQLite...")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
    )
    if result.returncode != 0:
        fatal("Alembic migration failed. Check the trace above.")


def seed_knowledge_base() -> None:
    """Populate the Chroma knowledge base. Idempotent — skips if already filled.

    On by default: without it retrieval silently returns nothing, which is a
    confusing way for a fresh clone to behave. Set SKIP_SEED=1 to opt out.
    """
    if os.environ.get("SKIP_SEED", "0") == "1":
        info("Skipping KB seed (SKIP_SEED=1).")
        return
    info("Seeding disease knowledge base into Chroma (idempotent)...")
    env = dict(os.environ)
    # The embedding model is cached after first download. Some networks
    # intercept TLS, which makes the hub's update check fail noisily even
    # though the cached copy is fine — this keeps startup quiet once cached.
    env.setdefault("HF_HUB_OFFLINE", "1" if _embed_model_cached() else "0")
    result = subprocess.run(
        [sys.executable, "-m", "scripts.seed_kb"],
        cwd=BACKEND,
        env=env,
    )
    if result.returncode != 0:
        info("Seed step failed; chat still works but RAG context will be empty.")


def _embed_model_cached() -> bool:
    """True if the sentence-transformers model is already in the local HF cache."""
    cache = Path.home() / ".cache" / "huggingface" / "hub"
    return any(cache.glob("models--sentence-transformers--all-MiniLM-L6-v2"))


def ollama_running() -> bool:
    import urllib.request

    try:
        urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2)
        return True
    except Exception:
        return False


def ensure_ollama_model() -> None:
    if not ollama_running():
        info(
            "Ollama is not running. Start it (Ollama Desktop or `ollama serve`) "
            "and re-run if you want the chatbot to answer. Skipping model pull."
        )
        return
    import json as _json
    import urllib.request

    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5) as r:
            tags = _json.loads(r.read())
        names = {m.get("name", "") for m in tags.get("models", [])}
        family = MEDGEMMA_MODEL.split(":")[0]
        if MEDGEMMA_MODEL in names or any(n.split(":")[0] == family for n in names):
            info(f"Ollama model '{MEDGEMMA_MODEL}' is present.")
            return
    except Exception as e:
        info(f"Could not enumerate Ollama models ({e}); attempting pull anyway.")

    info(f"Pulling Ollama model '{MEDGEMMA_MODEL}' (this may take a while)...")
    result = subprocess.run(["ollama", "pull", MEDGEMMA_MODEL])
    if result.returncode != 0:
        info(f"`ollama pull {MEDGEMMA_MODEL}` failed; you can retry manually. Continuing.")


def boot_backend_and_open_browser() -> None:
    info("Booting FastAPI on http://localhost:8000 ...")

    def open_later():
        time.sleep(2.5)
        webbrowser.open("http://localhost:8000/health")

    import threading

    threading.Thread(target=open_later, daemon=True).start()

    os.chdir(BACKEND)
    os.execvp(
        sys.executable,
        [sys.executable, "-m", "uvicorn", "app.main:app", "--reload",
         "--host", "0.0.0.0", "--port", "8000"],
    )


def main() -> None:
    info(f"MedAssist launcher — root={ROOT}")
    ensure_env_file()
    install_python_deps()
    ensure_fernet_key()
    ensure_data_dir()
    run_db_migrations()
    seed_knowledge_base()
    ensure_ollama_model()
    boot_backend_and_open_browser()


if __name__ == "__main__":
    main()
