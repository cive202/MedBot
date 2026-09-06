"""
Train the nearest-specialist KNN index.

The backend trains this automatically the first time it is needed, so running
this by hand is only necessary after changing the dataset.

    python -m scripts.train_specialists
    python -m scripts.train_specialists --lat 27.7172 --lon 85.3240 --specialty cardiology
"""
from __future__ import annotations

import argparse

from app.services import specialists


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        default=None,
        help=f"Path to the .xlsx directory (default: {specialists.DATASET_PATH})",
    )
    parser.add_argument(
        "--model",
        default=str(specialists.MODEL_PATH),
        help="Where to write the .joblib artifact.",
    )
    parser.add_argument("--lat", type=float, help="Latitude for a smoke-test query.")
    parser.add_argument("--lon", type=float, help="Longitude for a smoke-test query.")
    parser.add_argument("--specialty", default=None, help="Specialty for the smoke test.")
    parser.add_argument("--k", type=int, default=5, help="Results for the smoke test.")
    args = parser.parse_args()

    output_path = specialists.train_and_save(
        dataset_path=args.dataset, model_path=args.model
    )
    recommender = specialists.SpecialistRecommender.from_model(output_path)
    print(f"Trained on {len(recommender.training_df)} doctors.")
    print(f"Specialties: {len(recommender.specialties)}")
    print(f"Saved: {output_path}")

    if args.lat is not None and args.lon is not None:
        print()
        results = recommender.find_nearest(
            lat=args.lat, lon=args.lon, specialty=args.specialty, k=args.k
        )
        print(results.to_string(index=False))


if __name__ == "__main__":
    main()
