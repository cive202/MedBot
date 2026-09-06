"""Specialist lookup endpoints.

Open to guests: a signed-out visitor can search by passing explicit
coordinates (the browser supplies them via the geolocation API). Signed-in
users may omit ``lat``/``lon`` and fall back to their saved profile location.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import current_optional_user
from app.models.user import User
from app.services import specialists

router = APIRouter(prefix="/api/location", tags=["location"])


@router.get("/specialties")
async def get_specialties() -> dict[str, list[str]]:
    """Return the specialty labels the trained index supports."""
    return {"specialties": await asyncio.to_thread(specialists.list_specialties)}


@router.get("/stats")
async def get_stats() -> dict[str, int]:
    """Row and specialty counts for the trained index."""
    return await asyncio.to_thread(specialists.stats)


@router.get("/nearby-specialists")
async def get_nearby_specialists(
    specialty: str | None = Query(None),
    lat: float | None = Query(None, ge=-90, le=90),
    lon: float | None = Query(None, ge=-180, le=180),
    k: int = Query(5, ge=1, le=25),
    user: User | None = Depends(current_optional_user),
) -> dict:
    """Top-k nearest doctors to a coordinate, optionally filtered by specialty."""
    if lat is None or lon is None:
        saved = user.location if user else None
        if not saved:
            raise HTTPException(
                status_code=400,
                detail="No location available. Share your location or pass lat/lon.",
            )
        lat = float(saved.get("lat"))
        lon = float(saved.get("lon"))

    results = await asyncio.to_thread(
        specialists.search,
        lat=lat,
        lon=lon,
        specialty=specialty or None,
        k=k,
    )
    return {
        "specialty": specialty,
        "lat": lat,
        "lon": lon,
        "k": k,
        "results": results,
    }
