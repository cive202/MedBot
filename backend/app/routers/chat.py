"""Chat endpoints.

Two modes share one pipeline:

* **Signed in** — conversations and messages are persisted, history is read
  back from the database, and profile details come from the user's record.
* **Guest** — nothing is written. The client replays its own history in the
  request body and may attach a one-off profile. The response carries no
  ``conversation_id``, so there is nothing to resume and nothing to clean up.

Guest-supplied history and profile are ignored for signed-in callers, so those
fields cannot be used to inject context into another user's session.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.deps import current_active_user, current_optional_user
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.schemas.chat import ChatRequest, ConversationOut, ConversationSummary
from app.services.disease_predict import predict_and_explain
from app.services.patient_context import PatientContext

router = APIRouter(prefix="/api", tags=["chat"])

# Prior turns replayed into the prompt for signed-in users.
HISTORY_TURNS = 16


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
) -> list[Conversation]:
    result = await session.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .limit(50)
    )
    return list(result.scalars().all())


@router.get("/conversations/{conv_id}", response_model=ConversationOut)
async def get_conversation(
    conv_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
) -> Conversation:
    result = await session.execute(
        select(Conversation)
        .where(Conversation.id == conv_id, Conversation.user_id == user.id)
        .options(selectinload(Conversation.messages))
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


def _sse(event: str, payload: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n".encode("utf-8")


async def _load_or_create_conversation(
    req: ChatRequest, user: User, session: AsyncSession
) -> tuple[Conversation, list[dict[str, str]]]:
    """Resolve the conversation and its prior turns for a signed-in user."""
    if req.conversation_id is not None:
        result = await session.execute(
            select(Conversation).where(
                Conversation.id == req.conversation_id,
                Conversation.user_id == user.id,
            )
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conv = Conversation(
            user_id=user.id,
            title=req.message[:80] + ("…" if len(req.message) > 80 else ""),
        )
        session.add(conv)
        await session.flush()

    # Read prior turns BEFORE persisting the new message so it isn't counted twice.
    history_rows = await session.execute(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at.asc())
        .limit(HISTORY_TURNS)
    )
    history = [
        {"role": m.role, "content": m.content}
        for m in history_rows.scalars().all()
        if m.role in ("user", "assistant")
    ]

    session.add(Message(conversation_id=conv.id, role="user", content=req.message))
    await session.commit()
    await session.refresh(conv)
    return conv, history


async def _persist_reply(conv_id: uuid.UUID, text: str, metadata: dict) -> None:
    """Store the assistant turn on a fresh session (the request one is stale)."""
    from app.db import SessionLocal

    async with SessionLocal() as session:
        session.add(
            Message(
                conversation_id=conv_id,
                role="assistant",
                content=text,
                extra=metadata,
            )
        )
        await session.commit()


@router.post("/chat")
async def chat(
    req: ChatRequest,
    user: User | None = Depends(current_optional_user),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    if user is not None:
        conv, history = await _load_or_create_conversation(req, user, session)
        conv_id: uuid.UUID | None = conv.id
        patient = PatientContext.from_profile(user)
    else:
        # Guest: stateless. History and profile come from the client, and the
        # exchange is never written anywhere.
        conv_id = None
        history = [turn.model_dump() for turn in req.history]
        patient = PatientContext.from_profile(req.guest_profile)

    stream, metadata = await predict_and_explain(patient, req.message, history=history)

    async def event_source() -> AsyncIterator[bytes]:
        yield _sse(
            "meta",
            {"conversation_id": str(conv_id) if conv_id else None, **metadata},
        )

        chunks: list[str] = []
        try:
            async for delta in stream:
                chunks.append(delta)
                yield _sse("delta", {"text": delta})
        except Exception as e:  # noqa: BLE001 — surface as an SSE event, not a 500
            yield _sse("error", {"message": str(e)})

        final_text = "".join(chunks)
        if conv_id is not None:
            await _persist_reply(conv_id, final_text, metadata)

        yield _sse("done", {"length": len(final_text)})

    return StreamingResponse(event_source(), media_type="text/event-stream")
