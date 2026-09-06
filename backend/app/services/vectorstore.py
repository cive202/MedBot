"""
Chroma vector store accessed via LangChain.

Persistent, HNSW-backed, on-disk under ``backend/data/chroma``. No external
server required. Embeddings use sentence-transformers/all-MiniLM-L6-v2 (384-d,
L2-normalized) wrapped by LangChain's HuggingFaceEmbeddings.

Robustness / scale notes:
  * Persistent across restarts (data lives on disk).
  * HNSW index is built lazily; insertion order doesn't matter.
  * Thread-safe singleton — the underlying chromadb client uses an internal
    lock, and we add one of our own to guard initialization.
  * Heavy retrieval calls are pushed to a worker thread via asyncio.to_thread
    so the FastAPI event loop never blocks.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.config import get_settings

if TYPE_CHECKING:
    from langchain_chroma import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings

log = logging.getLogger(__name__)

EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384


def _resolve_dir(raw: str) -> Path:
    p = Path(raw)
    if not p.is_absolute():
        backend = Path(__file__).resolve().parents[2]
        p = (backend / p).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


_embeddings: "HuggingFaceEmbeddings | None" = None
_vectorstore: "Chroma | None" = None
_lock = threading.RLock()


def _detect_device() -> str:
    try:
        import torch  # type: ignore[import-not-found]

        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def get_embeddings() -> "HuggingFaceEmbeddings":
    global _embeddings
    if _embeddings is None:
        with _lock:
            if _embeddings is None:
                from langchain_huggingface import HuggingFaceEmbeddings

                _embeddings = HuggingFaceEmbeddings(
                    model_name=EMBED_MODEL_NAME,
                    model_kwargs={"device": _detect_device()},
                    encode_kwargs={"normalize_embeddings": True, "batch_size": 32},
                )
                log.info("Loaded embeddings %s on %s", EMBED_MODEL_NAME, _detect_device())
    return _embeddings


def get_vectorstore() -> "Chroma":
    global _vectorstore
    if _vectorstore is None:
        with _lock:
            if _vectorstore is None:
                from langchain_chroma import Chroma

                settings = get_settings()
                directory = _resolve_dir(settings.chroma_dir)
                _vectorstore = Chroma(
                    collection_name=settings.chroma_collection,
                    embedding_function=get_embeddings(),
                    persist_directory=str(directory),
                    collection_metadata={"hnsw:space": "cosine"},
                )
                log.info(
                    "Initialized Chroma at %s (collection=%s)",
                    directory,
                    settings.chroma_collection,
                )
    return _vectorstore


def collection_count() -> int:
    """Return how many entries are currently indexed (0 if collection empty)."""
    try:
        return get_vectorstore()._collection.count()  # type: ignore[attr-defined]
    except Exception as e:
        log.warning("Could not count vector store entries: %s", e)
        return 0


def reset_collection() -> None:
    """Delete every entry in the collection. Safe; only used by seed --force."""
    try:
        coll = get_vectorstore()._collection  # type: ignore[attr-defined]
        all_ids = coll.get(include=[]).get("ids", [])
        if all_ids:
            coll.delete(ids=all_ids)
    except Exception as e:
        log.warning("Could not reset collection: %s", e)


def add_documents(
    *,
    texts: list[str],
    metadatas: list[dict[str, Any]],
    ids: list[str],
) -> None:
    """Insert (or upsert by id) documents into the vector store."""
    vs = get_vectorstore()
    vs.add_texts(texts=texts, metadatas=metadatas, ids=ids)
