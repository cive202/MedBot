from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi_users import schemas
from pydantic import BaseModel, Field, field_validator

Sex = Literal["male", "female", "other", "prefer_not_to_say"]

# DOB range — keep registrations within sensible human bounds.
DOB_MIN = date(1920, 1, 1)
DOB_MAX = date(2026, 12, 31)

# Username: 3-30 chars, letters/digits/_/- only, must start with a letter.
USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_\-]{2,29}$")

BloodGroup = Literal[
    "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "unknown"
]


def _validate_dob(value: date | None) -> date | None:
    if value is None:
        return None
    if value < DOB_MIN or value > DOB_MAX:
        raise ValueError(
            f"date_of_birth must be between {DOB_MIN.isoformat()} and {DOB_MAX.isoformat()}"
        )
    return value


def _validate_username(value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip()
    if v == "":
        return None
    if not USERNAME_RE.match(v):
        raise ValueError(
            "username must be 3-30 chars, start with a letter, "
            "and use only letters, digits, '_' or '-'."
        )
    return v


class LocationIn(BaseModel):
    lat: Annotated[float, Field(ge=-90, le=90)]
    lon: Annotated[float, Field(ge=-180, le=180)]
    label: str | None = None  # e.g. reverse-geocoded city


class HistoryIn(BaseModel):
    conditions: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    blood_group: BloodGroup | None = None
    notes: str | None = None


class UserRead(schemas.BaseUser[uuid.UUID]):
    username: str | None = None
    full_name: str | None = None
    date_of_birth: date | None = None
    sex: Sex | None = None
    location: LocationIn | None = None
    history: HistoryIn | None = None


class UserCreate(schemas.BaseUserCreate):
    username: str | None = None
    full_name: str | None = None
    date_of_birth: date | None = None
    sex: Sex | None = None
    location: LocationIn | None = None
    history: HistoryIn | None = None

    _v_dob = field_validator("date_of_birth")(_validate_dob)
    _v_username = field_validator("username")(_validate_username)


class UserUpdate(schemas.BaseUserUpdate):
    username: str | None = None
    full_name: str | None = None
    date_of_birth: date | None = None
    sex: Sex | None = None
    location: LocationIn | None = None
    history: HistoryIn | None = None

    _v_dob = field_validator("date_of_birth")(_validate_dob)
    _v_username = field_validator("username")(_validate_username)
