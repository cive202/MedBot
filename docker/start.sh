#!/usr/bin/env bash
#
# Container entrypoint for the RunPod GPU Pod.
#
# Order matters: Ollama has to be up before uvicorn starts, because main.py's
# lifespan warms MedGemma at boot. Everything that must survive a pod restart
# lives on the network volume; backend/data is symlinked there because rf.py,
# vectorstore.py and specialists.py all resolve paths relative to backend/.
set -euo pipefail

APP_DIR=/app/backend
DATA_ROOT="${DATA_ROOT:-/workspace/data}"
OLLAMA_MODELS="${OLLAMA_MODELS:-/workspace/ollama}"
HF_HOME="${HF_HOME:-/workspace/hf-cache}"
OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
MEDGEMMA_MODEL="${MEDGEMMA_MODEL:-medgemma:4b}"
PORT="${PORT:-8000}"
export OLLAMA_MODELS HF_HOME OLLAMA_HOST

log() { echo "[start] $*"; }

# --- 1. Persistent storage -------------------------------------------------
mkdir -p "$DATA_ROOT" "$OLLAMA_MODELS" "$HF_HOME"
if [ ! -L "$APP_DIR/data" ]; then
    rm -rf "$APP_DIR/data"
    ln -s "$DATA_ROOT" "$APP_DIR/data"
fi
log "backend/data -> $DATA_ROOT"

# --- 2. Secret sanity ------------------------------------------------------
# Not fatal, because a demo pod without them still boots — but both are silent
# failures if you miss them, so say so loudly.
if [ -z "${FERNET_KEY:-}" ]; then
    log "WARNING: FERNET_KEY unset -> saved profiles are stored UNENCRYPTED."
    log "         Set it once as a RunPod env var and never change it: a new key"
    log "         makes every previously saved profile undecryptable."
fi
if [ -z "${SECRET_KEY:-}" ]; then
    log "WARNING: SECRET_KEY unset -> JWTs signed with the public default value."
fi

# --- 3. Ollama -------------------------------------------------------------
log "starting ollama on $OLLAMA_HOST (loopback only — do not expose this port)"
ollama serve &
OLLAMA_PID=$!
trap 'kill "$OLLAMA_PID" 2>/dev/null || true' EXIT

for _ in $(seq 1 60); do
    if curl -sf "http://${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
        log "ollama is up"
        break
    fi
    sleep 2
done

if ! curl -sf "http://${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
    log "ERROR: ollama did not come up in 120s — chat will fail. Continuing so"
    log "       /health stays reachable for debugging."
else
    # Match on the model family the way app/services/medgemma.py does, so a
    # differently-tagged MedGemma already on the volume is not re-pulled.
    family="${MEDGEMMA_MODEL%%:*}"
    if ollama list 2>/dev/null | tail -n +2 | awk '{print $1}' | grep -q "^${family}"; then
        log "model '${MEDGEMMA_MODEL}' already present in $OLLAMA_MODELS"
    else
        log "pulling '${MEDGEMMA_MODEL}' (4-6 GB, first boot only)..."
        ollama pull "$MEDGEMMA_MODEL" || log "pull failed — fix the tag and restart"
    fi
fi

# --- 4. Database + knowledge base -----------------------------------------
cd "$APP_DIR"

log "running alembic migrations"
python -m alembic upgrade head

if [ "${SKIP_SEED:-0}" = "1" ]; then
    log "skipping KB seed (SKIP_SEED=1)"
else
    log "seeding chroma KB (idempotent)"
    python -m scripts.seed_kb || log "seed failed — chat works, RAG context empty"
fi

if [ ! -f "$DATA_ROOT/rf_model.joblib" ]; then
    log "WARNING: rf_model.joblib not found in $DATA_ROOT."
    log "         Disease prediction degrades to [] and chat falls back to"
    log "         MedGemma + RAG only. Upload it — see DEPLOY.md step 5."
fi

# --- 5. Serve --------------------------------------------------------------
# One worker on purpose: SQLite plus the in-process RF/Chroma singletons do not
# survive being forked. --timeout-keep-alive is raised for the SSE chat stream.
log "starting uvicorn on 0.0.0.0:${PORT}"
exec python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --workers 1 \
    --timeout-keep-alive 75
