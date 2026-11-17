"""Image-only VisualStat-Ridge baseline for strawberry RUL.

This module deliberately keeps the baseline small and interpretable.  It uses
only hand-crafted visual statistics from the same image sequence as the deep
models, followed by StandardScaler and L2-regularised linear regression.  It
does not use fruit ID, timestamps, elapsed time, EOL information, or sensors.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .config import TrainingConfig
from .data import build_sequence_table, extract_frame_features, load_metadata
from .engine import build_loocv_splits, compute_metrics


BASELINE_KEY = "BASELINE_RIDGE"
BASELINE_SLUG = "ridge_image_only_seq8"
RIDGE_ALPHAS: tuple[float, ...] = (0.1, 1.0, 10.0, 100.0, 1000.0)
FRAME_FEATURE_NAMES: tuple[str, ...] = (
    "r_mean",
    "g_mean",
    "b_mean",
    "r_std",
    "g_std",
    "b_std",
    "gray_mean",
    "gray_std",
    "saturation_proxy_mean",
    "value_proxy_mean",
    "gradient_mean",
    "gradient_std",
)
SEQUENCE_FEATURE_NAMES: tuple[str, ...] = tuple(
    f"{summary}_{name}"
    for summary in ("last", "mean", "delta_last_minus_first")
    for name in FRAME_FEATURE_NAMES
)


def _build_pipeline(alpha: float) -> Pipeline:
    return Pipeline(
        [
            ("standardize", StandardScaler()),
            ("ridge", Ridge(alpha=float(alpha))),
        ]
    )


def build_visual_stat_feature_table(sequence_df: pd.DataFrame) -> pd.DataFrame:
    """Create 36 visual-only features from each image sequence.

    Every frame is reduced to the existing 12 cheap RGB/texture statistics.
    The baseline then keeps the last-frame state, sequence average, and visual
    change from first to last frame.  This preserves the selected seq_len
    without adding a CNN, an RNN, timestamps, or environmental variables.
    """
    if sequence_df.empty:
        return pd.DataFrame(columns=["sample_id", "fruit_id", "target_rul_hours", *SEQUENCE_FEATURE_NAMES])
    required = {"sample_id", "fruit_id", "target_rul_hours", "image_paths"}
    missing = required.difference(sequence_df.columns)
    if missing:
        raise ValueError(f"sequence_df is missing columns: {sorted(missing)}")

    feature_rows: list[dict[str, float | str]] = []
    for row in sequence_df.itertuples(index=False):
        image_paths = tuple(getattr(row, "image_paths"))
        if not image_paths:
            raise ValueError(f"Empty image sequence for sample {getattr(row, 'sample_id')}")
        per_frame = np.stack([extract_frame_features(str(path)) for path in image_paths], axis=0)
        features = np.concatenate(
            [
                per_frame[-1],
                per_frame.mean(axis=0),
                per_frame[-1] - per_frame[0],
            ]
        ).astype(np.float32)
        feature_row: dict[str, float | str] = {
            "sample_id": str(getattr(row, "sample_id")),
            "fruit_id": str(getattr(row, "fruit_id")),
            "target_rul_hours": float(getattr(row, "target_rul_hours")),
        }
        feature_row.update({name: float(value) for name, value in zip(SEQUENCE_FEATURE_NAMES, features)})
        feature_rows.append(feature_row)
    return pd.DataFrame(feature_rows)


def _sample_indices(sequence_subset: pd.DataFrame, position_by_sample: dict[str, int]) -> np.ndarray:
    sample_ids = sequence_subset["sample_id"].astype(str).tolist()
    try:
        return np.asarray([position_by_sample[sample_id] for sample_id in sample_ids], dtype=np.int64)
    except KeyError as error:
        raise KeyError(f"Feature table is missing sample_id: {error.args[0]}") from error


def _select_alpha_with_inner_logo(
    X_train: np.ndarray,
    y_train: np.ndarray,
    train_groups: np.ndarray,
    alphas: Iterable[float] = RIDGE_ALPHAS,
) -> tuple[float, dict[str, float]]:
    """Select alpha using only fruit IDs already in the outer training set."""
    candidate_alphas = tuple(float(alpha) for alpha in alphas)
    unique_groups = np.unique(train_groups.astype(str))
    if len(unique_groups) < 2:
        return candidate_alphas[0], {str(candidate_alphas[0]): float("nan")}

    splitter = LeaveOneGroupOut()
    inner_splits = list(splitter.split(X_train, y_train, groups=train_groups))
    scores: dict[str, float] = {}
    for alpha in candidate_alphas:
        fold_mae: list[float] = []
        for fit_idx, validation_idx in inner_splits:
            model = _build_pipeline(alpha)
            model.fit(X_train[fit_idx], y_train[fit_idx])
            prediction = model.predict(X_train[validation_idx])
            fold_mae.append(float(compute_metrics(y_train[validation_idx], prediction)["mae"]))
        scores[str(alpha)] = float(np.mean(fold_mae))
    selected_alpha = min(candidate_alphas, key=lambda alpha: (scores[str(alpha)], alpha))
    return float(selected_alpha), scores


def _prediction_frame(sequence_df: pd.DataFrame, raw_prediction: np.ndarray) -> pd.DataFrame:
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
                # Match the deep-model CSV convention: display non-negative RUL,
                # while fold metrics are still calculated from raw predictions.
                "predicted_rul_hours": float(np.clip(raw_value, 0.0, None)),
                "raw_predicted_rul_hours": raw_value,
                "error_hours": float(actual - raw_value),
            }
        )
    return pd.DataFrame(rows)


def _coefficient_frame(model: Pipeline) -> pd.DataFrame:
    ridge = model.named_steps["ridge"]
    coefficients = np.asarray(ridge.coef_, dtype=np.float64).reshape(-1)
    frame = pd.DataFrame(
        {
            "feature": SEQUENCE_FEATURE_NAMES,
            "coefficient_on_standardized_feature": coefficients,
        }
    )
    frame["absolute_coefficient"] = frame["coefficient_on_standardized_feature"].abs()
    return frame.sort_values("absolute_coefficient", ascending=False).reset_index(drop=True)


def _baseline_run_root(project_root: Path, config: TrainingConfig) -> Path:
    return config.artifact_root_path(project_root) / config.run_name / "baselines" / BASELINE_SLUG


def _write_shortcut_diagnostic(sequence_df: pd.DataFrame, output_path: Path) -> pd.DataFrame:
    """Record why elapsed time is excluded from the image-only baseline."""
    diagnostic = sequence_df[["fruit_id", "target_rul_hours", "elapsed_hours_end"]].copy()
    diagnostic["rul_plus_elapsed_hours"] = diagnostic["target_rul_hours"] + diagnostic["elapsed_hours_end"]
    summary = (
        diagnostic.groupby("fruit_id", as_index=False)
        .agg(
            sequence_windows=("rul_plus_elapsed_hours", "count"),
            lifecycle_hours_mean=("rul_plus_elapsed_hours", "mean"),
            lifecycle_hours_std=("rul_plus_elapsed_hours", "std"),
        )
        .sort_values("fruit_id")
        .reset_index(drop=True)
    )
    summary.to_csv(output_path, index=False)
    return summary


def run_visual_stat_ridge_baseline(
    config: TrainingConfig,
    *,
    project_root: Path | None = None,
    alphas: Iterable[float] = RIDGE_ALPHAS,
) -> pd.DataFrame:
    """Evaluate VisualStat-Ridge with the project’s fruit-level LOOCV protocol.

    The outer held-out fruit, model-fit fruits, and validation fruit are created
    by the same split builder as A–D.  Alpha selection uses a nested LOGO only
    on the four model-fit fruits.  The reserved A–D validation fruit is logged
    but not used to select the Ridge hyperparameter.
    """
    root = (project_root or Path(__file__).resolve().parents[3]).resolve()
    candidate_alphas = tuple(float(alpha) for alpha in alphas)
    if not candidate_alphas:
        raise ValueError("At least one Ridge alpha candidate is required.")
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
        raise RuntimeError("No sequence windows were generated for the Ridge baseline.")

    feature_df = build_visual_stat_feature_table(sequence_df)
    if len(feature_df) != len(sequence_df) or not feature_df["sample_id"].equals(sequence_df["sample_id"].astype(str)):
        raise RuntimeError("Visual feature rows do not align exactly with the sequence table.")
    X = feature_df.loc[:, SEQUENCE_FEATURE_NAMES].to_numpy(dtype=np.float32)
    y = sequence_df["target_rul_hours"].to_numpy(dtype=np.float64)
    position_by_sample = {sample_id: index for index, sample_id in enumerate(sequence_df["sample_id"].astype(str))}

    baseline_root = _baseline_run_root(root, config)
    baseline_root.mkdir(parents=True, exist_ok=True)
    feature_schema = {
        "baseline_key": BASELINE_KEY,
        "description": "Visual-only sequence statistics (last, mean, last-minus-first) + StandardScaler + Ridge",
        "seq_len": config.seq_len,
        "feature_count": len(SEQUENCE_FEATURE_NAMES),
        "feature_names": list(SEQUENCE_FEATURE_NAMES),
        "excluded_inputs": ["fruit_id", "timestamp", "elapsed_hours_end", "EOL", "sensor values"],
        "alpha_candidates": list(candidate_alphas),
        "metric_prediction_convention": "Metrics use raw Ridge predictions; prediction CSV also carries non-negative deployment display values.",
    }
    (baseline_root / "feature_schema.json").write_text(json.dumps(feature_schema, indent=2), encoding="utf-8")
    lifecycle_summary = _write_shortcut_diagnostic(sequence_df, baseline_root / "elapsed_time_shortcut_diagnostic.csv")

    fold_rows: list[dict[str, object]] = []
    for fold_split in build_loocv_splits(sequence_df, BASELINE_KEY):
        train_idx = _sample_indices(fold_split.train_sequence_df, position_by_sample)
        val_idx = _sample_indices(fold_split.val_sequence_df, position_by_sample)
        test_idx = _sample_indices(fold_split.test_sequence_df, position_by_sample)
        alpha, inner_scores = _select_alpha_with_inner_logo(
            X[train_idx],
            y[train_idx],
            fold_split.train_sequence_df["fruit_id"].astype(str).to_numpy(),
            candidate_alphas,
        )
        model = _build_pipeline(alpha)
        model.fit(X[train_idx], y[train_idx])

        val_prediction = model.predict(X[val_idx])
        test_prediction = model.predict(X[test_idx])
        val_metrics = compute_metrics(y[val_idx], val_prediction)
        test_metrics = compute_metrics(y[test_idx], test_prediction)

        fold_root = baseline_root / fold_split.fold_name
        fold_root.mkdir(parents=True, exist_ok=True)
        prediction_path = fold_root / "predictions.csv"
        _prediction_frame(fold_split.test_sequence_df, test_prediction).to_csv(prediction_path, index=False)
        coefficients_path = fold_root / "feature_coefficients.csv"
        _coefficient_frame(model).to_csv(coefficients_path, index=False)
        metrics_payload = {
            "model_key": BASELINE_KEY,
            "baseline_name": "VisualStat-Ridge (image-only sequence)",
            "fold_name": fold_split.fold_name,
            "test_group": fold_split.test_group,
            "val_group": fold_split.val_group,
            "fit_groups": list(fold_split.train_groups),
            "selected_alpha": alpha,
            "inner_logo_mae_by_alpha": inner_scores,
            "validation_metrics": val_metrics,
            "test_metrics": test_metrics,
            "feature_count": len(SEQUENCE_FEATURE_NAMES),
            "feature_schema_path": str((baseline_root / "feature_schema.json")),
            "prediction_path": str(prediction_path),
            "coefficients_path": str(coefficients_path),
        }
        metrics_path = fold_root / "metrics.json"
        metrics_path.write_text(json.dumps(metrics_payload, indent=2, default=str), encoding="utf-8")
        fold_rows.append(
            {
                "model_key": BASELINE_KEY,
                "model_name": "VisualStat-Ridge (image-only sequence)",
                "fold_name": fold_split.fold_name,
                "test_group": fold_split.test_group,
                "val_group": fold_split.val_group,
                "best_epoch": 0,
                "best_val_mae": float(val_metrics["mae"]),
                "test_mae": float(test_metrics["mae"]),
                "test_rmse": float(test_metrics["rmse"]),
                "test_r2": float(test_metrics["r2"]),
                "test_smape": float(test_metrics["smape"]),
                "selected_alpha": alpha,
                "feature_count": len(SEQUENCE_FEATURE_NAMES),
                "fit_groups": ",".join(fold_split.train_groups),
                "metrics_path": str(metrics_path),
                "prediction_path": str(prediction_path),
                "coefficients_path": str(coefficients_path),
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
                "baseline_key": BASELINE_KEY,
                "baseline_name": "VisualStat-Ridge (image-only sequence)",
                "source_run_name": config.run_name,
                "feature_schema": feature_schema,
                "fold_results": fold_results.to_dict(orient="records"),
                "summary": summary.to_dict(orient="records"),
                "elapsed_time_shortcut_diagnostic": lifecycle_summary.to_dict(orient="records"),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    return fold_results
