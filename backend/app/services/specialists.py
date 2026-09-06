"""
Nearest-specialist recommendation via a haversine k-nearest-neighbours index.

Given a coordinate and an optional specialty, this returns the closest doctors
from the bundled directory in ``backend/datasets/specialists.xlsx``.

Two indexes are built at training time:

  * one global index over every doctor, and
  * one index per specialty,

so the common case ("cardiologists near me") queries a small pre-built index
instead of filtering ten thousand rows at request time. A specialty we have no
exact index for falls back to a substring match plus an index fitted on the fly.

Distances use ``metric="haversine"``, which expects radians and returns radians,
hence the conversions around every query.

The trained artifact is cached to ``backend/data/specialist_knn.joblib`` and
rebuilt automatically on first use if missing. To retrain explicitly:

    python -m scripts.train_specialists
"""
from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors

log = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
DATASET_PATH = BACKEND_DIR / "datasets" / "specialists.xlsx"
MODEL_PATH = BACKEND_DIR / "data" / "specialist_knn.joblib"

EARTH_RADIUS_KM = 6371.0

# Columns the dataset must provide for the index to be buildable.
REQUIRED_COLUMNS = {
    "Doctor_ID",
    "Doctor_Name",
    "Specialty",
    "Hospital",
    "City",
    "Province",
    "Experience_Years",
    "Contact_Phone",
    "Latitude",
    "Longitude",
}

# Columns returned to callers, in order. Distance_km is computed per query.
RESULT_COLUMNS = [
    "Doctor_ID",
    "Doctor_Name",
    "Specialty",
    "Hospital",
    "City",
    "Province",
    "Experience_Years",
    "Contact_Phone",
    "Latitude",
    "Longitude",
    "Distance_km",
]


def normalize_specialty(value: Any) -> str:
    """Collapse a specialty label to a stable lookup key.

    ``"Ear, Nose & Throat"`` and ``"ear nose throat"`` both become
    ``"ear_nose_throat"`` so the per-specialty index survives punctuation and
    casing differences between the dataset and the caller.
    """
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def load_dataset(path: str | Path | None = None) -> pd.DataFrame:
    """Read the specialist directory and drop rows we cannot place on a map."""
    dataset_path = Path(path) if path else DATASET_PATH
    if not dataset_path.exists():
        raise FileNotFoundError(f"Specialist dataset not found: {dataset_path}")

    df = pd.read_excel(dataset_path)

    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(
            f"Specialist dataset is missing required columns: {', '.join(sorted(missing))}"
        )

    df = df.copy()
    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
    df = df.dropna(subset=["Latitude", "Longitude"])
    df = df[df["Latitude"].between(-90, 90) & df["Longitude"].between(-180, 180)]
    df = df.reset_index(drop=True)
    df["_specialty_key"] = df["Specialty"].map(normalize_specialty)

    if df.empty:
        raise ValueError("Specialist dataset has no rows with usable coordinates.")

    return df


def _fit_index(df: pd.DataFrame) -> NearestNeighbors:
    """Fit a haversine ball-tree over a frame's coordinates."""
    coords = np.radians(df[["Latitude", "Longitude"]].to_numpy(dtype=float))
    model = NearestNeighbors(
        n_neighbors=min(len(df), 10),
        metric="haversine",
        algorithm="ball_tree",
    )
    model.fit(coords)
    return model


def train_and_save(
    dataset_path: str | Path | None = None,
    model_path: str | Path = MODEL_PATH,
) -> Path:
    """Build the global and per-specialty indexes and persist them together."""
    df = load_dataset(dataset_path)

    specialty_models: dict[str, dict[str, Any]] = {
        key: {
            "display_name": str(group["Specialty"].iloc[0]),
            "row_indices": group.index.to_numpy(),
            "model": _fit_index(group),
        }
        for key, group in df.groupby("_specialty_key")
        if key
    }

    artifact = {
        "trained_rows": len(df),
        "data": df,
        "all_model": _fit_index(df),
        "specialty_models": specialty_models,
        "specialties": sorted(df["Specialty"].dropna().astype(str).unique().tolist()),
    }

    output_path = Path(model_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, output_path)
    log.info("Trained specialist index on %d rows -> %s", len(df), output_path)
    return output_path


