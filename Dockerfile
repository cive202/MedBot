# syntax=docker/dockerfile:1
#
# MedAssist — single-container image for a RunPod GPU Pod.
# Runs Ollama (GPU) and FastAPI (which also serves the built SPA) side by side,
# so the browser talks to exactly one origin and the auth cookie stays
# first-party. Ollama listens on loopback only and is never exposed.

# ---------- Stage 1: build the React SPA ----------
FROM node:20-bookworm-slim AS frontend

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build


# ---------- Stage 2: runtime ----------
# Torch + CUDA ship in this base, so `pip install -r requirements.txt` reuses
# them instead of pulling a second ~2.5 GB wheel for sentence-transformers.
# Python here is 3.11; the repo's .python-version (3.13) is a local dev
# preference, not a requirement — nothing in the code needs 3.12+.
FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# libmagic1 is not optional: app/services/document_ocr.py imports `magic` at
# module load time, so the entire app fails to import without it.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libmagic1 \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Ollama from the official tarball. The install.sh script assumes systemd,
# which a container does not have.
RUN curl -fsSL https://ollama.com/download/ollama-linux-amd64.tgz -o /tmp/ollama.tgz \
    && tar -xzf /tmp/ollama.tgz -C /usr/local \
    && rm /tmp/ollama.tgz

WORKDIR /app

# build-essential is installed and removed in one layer: chroma-hnswlib
# occasionally falls back to a source build when no matching wheel exists.
COPY backend/requirements.txt backend/requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && pip install --no-cache-dir -r backend/requirements.txt \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/ backend/
COPY --from=frontend /build/dist frontend/dist
COPY docker/start.sh /usr/local/bin/start.sh
RUN chmod +x /usr/local/bin/start.sh

# Everything that must survive a pod restart points at the network volume.
ENV OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_MODELS=/workspace/ollama \
    HF_HOME=/workspace/hf-cache \
    DATA_ROOT=/workspace/data \
    MEDGEMMA_MODEL=medgemma:4b \
    ENVIRONMENT=production \
    COOKIE_SECURE=true \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=5 \
    CMD curl -sf http://127.0.0.1:8000/health || exit 1

CMD ["/usr/local/bin/start.sh"]
