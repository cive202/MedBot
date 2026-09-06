"""
Retrieval-Augmented Generation grounding via Chroma (LangChain).

Returns lightweight dicts so callers don't depend on LangChain types.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.services.vectorstore import get_vectorstore

log = logging.getLogger(__name__)


def _build_filter(restrict_to: list[str] | None) -> dict | None:
    if not restrict_to:
        return None
    # Normalize to unique non-empty strings.
    diseases = sorted({d.strip() for d in restrict_to if d and d.strip()})
    if not diseases:
        return None
    if len(diseases) == 1:
        return {"disease": diseases[0]}
    return {"disease": {"$in": diseases}}


def _sync_retrieve(query: str, k: int, restrict_to: list[str] | None) -> list[dict[str, Any]]:
    vs = get_vectorstore()
    flt = _build_filter(restrict_to)
    try:
        docs_scored = vs.similarity_search_with_score(query, k=k, filter=flt)
    except Exception as e:
        log.warning("Vector search failed (%s); returning empty context.", e)
        return []
    out: list[dict[str, Any]] = []
    for doc, score in docs_scored:
        md = doc.metadata or {}
        out.append(
            {
                "disease": md.get("disease", "unknown"),
                "section": md.get("section", "overview"),
                "content": doc.page_content,
                "score": float(score),
            }
        )
    return out


async def retrieve(
    query: str, k: int = 5, restrict_to: list[str] | None = None
) -> list[dict[str, Any]]:
    """Cosine-similarity search over the disease KB. Non-blocking for FastAPI."""
    return await asyncio.to_thread(_sync_retrieve, query, k, restrict_to)


def format_context(chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return "(no knowledge-base context retrieved)"
    return "\n\n".join(
        f"### {c.get('disease', 'unknown')} — {c.get('section', 'overview')}\n{c.get('content', '')}"
        for c in chunks
    )
