from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.deps import current_optional_user
from app.models.user import User
from app.services.socrates import next_step

router = APIRouter(prefix="/api/intake", tags=["intake"])


class IntakeAnswer(BaseModel):
    key: str = Field(default="anything_else")
    question: str = Field(default="")
    answer: str = Field(default="")
    letter: str = Field(default="-")
    letter_label: str = Field(default="Response")


class IntakeRequest(BaseModel):
    answers: list[IntakeAnswer] = Field(default_factory=list)


@router.post("/next")
async def get_next_step(
    req: IntakeRequest,
    _: User | None = Depends(current_optional_user),
) -> dict[str, Any]:
    """Ask MedGemma what to ask the patient next, or finish the intake.

    Stateless and open to guests — the answers live in the request body.
    """
    return await next_step([a.model_dump() for a in req.answers])
