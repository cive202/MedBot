import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.routes import router as auth_router
from app.config import get_settings
from app.routers.analyze import router as analyze_router
from app.routers.chat import router as chat_router
from app.routers.intake import router as intake_router
from app.routers.location import router as location_router
from app.routers.profile import router as profile_router

log = logging.getLogger("medassist.startup")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm-load the RF classifier in the BACKGROUND so the app starts serving
    # auth/profile/health immediately. The first chat request will block on the
    # singleton lock if the load is still in flight — every other request is
    # unaffected.
    def _say(msg: str) -> None:
        # Use print so the message lands on uvicorn's stdout, not Python logging.
        print(f"[medassist] {msg}", flush=True)

    async def _warm_rf() -> None:
        try:
            from app.services.rf import get_predictor

            await asyncio.to_thread(get_predictor)
            _say("RF predictor warmed.")
        except Exception as e:
            _say(f"RF warm-load failed: {e}")

    async def _warm_rag() -> None:
        # Loads sentence-transformers/all-MiniLM-L6-v2 (CUDA if available) and
        # opens the Chroma index so the first retrieve() call doesn't pay
        # ~5-15 seconds of model-load + index-init time.
        try:
            from app.services.vectorstore import get_vectorstore

            def _open() -> None:
                vs = get_vectorstore()
                vs.similarity_search("warm-up", k=1)

            await asyncio.to_thread(_open)
            _say("RAG (Chroma + MiniLM) warmed.")
        except Exception as e:
            _say(f"RAG warm-load failed: {e}")

    async def _warm_medgemma() -> None:
        # Send a tiny prompt so Ollama pulls medgemma:4b into VRAM before the
        # first real chat request. Skips silently if Ollama isn't running.
        try:
            from app.services.medgemma import chat_json, is_ready

            status = await is_ready()
            if not status.get("ollama_running"):
                _say("Ollama not reachable at startup; MedGemma will warm on first request.")
                return
            if not status.get("model_ready"):
                _say(f"MedGemma model '{status.get('model')}' not present; run `ollama pull {status.get('model')}`.")
                return
            await chat_json(
                messages=[
                    {"role": "system", "content": "Reply with strict JSON."},
                    {"role": "user", "content": 'Echo {"ok": true} and nothing else.'},
                ],
                temperature=0.0,
            )
            _say("MedGemma warmed.")
        except Exception as e:
            _say(f"MedGemma warm-load failed: {e}")

    warm_tasks = [
        asyncio.create_task(_warm_rf()),
        asyncio.create_task(_warm_rag()),
        asyncio.create_task(_warm_medgemma()),
    ]
    try:
        yield
    finally:
        for t in warm_tasks:
            t.cancel()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(chat_router)
app.include_router(intake_router)
app.include_router(location_router)
app.include_router(analyze_router)


@app.get("/health")
async def health() -> dict:
    """Liveness + key-subsystem readiness in one shot. Never blocks on warm-load."""
    from app.services import medgemma as medgemma_svc
    from app.services.rf import get_predictor_if_loaded

    medgemma_state = await medgemma_svc.is_ready()
    rf = get_predictor_if_loaded()
    rf_state: dict = {"ready": False, "loading": rf is None}
    if rf is not None:
        rf_state = {
            "ready": rf.ready,
            "features": len(rf.feature_names),
            "classes": len(rf.classes),
        }
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.environment,
        "medgemma": medgemma_state,
        "rf": rf_state,
    }