@dataclass
class SpecialistRecommender:
    """Query side of the trained index."""

    training_df: pd.DataFrame
    all_model: NearestNeighbors
    specialty_models: dict[str, dict[str, Any]]
    specialties: list[str]

    @classmethod
    def from_model(cls, model_path: str | Path = MODEL_PATH) -> SpecialistRecommender:
        artifact = joblib.load(Path(model_path))
        return cls(
            training_df=artifact["data"],
            all_model=artifact["all_model"],
            specialty_models=artifact["specialty_models"],
            specialties=artifact["specialties"],
        )

    def find_nearest(
        self,
        lat: float,
        lon: float,
        specialty: str | None = None,
        k: int = 5,
    ) -> pd.DataFrame:
        """Return the ``k`` closest doctors, optionally constrained to a specialty."""
        if k <= 0:
            raise ValueError("k must be greater than 0")

        query = np.radians([[float(lat), float(lon)]])
        model = self.all_model
        candidates = self.training_df

        if specialty:
            exact = self.specialty_models.get(normalize_specialty(specialty))
            if exact:
                # Pre-built index for this specialty — the fast path.
                candidates = self.training_df.iloc[exact["row_indices"]]
                model = exact["model"]
            else:
                # Unknown label (e.g. "cardio"): substring match, then fit ad hoc.
                mask = self.training_df["Specialty"].str.contains(
                    specialty, case=False, na=False
                )
                candidates = self.training_df[mask]
                if candidates.empty:
                    return pd.DataFrame(columns=RESULT_COLUMNS)
                model = _fit_index(candidates)

        distances, indices = model.kneighbors(
            query, n_neighbors=min(k, len(candidates))
        )
        results = candidates.iloc[indices[0]].copy()
        # kneighbors returns radians for the haversine metric.
        results["Distance_km"] = distances[0] * EARTH_RADIUS_KM
        return results[RESULT_COLUMNS].reset_index(drop=True)

    def as_records(
        self,
        lat: float,
        lon: float,
        specialty: str | None = None,
        k: int = 5,
    ) -> list[dict[str, Any]]:
        """JSON-safe form of :meth:`find_nearest` for API responses."""
        results = self.find_nearest(lat=lat, lon=lon, specialty=specialty, k=k)
        records = results.replace({np.nan: None}).to_dict(orient="records")
        for row in records:
            row["Distance_km"] = round(float(row["Distance_km"]), 2)
        return records


_recommender: SpecialistRecommender | None = None
_lock = threading.Lock()


def get_recommender() -> SpecialistRecommender:
    """Load the trained index once per process, training it if absent."""
    global _recommender
    if _recommender is not None:
        return _recommender
    with _lock:
        if _recommender is None:
            if not MODEL_PATH.exists():
                log.info("No specialist index found; training from %s", DATASET_PATH)
                train_and_save()
            _recommender = SpecialistRecommender.from_model(MODEL_PATH)
    return _recommender


# --- Service API used by the routers and the chat pipeline -------------------


def list_specialties() -> list[str]:
    return get_recommender().specialties


def search(
    lat: float,
    lon: float,
    specialty: str | None = None,
    k: int = 5,
) -> list[dict[str, Any]]:
    """Return the ``k`` nearest doctors, optionally filtered by specialty."""
    return get_recommender().as_records(lat=lat, lon=lon, specialty=specialty, k=k)


def stats() -> dict[str, int]:
    rec = get_recommender()
    return {
        "trained_rows": int(len(rec.training_df)),
        "specialties": int(len(rec.specialties)),
    }
