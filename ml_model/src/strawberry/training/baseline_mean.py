"""Train-mean, no-input baseline for strawberry RUL.

This is deliberately the smallest possible reference: for each outer
Leave-One-Fruit-Out fold it predicts the pooled mean RUL of only the four
fruit groups used to fit A--D and VisualStat-Ridge.  It consumes no image,
metadata, sensor, fruit ID, timestamp, or test/validation target.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import TrainingConfig
from .data import build_sequence_table, load_metadata
from .engine import build_loocv_splits, compute_metrics


BASELINE_KEY = "BASELINE_TRAIN_MEAN"
BASELINE_SLUG = "train_mean_no_input_seq8"
BASELINE_NAME = "Train-mean predictor (no input)"


def _baseline_run_root(project_root: Path, config: TrainingConfig) -> Path:
    return config.artifact_root_path(project_root) / config.run_name / "baselines" / BASELINE_SLUG


def _prediction_frame(sequence_df: pd.DataFrame, raw_prediction: np.ndarray) -> pd.DataFrame:
    """Write the same held-out prediction columns used by the other models."""
    rows: list[dict[str, object]] = []
    for row, predicted in zip(sequence_df.itertuples(index=False), raw_prediction):
        actual = float(getattr(row, "target_rul_hours"))
        raw_value = float(predicted)
        rows.append(
            {
                "sample_id": str(getattr(row, "sample_id")),
                "fruit_id": str(getattr(row, "fruit_id")),
                "split": str(getattr(row, "split", "")),
                "start_timestamp": pd.Timestamp(getattr(row, "start_timestamp")).isoformat(),
                "end_timestamp": pd.Timestamp(getattr(row, "end_timestamp")).isoformat(),
                "actual_rul_hours": actual,
                "predicted_rul_hours": raw_value,
                "raw_predicted_rul_hours": raw_value,
                "error_hours": float(actual - raw_value),
            }
        )
    return pd.DataFrame(rows)


def run_train_mean_baseline(
    config: TrainingConfig,
    *,
    project_root: Path | None = None,
) -> pd.DataFrame:
    """Evaluate a leakage-safe train-mean lower-bound using project LOFO splits.

    `build_loocv_splits` reserves one validation fruit and exposes exactly four
    fit fruits.  The constant is the pooled-window target mean over those fit
    fruits only.  The validation metric is recorded as a diagnostic; there is
    no tuning or fitted feature transform.
    """
    root = (project_root or Path(__file__).resolve().parents[3]).resolve()
    split_root = root / "data" / "03_split" / "strawberry"
    metadata_path = split_root / "metadata.csv"
    frame_df = load_metadata(metadata_path, project_root=root, split_root=split_root)
    sequence_df = build_sequence_table(
        frame_df,
        config.seq_len,
        max_gap_hours=config.max_gap_hours,
        pre_eol_only=True,
    )
    if sequence_df.empty:
        raise RuntimeError("No sequence windows were generated for the train-mean baseline.")

    baseline_root = _baseline_run_root(root, config)
    baseline_root.mkdir(parents=True, exist_ok=True)
    definition = {
        "baseline_key": BASELINE_KEY,
        "baseline_name": BASELINE_NAME,
        "slug": BASELINE_SLUG,
        "input_modality": "none (target-only training reference)",
        "prediction_rule": "For each outer LOFO fold, predict the pooled mean target_rul_hours from only the four model-fit fruits.",
        "seq_len": config.seq_len,
        "sequence_construction": "Matches the project sequence table (pre_eol_only=True). Images and all metadata are ignored by the predictor.",
        "excluded_from_fit": ["outer held-out fruit", "reserved validation fruit", "image pixels", "fruit_id", "timestamp", "elapsed time", "sensor values"],
        "metric_prediction_convention": "Metrics use the raw constant prediction, matching the A-D fold-metric convention.",
    }
    (baseline_root / "baseline_definition.json").write_text(json.dumps(definition, indent=2), encoding="utf-8")

    fold_rows: list[dict[str, object]] = []
    for fold_split in build_loocv_splits(sequence_df, BASELINE_KEY):
        y_train = fold_split.train_sequence_df["target_rul_hours"].to_numpy(dtype=np.float64)
        y_val = fold_split.val_sequence_df["target_rul_hours"].to_numpy(dtype=np.float64)
        y_test = fold_split.test_sequence_df["target_rul_hours"].to_numpy(dtype=np.float64)
        if len(y_train) == 0 or not np.isfinite(y_train).all():
            raise RuntimeError(f"Invalid fit targets in {fold_split.fold_name}")
        if len(y_val) == 0 or len(y_test) == 0:
            raise RuntimeError(f"Empty validation or held-out targets in {fold_split.fold_name}")

        train_target_mean = float(np.mean(y_train))
        val_prediction = np.full(len(y_val), train_target_mean, dtype=np.float64)
        test_prediction = np.full(len(y_test), train_target_mean, dtype=np.float64)
        val_metrics = compute_metrics(y_val, val_prediction)
        test_metrics = compute_metrics(y_test, test_prediction)

        fold_root = baseline_root / fold_split.fold_name
        fold_root.mkdir(parents=True, exist_ok=True)
        prediction_path = fold_root / "predictions.csv"
        _prediction_frame(fold_split.test_sequence_df, test_prediction).to_csv(prediction_path, index=False)
        metrics_payload = {
            "model_key": BASELINE_KEY,
            "baseline_name": BASELINE_NAME,
            "fold_name": fold_split.fold_name,
            "test_group": fold_split.test_group,
            "val_group": fold_split.val_group,
            "fit_groups": list(fold_split.train_groups),
            "train_target_mean_hours": train_target_mean,
            "n_train_windows": int(len(y_train)),
            "n_val_windows": int(len(y_val)),
            "n_test_windows": int(len(y_test)),
            "validation_metrics": val_metrics,
            "test_metrics": test_metrics,
            "prediction_path": str(prediction_path),
        }
        metrics_path = fold_root / "metrics.json"
        metrics_path.write_text(json.dumps(metrics_payload, indent=2, default=str), encoding="utf-8")
        fold_rows.append(
            {
                "model_key": BASELINE_KEY,
                "model_name": BASELINE_NAME,
                "fold_name": fold_split.fold_name,
                "test_group": fold_split.test_group,
                "val_group": fold_split.val_group,
                "best_epoch": 0,
                "best_val_mae": float(val_metrics["mae"]),
                "test_mae": float(test_metrics["mae"]),
                "test_rmse": float(test_metrics["rmse"]),
                "test_r2": float(test_metrics["r2"]),
                "test_smape": float(test_metrics["smape"]),
                "train_target_mean_hours": train_target_mean,
                "n_train_windows": int(len(y_train)),
                "n_val_windows": int(len(y_val)),
                "n_test_windows": int(len(y_test)),
                "fit_groups": ",".join(fold_split.train_groups),
                "metrics_path": str(metrics_path),
                "prediction_path": str(prediction_path),
            }
        )

    fold_results = pd.DataFrame(fold_rows).sort_values("test_group").reset_index(drop=True)
    fold_results.to_csv(baseline_root / "fold_results.csv", index=False)
    summary = (
        fold_results.groupby("model_key", as_index=False)
        .agg(
            folds=("fold_name", "count"),
            val_mae_mean=("best_val_mae", "mean"),
            val_mae_std=("best_val_mae", "std"),
            test_mae_mean=("test_mae", "mean"),
            test_mae_std=("test_mae", "std"),
            test_rmse_mean=("test_rmse", "mean"),
            test_rmse_std=("test_rmse", "std"),
            test_r2_mean=("test_r2", "mean"),
            test_r2_std=("test_r2", "std"),
            test_smape_mean=("test_smape", "mean"),
        )
        .reset_index(drop=True)
    )
    summary.to_csv(baseline_root / "model_summary.csv", index=False)
    (baseline_root / "summary.json").write_text(
        json.dumps(
            {
                "baseline_definition": definition,
                "source_run_name": config.run_name,
                "fold_results": fold_results.to_dict(orient="records"),
                "summary": summary.to_dict(orient="records"),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    return fold_results
