"""Operational Non-Deep-Learning Baselines for Strawberry RUL Prediction.

Implements two standard perishable inventory operations heuristics requested by reviewers:
1. BASELINE_FIFO_COUNTDOWN: Fixed-Lifespan / Age-based Countdown (standard FIFO date-coding heuristic).
   Predicted RUL(t) = max(0, Mean_Train_Lifespan - elapsed_time)
2. BASELINE_ENV_KINETIC: Temperature-compensated kinetic degradation baseline (Ridge on elapsed_time + temperature).

Both are evaluated under strict 6-fold Leave-One-Fruit-Out Cross-Validation (LOOCV),
reporting fold-level metrics and 95% confidence intervals.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import Ridge

from .config import TrainingConfig
from .data import build_sequence_table, load_metadata
from .engine import build_loocv_splits, compute_metrics


def _calc_ci(values: np.ndarray, alpha: float = 0.05) -> tuple[float, float, float, float]:
    n = len(values)
    mean = float(np.mean(values))
    std = float(np.std(values, ddof=1)) if n > 1 else 0.0
    se = std / np.sqrt(n) if n > 0 else 0.0
    t_val = float(stats.t.ppf(1.0 - alpha / 2.0, df=n - 1)) if n > 1 else 0.0
    ci_low = mean - t_val * se
    ci_high = mean + t_val * se
    return mean, std, ci_low, ci_high


def run_operational_baselines(
    config: TrainingConfig,
    *,
    project_root: Path | None = None,
) -> dict[str, pd.DataFrame]:
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
        raise RuntimeError("No sequence windows were generated.")

    out_base = root / "baseline_results" / "operational_baselines"
    out_base.mkdir(parents=True, exist_ok=True)

    splits = build_loocv_splits(sequence_df, "OPERATIONAL")

    # Baseline 1: FIFO Fixed-Lifespan Countdown
    fifo_fold_records = []
    # Baseline 2: Kinetic (Elapsed Time + Temperature)
    kinetic_fold_records = []

    for s in splits:
        train_df = s.train_sequence_df
        test_df = s.test_sequence_df
        y_test = test_df["target_rul_hours"].to_numpy(dtype=np.float64)
        elapsed_test = test_df["elapsed_hours_end"].to_numpy(dtype=np.float64)

        # 1. FIFO Countdown: compute mean total lifespan across the 4 training fruits
        train_lifespans = [
            grp["target_rul_hours"].max() + grp["elapsed_hours_end"].min()
            for _, grp in train_df.groupby("fruit_id")
        ]
        mean_lifespan = float(np.mean(train_lifespans))
        pred_fifo = np.maximum(0.0, mean_lifespan - elapsed_test)
        m_fifo = compute_metrics(y_test, pred_fifo)

        fifo_fold_records.append(
            {
                "model_key": "BASELINE_FIFO_COUNTDOWN",
                "model_name": "Age-based FIFO Countdown",
                "fold_name": s.fold_name,
                "test_group": s.test_group,
                "val_group": s.val_group,
                "fit_groups": ",".join(s.train_groups),
                "nominal_lifespan_hours": mean_lifespan,
                "test_mae": m_fifo["mae"],
                "test_rmse": m_fifo["rmse"],
                "test_r2": m_fifo["r2"],
                "test_smape": m_fifo["smape"],
                "n_test_windows": len(test_df),
            }
        )

        # 2. Kinetic model: Ridge on elapsed time + mean sequence temperature
        t_seq_train = train_df["temperature_seq"].apply(lambda arr: float(np.mean(arr))).to_numpy()
        X_train = np.column_stack([train_df["elapsed_hours_end"].to_numpy(), t_seq_train])
        y_train = train_df["target_rul_hours"].to_numpy(dtype=np.float64)

        t_seq_test = test_df["temperature_seq"].apply(lambda arr: float(np.mean(arr))).to_numpy()
        X_test = np.column_stack([elapsed_test, t_seq_test])

        ridge = Ridge(alpha=1.0)
        ridge.fit(X_train, y_train)
        pred_kinetic = np.maximum(0.0, ridge.predict(X_test))
        m_kinetic = compute_metrics(y_test, pred_kinetic)

        kinetic_fold_records.append(
            {
                "model_key": "BASELINE_ENV_KINETIC",
                "model_name": "Kinetic Degradation (Time + Temp)",
                "fold_name": s.fold_name,
                "test_group": s.test_group,
                "val_group": s.val_group,
                "fit_groups": ",".join(s.train_groups),
                "intercept": float(ridge.intercept_),
                "coef_elapsed": float(ridge.coef_[0]),
                "coef_temp": float(ridge.coef_[1]),
                "test_mae": m_kinetic["mae"],
                "test_rmse": m_kinetic["rmse"],
                "test_r2": m_kinetic["r2"],
                "test_smape": m_kinetic["smape"],
                "n_test_windows": len(test_df),
            }
        )

    df_fifo = pd.DataFrame(fifo_fold_records)
    df_kinetic = pd.DataFrame(kinetic_fold_records)

    df_fifo.to_csv(out_base / "fifo_countdown_folds.csv", index=False)
    df_kinetic.to_csv(out_base / "kinetic_folds.csv", index=False)

    return {"fifo": df_fifo, "kinetic": df_kinetic}


if __name__ == "__main__":
    cfg = TrainingConfig()
    results = run_operational_baselines(cfg)
    print("Operational baselines computed successfully.")
