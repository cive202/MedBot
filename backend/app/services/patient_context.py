"""
The patient details the triage pipeline reads, decoupled from where they came from.

A signed-in user's details come from their database row; a guest's arrive in the
request body and are never persisted. Both expose the same attribute names, so
:meth:`PatientContext.from_profile` accepts either and the pipeline never has to
know which it was given.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


def _as_dict(value: Any) -> dict[str, Any] | None:
    """Normalise a JSON column (dict) or a Pydantic model into a plain dict."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    dump = getattr(value, "model_dump", None)
    return dump() if callable(dump) else None


@dataclass(frozen=True)
class PatientContext:
    """Read-only snapshot of the patient, safe to pass around the pipeline."""

    full_name: str | None = None
    sex: str | None = None
    date_of_birth: date | None = None
    history: dict[str, Any] | None = None
    location: dict[str, Any] | None = None

    @classmethod
    def from_profile(cls, profile: Any | None) -> PatientContext:
        """Build from a ``User`` row, a guest profile payload, or ``None``.

        ``None`` yields an empty context — an anonymous visitor who supplied no
        details. Every field is optional, so the pipeline degrades to
        symptom-only triage rather than failing.
        """
        if profile is None:
            return cls()
        return cls(
            full_name=getattr(profile, "full_name", None),
            sex=getattr(profile, "sex", None),
            date_of_birth=getattr(profile, "date_of_birth", None),
            history=_as_dict(getattr(profile, "history", None)),
            location=_as_dict(getattr(profile, "location", None)),
        )
