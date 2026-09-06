"""
Train (and benchmark) the disease classifier.

Improvements over v1:
  * Stratified 5-fold cross-validation reporting **top-1, top-3, top-5** accuracy
    plus macro-F1 and log-loss. Top-K is the clinically meaningful metric —
    a differential diagnosis is "useful" when the true disease is in the top
    handful of candidates.
  * Compares **RandomForest** vs **HistGradientBoosting** (built into sklearn,
    no extra dep). Often boosting edges RF on this dataset shape.
  * Optional **RandomizedSearchCV** hyperparameter search (`--search`).
  * Optional probability **calibration** (`--calibrate isotonic|sigmoid`) so
    the probabilities the chat surfaces aren't wildly over/under-confident.
  * Optional **deduplication** (`--dedup`) — off by default because the
    Kaggle dataset has many near-identical rows per disease and dedup
    shrinks it to ~1 row per class.
  * Persists model + metadata + metrics to `backend/data/`.

Usage:
  python -m scripts.train_rf --csv Training.csv
  python -m scripts.train_rf --csv Training.csv --algo both --search
  python -m scripts.train_rf --csv Training.csv --test Testing.csv --calibrate isotonic
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import (
    classification_report,
    f1_score,
    log_loss,
    top_k_accuracy_score,
)
from sklearn.model_selection import (
    RandomizedSearchCV,
    StratifiedKFold,
    cross_val_predict,
    train_test_split,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
MODEL_PATH = DATA_DIR / "rf_model.joblib"
METRICS_PATH = DATA_DIR / "rf_metrics.json"
# Label column names seen across the public symptom datasets. "diseases" is
# what the large Kaggle set uses; "prognosis" is the small 41-disease one.
LABEL_COL_CANDIDATES = [
    "prognosis", "diseases", "Diseases", "Disease", "disease", "label", "target",
]


def load_df(path: Path, label_col: str | None = None) -> tuple[pd.DataFrame, str]:
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    if label_col is None:
        label_col = next((c for c in LABEL_COL_CANDIDATES if c in df.columns), None)
    elif label_col not in df.columns:
        raise SystemExit(f"Column {label_col!r} not found in {path}.")
    if label_col is None:
        raise SystemExit(
            f"Could not find a label column in {path}. Expected one of "
            f"{LABEL_COL_CANDIDATES}, or pass --label-col."
        )
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
    return df, label_col


def drop_rare_classes(df: pd.DataFrame, label_col: str, min_count: int) -> pd.DataFrame:
    """Drop classes with too few examples to appear in every CV fold.

    Stratified 5-fold cross-validation needs at least 5 examples per class.
    Rarer ones cannot be scored meaningfully — they land in some folds and not
    others — and their presence makes the reported metrics misleading rather
    than merely noisy.
    """
    if min_count <= 1:
        return df
    counts = df[label_col].value_counts()
    rare = counts[counts < min_count].index
    if len(rare) == 0:
        return df
    print(
        f"  Dropping {len(rare)} class(es) with <{min_count} examples "
        f"({int(counts[rare].sum())} rows); {df[label_col].nunique() - len(rare)} classes remain."
    )
    return df[~df[label_col].isin(rare)].reset_index(drop=True)


def maybe_dedup(df: pd.DataFrame, label_col: str, do_it: bool) -> pd.DataFrame:
    if not do_it:
        return df
    before = len(df)
    df2 = df.drop_duplicates()
    print(f"  Dedup: {before} -> {len(df2)} rows ({before - len(df2)} duplicates dropped).")
    counts = df2[label_col].value_counts()
    rare = counts[counts < 2].index.tolist()
    if rare:
        print(f"  Dropping {len(rare)} class(es) with <2 examples after dedup: {rare}")
        df2 = df2[~df2[label_col].isin(rare)]
    return df2


def topk_safe(y_true: np.ndarray, proba: np.ndarray, classes: np.ndarray, k: int) -> float:
    """top_k_accuracy_score that won't error when k > n_classes."""
    k = max(1, min(k, len(classes)))
    return top_k_accuracy_score(y_true, proba, k=k, labels=classes)


def cv_report(
    name: str, model: Any, X: np.ndarray, y: np.ndarray, classes: np.ndarray
) -> dict[str, float]:
    print(f"\n--- {name} (5-fold CV) ---")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    proba = cross_val_predict(model, X, y, cv=cv, method="predict_proba", n_jobs=-1)
    pred = classes[proba.argmax(axis=1)]
    res = {
        "top1": topk_safe(y, proba, classes, 1),
        "top3": topk_safe(y, proba, classes, 3),
        "top5": topk_safe(y, proba, classes, 5),
        "macro_f1": float(f1_score(y, pred, average="macro", zero_division=0)),
        "log_loss": float(log_loss(y, proba, labels=classes)),
    }
    for k, v in res.items():
        print(f"  {k:>9}: {v:.4f}")
    return res


