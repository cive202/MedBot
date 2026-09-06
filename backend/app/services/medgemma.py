from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import get_settings

settings = get_settings()


class MedGemmaError(RuntimeError):
    pass


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=settings.ollama_url, timeout=httpx.Timeout(120.0, connect=10.0))


async def is_ready() -> dict[str, Any]:
    """Quick status check for the Ollama server + model."""
    try:
        async with _client() as c:
            r = await c.get("/api/tags", timeout=2.0)
            r.raise_for_status()
            tags = r.json().get("models", [])
            family = settings.medgemma_model.split(":")[0]
            present = any(
                m.get("name") == settings.medgemma_model
                or m.get("name", "").split(":")[0] == family
                for m in tags
            )
            return {"ollama_running": True, "model_ready": present, "model": settings.medgemma_model}
    except httpx.HTTPError:
        return {"ollama_running": False, "model_ready": False, "model": settings.medgemma_model}


# Keep MedGemma resident in VRAM between calls. Ollama's default is 5 min;
# medical chat turns can be longer between requests, so we extend it.
KEEP_ALIVE = "30m"


async def chat_json(messages: list[dict[str, Any]], temperature: float = 0.2) -> dict[str, Any]:
    """One-shot non-streaming chat that requests strict JSON output."""
    payload = {
        "model": settings.medgemma_model,
        "messages": messages,
        "stream": False,
        "format": "json",
        "keep_alive": KEEP_ALIVE,
        "options": {"temperature": temperature},
    }
    async with _client() as c:
        r = await c.post("/api/chat", json=payload)
        if r.status_code != 200:
            raise MedGemmaError(f"Ollama error {r.status_code}: {r.text[:500]}")
        data = r.json()
        content = data.get("message", {}).get("content", "")
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise MedGemmaError(f"MedGemma did not return valid JSON: {content[:300]}") from e


async def chat_stream(
    messages: list[dict[str, Any]], temperature: float = 0.3
) -> AsyncIterator[str]:
    """Stream text deltas from MedGemma."""
    payload = {
        "model": settings.medgemma_model,
        "messages": messages,
        "stream": True,
        "keep_alive": KEEP_ALIVE,
        "options": {"temperature": temperature},
    }
    async with _client() as c:
        async with c.stream("POST", "/api/chat", json=payload) as r:
            if r.status_code != 200:
                body = await r.aread()
                raise MedGemmaError(f"Ollama error {r.status_code}: {body[:500].decode(errors='replace')}")
            async for line in r.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                delta = chunk.get("message", {}).get("content")
                if delta:
                    yield delta
                if chunk.get("done"):
                    break


async def vision_json(prompt: str, image_bytes: bytes) -> dict[str, Any]:
    """Send an image plus prompt to MedGemma; expect JSON output."""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "model": settings.medgemma_model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [b64],
            }
        ],
        "stream": False,
        "format": "json",
        "keep_alive": KEEP_ALIVE,
        "options": {"temperature": 0.2},
    }
    async with _client() as c:
        r = await c.post("/api/chat", json=payload)
        if r.status_code != 200:
            raise MedGemmaError(f"Ollama vision error {r.status_code}: {r.text[:500]}")
        data = r.json()
        content = data.get("message", {}).get("content", "")
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise MedGemmaError(f"MedGemma vision did not return valid JSON: {content[:300]}") from e
