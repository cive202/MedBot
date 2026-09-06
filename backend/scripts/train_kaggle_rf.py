"""
One-shot wrapper around `scripts.train_rf` for the Kaggle
`dhivyeshrk/diseases-and-symptoms-dataset` CSV.

Usage (after dropping the file at backend/data/Diseases_Symptoms.csv):

    python -m scripts.train_kaggle_rf

Or with a custom path:

    python -m scripts.train_kaggle_rf --csv path/to/your.csv

Defaults are tuned for the ~250k-row × 377-symptom × ~720-class dataset on a
machine with modest RAM.

The binding constraint is class count, not row count. A decision tree stores one
float per class at every node, so with ~720 classes a deep forest costs
gigabytes before it finishes fitting. The defaults below trade a little accuracy
for a model that trains and loads on an 8 GB laptop:

    --n-estimators 60  --max-depth 18  --min-samples-leaf 8  --max-samples 0.3
    --eval holdout     --calibrate none

Raise them if you have the headroom; --search explores the space properly.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
# Auto-detect the Kaggle CSV — supports the common filenames the dataset ships with.
_KNOWN_NAMES = (
    "Final_Augmented_dataset_Diseases_and_Symptoms.csv",
    "Diseases_Symptoms.csv",
    "diseases_and_symptoms.csv",
)
DEFAULT_CSV = next(
    (BACKEND / "data" / n for n in _KNOWN_NAMES if (BACKEND / "data" / n).exists()),
    BACKEND / "data" / _KNOWN_NAMES[0],
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--n-estimators", type=int, default=60)
    parser.add_argument("--max-depth", type=int, default=18)
    parser.add_argument("--max-samples", type=float, default=0.3)
    parser.add_argument("--min-samples-leaf", type=int, default=8)
    parser.add_argument("--calibrate", choices=["none", "isotonic", "sigmoid"],
                        default="none",
                        help="Probability calibration. Off by default here: with ~770 "
                             "classes it costs far more than the ranking gains.")
    parser.add_argument("--eval", choices=["cv", "holdout", "none"], default="holdout",
                        help="Scoring strategy (default: holdout, see train_rf.py).")
    parser.add_argument("--class-weight", choices=["none", "balanced"], default="none",
                        help="Off by default here: this set is long-tailed across ~720 "
                             "classes, and inverse-frequency weighting surfaces rare "
                             "conditions for everyday symptoms.")
    args = parser.parse_args()

    if not args.csv.exists():
        sys.exit(
            f"CSV not found: {args.csv}\n"
            "Download from https://www.kaggle.com/datasets/dhivyeshrk/diseases-and-symptoms-dataset "
            "and drop the .csv at backend/data/."
        )

    cmd = [
        sys.executable, "-m", "scripts.train_rf",
        "--csv", str(args.csv),
        # Forest only. This dataset has ~770 classes, and gradient boosting
        # fits one tree per class per iteration, so --algo both would mean
        # hundreds of thousands of trees for the losing candidate alone.
        "--algo", "rf",
        "--n-estimators", str(args.n_estimators),
        "--max-depth", str(args.max_depth),
        "--max-samples", str(args.max_samples),
        "--min-samples-leaf", str(args.min_samples_leaf),
        "--calibrate", args.calibrate,
        "--class-weight", args.class_weight,
        # 5-fold CV would fit the forest five times and build a
        # (247k x 721) probability matrix; a single split measures the same
        # thing for a fraction of the memory.
        "--eval", args.eval,
    ]
    print("[train_kaggle_rf] running:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=BACKEND)


if __name__ == "__main__":
    main()