def holdout_report(
    name: str, model: Any, X: np.ndarray, y: np.ndarray, seed: int
) -> dict[str, float]:
    """Score on a single stratified 80/20 split instead of 5-fold CV.

    Cross-validation fits the forest five times and materialises an
    (n_rows x n_classes) probability matrix. With a quarter-million rows and
    hundreds of classes that matrix alone runs to gigabytes, which is why this
    is the default for the large dataset. One split gives the same top-k
    metrics at a fifth of the cost.
    """
    print(f"\n--- {name} (holdout 80/20) ---")
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=seed
    )
    model.fit(X_tr, y_tr)
    proba = model.predict_proba(X_te)
    classes = model.classes_
    pred = classes[proba.argmax(axis=1)]
    res = {
        "top1": topk_safe(y_te, proba, classes, 1),
        "top3": topk_safe(y_te, proba, classes, 3),
        "top5": topk_safe(y_te, proba, classes, 5),
        "macro_f1": float(f1_score(y_te, pred, average="macro", zero_division=0)),
        "log_loss": float(log_loss(y_te, proba, labels=classes)),
    }
    for k, v in res.items():
        print(f"  {k:>9}: {v:.4f}")
    return res


def search_rf(X: np.ndarray, y: np.ndarray, n_iter: int, seed: int) -> RandomForestClassifier:
    print("  RandomizedSearchCV (RandomForest)...")
    base = RandomForestClassifier(n_jobs=-1, class_weight="balanced", random_state=seed)
    space = {
        "n_estimators": [200, 400, 600, 800],
        "max_depth": [None, 10, 20, 30],
        "min_samples_split": [2, 4, 8],
        "min_samples_leaf": [1, 2, 4],
        "max_features": ["sqrt", "log2", 0.5],
    }
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    search = RandomizedSearchCV(
        base, space, n_iter=n_iter, cv=cv, scoring="neg_log_loss",
        n_jobs=-1, random_state=seed, verbose=1,
    )
    search.fit(X, y)
    print(f"  Best RF params: {search.best_params_}")
    return search.best_estimator_


