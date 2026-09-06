from __future__ import annotations

from pydantic import BaseModel


class GlossaryEntry(BaseModel):
    term: str
    meaning: str


class ValueOfConcern(BaseModel):
    name: str
    value: str
    concern: str


class DocumentAnalysis(BaseModel):
    kind: str
    mime: str
    summary: str
    key_findings: list[str] = []
    values_of_concern: list[ValueOfConcern] = []
    questions_to_ask_doctor: list[str] = []
    plain_language_glossary: list[GlossaryEntry] = []
    extracted_chars: int | None = None


class XrayAnalysis(BaseModel):
    mime: str
    modality_guess: str
    findings: list[str]
    impressions: list[str]
    severity: str
    recommended_followup: str
    limitations: str


class MriAnalysis(BaseModel):
    mime: str
    body_region: str
    sequence_guess: str
    plane: str
    anatomy_visible: list[str] = []
    findings: list[str] = []
    impressions: list[str] = []
    severity: str
    recommended_followup: str
    limitations: str
