"""Document, X-ray and MRI analysis endpoints.

Open to guests. Uploads are held in memory for the length of the request,
passed to MedGemma, and never written to disk or the database — so an
anonymous visitor leaves no trace behind.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.deps import current_optional_user
from app.models.user import User
from app.schemas.analysis import DocumentAnalysis, MriAnalysis, XrayAnalysis
from app.services.document_ocr import UnsupportedMediaError, analyze_document
from app.services.medgemma import MedGemmaError
from app.services.mri import analyze_mri
from app.services.xray import analyze_xray

router = APIRouter(prefix="/api/analyze", tags=["analyze"])


@router.post("/document", response_model=DocumentAnalysis)
async def post_document(
    file: UploadFile = File(...),
    _: User | None = Depends(current_optional_user),
) -> DocumentAnalysis:
    raw = await file.read()
    try:
        result = await analyze_document(file.filename or "document", raw)
    except UnsupportedMediaError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except MedGemmaError as e:
        raise HTTPException(status_code=502, detail=f"MedGemma error: {e}") from e
    return DocumentAnalysis(**result)


@router.post("/xray", response_model=XrayAnalysis)
async def post_xray(
    file: UploadFile = File(...),
    _: User | None = Depends(current_optional_user),
) -> XrayAnalysis:
    raw = await file.read()
    try:
        result = await analyze_xray(file.filename or "xray", raw)
    except UnsupportedMediaError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except MedGemmaError as e:
        raise HTTPException(status_code=502, detail=f"MedGemma error: {e}") from e
    return XrayAnalysis(**result)


@router.post("/mri", response_model=MriAnalysis)
async def post_mri(
    file: UploadFile = File(...),
    _: User | None = Depends(current_optional_user),
) -> MriAnalysis:
    raw = await file.read()
    try:
        result = await analyze_mri(file.filename or "mri", raw)
    except UnsupportedMediaError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except MedGemmaError as e:
        raise HTTPException(status_code=502, detail=f"MedGemma error: {e}") from e
    return MriAnalysis(**result)