def search_hgb(X: np.ndarray, y: np.ndarray, n_iter: int, seed: int) -> HistGradientBoostingClassifier:
    print("  RandomizedSearchCV (HistGradientBoosting)...")
    base = HistGradientBoostingClassifier(random_state=seed)
    space = {
        "max_iter": [200, 400, 600],
        "max_depth": [None, 6, 10],
        "learning_rate": [0.03, 0.05, 0.1],
        "min_samples_leaf": [5, 10, 20],
        "l2_regularization": [0.0, 0.1, 1.0],
    }
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    search = RandomizedSearchCV(
        base, space, n_iter=n_iter, cv=cv, scoring="neg_log_loss",
        n_jobs=-1, random_state=seed, verbose=1,
    )
    search.fit(X, y)
    print(f"  Best HGB params: {search.best_params_}")
    return search.best_estimator_


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, type=Path, help="Training CSV path.")
    parser.add_argument("--test", type=Path, default=None, help="Optional held-out test CSV.")
    parser.add_argument("--algo", choices=["rf", "hgb", "both"], default="both",
                        help="Which classifier(s) to train. 'both' = compare and keep the best.")
    parser.add_argument("--search", action="store_true",
                        help="Run RandomizedSearchCV for the chosen algorithm(s).")
    parser.add_argument("--n-iter", type=int, default=20,
                        help="RandomizedSearchCV iteration budget per algorithm.")
    parser.add_argument("--calibrate", choices=["none", "isotonic", "sigmoid"], default="isotonic",
                        help="Probability calibration. Isotonic is non-parametric and usually best.")
    parser.add_argument("--dedup", action="store_true",
                        help="Drop duplicate (features+label) rows. WARNING: Kaggle Training.csv "
                             "has many near-identical rows per disease; dedup shrinks it heavily.")
    parser.add_argument("--label-col", default=None,
                        help="Label column name. Auto-detected when omitted.")
    parser.add_argument("--min-class-count", type=int, default=5,
                        help="Drop classes with fewer examples than this (default 5, "
                             "the CV fold count). Set to 1 to keep everything.")
    parser.add_argument("--seed", type=int, default=42)
    # Forest size/shape knobs. Defaults suit the small 41-disease Kaggle set;
    # scripts/train_kaggle_rf.py lowers them for the 250k-row variant so the
    # artifact stays a sane size. Ignored when --search is set, since the
    # search explores these itself.
    parser.add_argument("--n-estimators", type=int, default=600,
                        help="Trees in the forest. Fewer = smaller artifact, faster training.")
    parser.add_argument("--max-depth", type=int, default=None,
                        help="Max tree depth. None grows until leaves are pure.")
    parser.add_argument("--max-samples", type=float, default=None,
                        help="Fraction of rows each tree is fitted on (bootstrap sub-sampling).")
    parser.add_argument("--min-samples-leaf", type=int, default=1,
                        help="Minimum samples per leaf. Raising this is the most effective "
                             "way to shrink the model: every node stores one float per "
                             "class, so with many classes node count dominates memory.")
    parser.add_argument("--class-weight", choices=["none", "balanced"], default="balanced",
                        help="'balanced' up-weights rare classes by inverse frequency. On a "
                             "long-tailed set with hundreds of diseases that can be a 70x "
                             "multiplier, which pushes rare conditions to the top of the "
                             "differential for everyday symptoms. Use 'none' there.")
    parser.add_argument("--eval", choices=["cv", "holdout", "none"], default="cv",
                        help="How to score candidates. 'cv' is 5-fold; 'holdout' is a "
                             "single 80/20 split (far cheaper on large, many-class data); "
                             "'none' skips scoring and just fits.")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading {args.csv}...")
    df, label_col = load_df(args.csv, args.label_col)
    df = maybe_dedup(df, label_col, args.dedup)
    df = drop_rare_classes(df, label_col, args.min_class_count)

    feature_cols = [c for c in df.columns if c != label_col]
    X = df[feature_cols].astype(np.int8).to_numpy()
    y = df[label_col].astype(str).to_numpy()
    classes = np.array(sorted(set(y)))

    print(f"Rows: {X.shape[0]}, features: {X.shape[1]}, classes: {len(classes)}")

    candidates: dict[str, Any] = {}
    if args.algo in ("rf", "both"):
        candidates["rf"] = (
            search_rf(X, y, args.n_iter, args.seed)
            if args.search
            else RandomForestClassifier(
                n_estimators=args.n_estimators, max_depth=args.max_depth,
                max_samples=args.max_samples, min_samples_leaf=args.min_samples_leaf,
                max_features="sqrt",
                class_weight=None if args.class_weight == "none" else "balanced",
                n_jobs=-1, random_state=args.seed,
            )
        )
    if args.algo in ("hgb", "both"):
        candidates["hgb"] = (
            search_hgb(X, y, args.n_iter, args.seed)
            if args.search
            else HistGradientBoostingClassifier(
                max_iter=400, learning_rate=0.05, min_samples_leaf=10,
                random_state=args.seed,
            )
        )

    cv_results: dict[str, dict[str, float]] = {}
    for name, model in candidates.items():
        if args.eval == "cv":
            cv_results[name] = cv_report(name, model, X, y, classes)
        elif args.eval == "holdout":
            cv_results[name] = holdout_report(name, model, X, y, args.seed)

    # Winner by top-3 accuracy (most clinically meaningful for a differential).
    if cv_results:
        best_name = max(cv_results, key=lambda n: cv_results[n]["top3"])
        print(f"\n>>> Winner by top-3 accuracy: {best_name} ({cv_results[best_name]['top3']:.4f})")
    else:
        best_name = next(iter(candidates))
    best_model = candidates[best_name]

    if args.calibrate != "none":
        print(f"\nCalibrating with {args.calibrate}...")
        X_tr, X_cal, y_tr, y_cal = train_test_split(
            X, y, test_size=0.2, stratify=y, random_state=args.seed
        )
        best_model.fit(X_tr, y_tr)
        final_model = CalibratedClassifierCV(best_model, method=args.calibrate, cv="prefit")
        final_model.fit(X_cal, y_cal)
    else:
        best_model.fit(X, y)
        final_model = best_model

    if args.test:
        df_t, lc_t = load_df(args.test)
        df_t = df_t[feature_cols + [lc_t]]
        X_te = df_t[feature_cols].astype(np.int8).to_numpy()
        y_te = df_t[lc_t].astype(str).to_numpy()
        proba = final_model.predict_proba(X_te)
        pred = final_model.classes_[proba.argmax(axis=1)]
        print("\n--- Held-out test set ---")
        print(classification_report(y_te, pred, zero_division=0))
        cv_results["holdout"] = {
            "top1": topk_safe(y_te, proba, final_model.classes_, 1),
            "top3": topk_safe(y_te, proba, final_model.classes_, 3),
            "top5": topk_safe(y_te, proba, final_model.classes_, 5),
        }

    bundle = {
        "model": final_model,
        "features": feature_cols,
        "classes": list(final_model.classes_),
        "algo": best_name,
        "calibration": args.calibrate,
        "metrics": cv_results,
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    joblib.dump(bundle, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(cv_results, indent=2))
    print(f"\nSaved model   -> {MODEL_PATH}")
    print(f"Saved metrics -> {METRICS_PATH}")


if __name__ == "__main__":
    main()
