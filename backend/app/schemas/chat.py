from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.user import HistoryIn, LocationIn, Sex

# Guests may carry at most this many prior turns; the pipeline only replays the
# most recent handful anyway, and an unbounded list is an easy way to blow up
# the prompt.
MAX_GUEST_HISTORY_TURNS = 20


class ChatTurn(BaseModel):
    """One prior turn, replayed by guests who have no server-side history."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class GuestProfile(BaseModel):
    """Optional details an anonymous visitor supplies for this request only.

    Field names mirror ``User`` so both feed ``PatientContext.from_profile``.
    Nothing here is written to the database.
    """

    full_name: str | None = None
    date_of_birth: date | None = None
    sex: Sex | None = None
    location: LocationIn | None = None
    history: HistoryIn | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = None

    # Guest-only fields. Signed-in requests ignore both: their history and
    # profile are read from the database instead, so a client cannot use these
    # to spoof another user's context.
    history: list[ChatTurn] = Field(
        default_factory=list, max_length=MAX_GUEST_HISTORY_TURNS
    )
    guest_profile: GuestProfile | None = None


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    extra: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut] = []

    model_config = {"from_attributes": True}


class ConversationSummary(BaseModel):
    id: uuid.UUID
    title: str
    updated_at: datetime

    model_config = {"from_attributes": True}
