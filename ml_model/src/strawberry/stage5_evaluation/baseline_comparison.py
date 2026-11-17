"""Report the VisualStat-Ridge baseline beside the existing strawberry A–D run.

The report is deliberately written to a separate directory so existing A–D
artifacts and their published comparison report remain unchanged.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from strawberry.training.baseline_ridge import BASELINE_KEY, BASELINE_SLUG

from .common import MODEL_REGISTRY, PROJECT_ROOT, resolve_run_root


BASELINE_LABEL = "VisualStat-Ridge (36 visual sequence statistics)"
BASELINE_COLOR = "#616161"
DEEP_KEYS = ("A", "B", "C", "D")


def _baseline_root(run_root: Path) -> Path:
    return run_root / "baselines" / BASELINE_SLUG


def _summarize(fold_results: pd.DataFrame) -> pd.DataFrame:
    return (
        fold_results.groupby("model_key", as_index=False)
        .agg(
            folds=("fold_name", "count"),
            test_mae_mean=("test_mae", "mean"),
            test_mae_std=("test_mae", "std"),
            test_rmse_mean=("test_rmse", "mean"),
            test_r2_mean=("test_r2", "mean"),
            test_smape_mean=("test_smape", "mean"),
        )
        .reset_index(drop=True)
    )


def _display_label(model_key: str) -> str:
    if model_key == BASELINE_KEY:
        return BASELINE_LABEL
    return MODEL_REGISTRY.get(model_key, {}).get("label", f"Model {model_key}")


def _color(model_key: str) -> str:
    if model_key == BASELINE_KEY:
        return BASELINE_COLOR
    return MODEL_REGISTRY.get(model_key, {}).get("color", "#666666")


def _plot_mae(summary: pd.DataFrame, output_path: Path) -> None:
    ordered = summary.copy()
    order = {BASELINE_KEY: 0, **{key: index + 1 for index, key in enumerate(DEEP_KEYS)}}
    ordered["_order"] = ordered["model_key"].map(order).fillna(99)
    ordered = ordered.sort_values("_order")
    x = np.arange(len(ordered))
    figure, axis = plt.subplots(figsize=(10.8, 5.2))
    bars = axis.bar(
        x,
        ordered["test_mae_mean"],
        yerr=ordered["test_mae_std"],
        capsize=5,
        color=[_color(key) for key in ordered["model_key"]],
        alpha=0.88,
        edgecolor="#333333",
        linewidth=0.6,
    )
    axis.set_xticks(x)
    axis.set_xticklabels(["VisualStat-Ridge" if key == BASELINE_KEY else f"Model {key}" for key in ordered["model_key"]])
    axis.set_ylabel("LOFO test MAE (hours, lower is better)")
    axis.set_title("Strawberry RUL: Image-only Baseline vs Deep Sequence Models", fontweight="bold")
    axis.grid(True, axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    ymax = float((ordered["test_mae_mean"] + ordered["test_mae_std"]).max())
    axis.set_ylim(0, ymax * 1.22)
    for bar, value in zip(bars, ordered["test_mae_mean"]):
        axis.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + ymax * 0.035, f"{value:.2f}", ha="center", fontsize=9, fontweight="bold")
    figure.text(
        0.5,
        0.01,
        "Error bars show the standard deviation across the six held-out fruits. "
        "All approaches use image-only sequence input; elapsed time and fruit ID are excluded.",
        ha="center",
        fontsize=8.5,
    )
    figure.tight_layout(rect=(0, 0.06, 1, 1))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)


def _markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
    table = frame.loc[:, columns].copy()
    for column in table.columns:
        if pd.api.types.is_numeric_dtype(table[column]):
            table[column] = table[column].map(lambda value: "" if pd.isna(value) else f"{value:.3f}")
    header = "| " + " | ".join(table.columns) + " |"
    separator = "| " + " | ".join("---" for _ in table.columns) + " |"
    rows = ["| " + " | ".join(str(value) for value in row) + " |" for row in table.to_numpy()]
    return "\n".join([header, separator, *rows])


def write_baseline_comparison(
    run_root: str | Path | None = None,
    *,
    baseline_root: str | Path | None = None,
    output_dir: str | Path | None = None,
    graph_dir: str | Path | None = None,
) -> Path:
    root = resolve_run_root(run_root)
    source_baseline_root = Path(baseline_root) if baseline_root is not None else _baseline_root(root)
    if not source_baseline_root.is_absolute():
        source_baseline_root = PROJECT_ROOT / source_baseline_root
    baseline_fold_path = source_baseline_root / "fold_results.csv"
    if not baseline_fold_path.exists():
        raise FileNotFoundError(f"Run the Ridge baseline first; missing {baseline_fold_path}")

    default_reports = PROJECT_ROOT / "output" / "reports" / "evaluation" / root.name / "with_ridge_baseline"
    default_graphs = PROJECT_ROOT / "output" / "graphs" / "evaluation" / root.name / "with_ridge_baseline"
    reports = Path(output_dir) if output_dir is not None else default_reports
    graphs = Path(graph_dir) if graph_dir is not None else default_graphs
    if not reports.is_absolute():
        reports = PROJECT_ROOT / reports
    if not graphs.is_absolute():
        graphs = PROJECT_ROOT / graphs
    reports.mkdir(parents=True, exist_ok=True)
    graphs.mkdir(parents=True, exist_ok=True)

    deep_fold = pd.read_csv(root / "fold_results.csv")
    deep_fold = deep_fold[deep_fold["model_key"].astype(str).isin(DEEP_KEYS)].copy()
    baseline_fold = pd.read_csv(baseline_fold_path)
    if set(baseline_fold["model_key"].astype(str)) != {BASELINE_KEY}:
        raise ValueError(f"Unexpected baseline model key in {baseline_fold_path}")
    combined_fold = pd.concat([baseline_fold, deep_fold], ignore_index=True, sort=False)
    summary = _summarize(combined_fold)
    summary["approach"] = summary["model_key"].map(_display_label)
    order = {BASELINE_KEY: 0, **{key: index + 1 for index, key in enumerate(DEEP_KEYS)}}
    summary["_order"] = summary["model_key"].map(order).fillna(99)
    summary = summary.sort_values("_order").drop(columns="_order").reset_index(drop=True)
    summary.to_csv(reports / "model_comparison_with_ridge.csv", index=False)
    combined_fold.to_csv(reports / "fold_results_with_ridge.csv", index=False)

    chart_path = graphs / "ridge_baseline_vs_deep_models.png"
    _plot_mae(summary, chart_path)
    shortcut_path = source_baseline_root / "elapsed_time_shortcut_diagnostic.csv"
    shortcut = pd.read_csv(shortcut_path) if shortcut_path.exists() else pd.DataFrame()
    if not shortcut.empty:
        shortcut.to_csv(reports / "elapsed_time_shortcut_diagnostic.csv", index=False)

    baseline_row = summary.loc[summary["model_key"] == BASELINE_KEY].iloc[0]
    d_row = summary.loc[summary["model_key"] == "D"].iloc[0] if "D" in set(summary["model_key"]) else None
    chart_relative = Path("..") / ".." / ".." / ".." / "graphs" / "evaluation" / root.name / "with_ridge_baseline" / chart_path.name
    lines = [
        "# Strawberry RUL — image-only VisualStat-Ridge baseline",
        "",
        "## Purpose",
        "",
        "VisualStat-Ridge is the primary low-capacity reference for the current strawberry-only study. It tests whether A–D improve over simple, interpretable visual statistics without convolutional backbones, CBAM, recurrent layers, or ImageNet pretraining.",
        "",
        "## Fixed, leakage-safe protocol",
        "",
        "- Input is the same image-only sequence length as A–D (`seq_len=8`).",
        "- Each frame yields 12 existing low-cost RGB/brightness/saturation/gradient statistics. The model uses last-frame, sequence mean, and last-minus-first change: 36 features total.",
        "- `StandardScaler → Ridge` is fit only on the four model-fit fruits from the project’s outer LOFO split. `alpha` is selected by a nested Leave-One-Fruit-Out procedure only within those four fruits.",
        "- It excludes fruit ID, timestamps, elapsed time, EOL-derived values, and sensor values. Metrics use raw regression output to match the current A–D fold-metric convention.",
        "",
        "## LOFO comparison",
        "",
    ]
    report_table = summary.copy()
    report_table["mae_mean_std_h"] = report_table.apply(
        lambda row: f"{row.test_mae_mean:.2f} +/- {row.test_mae_std:.2f}", axis=1
    )
    lines.append(
        _markdown_table(
            report_table,
            ["model_key", "approach", "folds", "mae_mean_std_h", "test_rmse_mean", "test_r2_mean", "test_smape_mean"],
        )
    )
    lines.extend(
        [
            "",
            "## MAE chart",
            "",
            f"![Image-only LOFO MAE comparison]({chart_relative.as_posix()})",
            "",
            "## Interpretation",
            "",
            f"- VisualStat-Ridge achieved **{baseline_row.test_mae_mean:.2f} +/- {baseline_row.test_mae_std:.2f} h** fold-averaged LOFO MAE.",
        ]
    )
    if d_row is not None:
        difference = float(baseline_row.test_mae_mean - d_row.test_mae_mean)
        direction = "lower" if difference > 0 else "higher"
        lines.append(
            f"- Model D has **{abs(difference):.2f} h {direction}** mean MAE than VisualStat-Ridge in this image-only comparison."
        )
    lines.extend(
        [
            "- With only six fruits, use this as a transparent benchmark rather than a claim of population-level superiority; keep per-fruit fold results in the supplement.",
            "",
            "## Metadata-control warning (not part of the image-only table)",
            "",
            "`RUL + elapsed_hours_end` is nearly constant within each fruit because RUL is derived from EOL timestamp minus capture timestamp. Elapsed time is therefore deliberately excluded from both this baseline and the image-only A–D comparison. A time-only model is an operational/metadata control only if the deployed system knows the fruit tracking start time and every comparator receives that modality.",
        ]
    )
    if not shortcut.empty:
        lines.extend(
            [
                "",
                _markdown_table(shortcut, ["fruit_id", "sequence_windows", "lifecycle_hours_mean", "lifecycle_hours_std"]),
            ]
        )
    lines.extend(
        [
            "",
            "## References supporting the baseline design",
            "",
            "- Hoerl, A. E., & Kennard, R. W. (1970). *Ridge Regression: Biased Estimation for Nonorthogonal Problems*. Technometrics, 12(1), 55–67. https://doi.org/10.1080/00401706.1970.10488634",
            "- Jimenez-Jimenez, F., Possas, A., Rabasco-Vílchez, L., & Perez-Rodríguez, F. (2023). *Image Analysis Assessment of the Shelf Life of Fresh Strawberries*. Chemical Engineering Transactions, 102, 277–282. https://doi.org/10.3303/CET23102047",
            "- scikit-learn documentation: Leave-One-Group-Out cross-validation. https://scikit-learn.org/stable/modules/cross_validation.html#leave-one-group-out",
            "",
        ]
    )
    report_path = reports / "ridge_baseline_comparison.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    (reports / "ridge_baseline_comparison.json").write_text(
        json.dumps(
            {
                "source_run_root": str(root),
                "baseline_root": str(source_baseline_root),
                "chart_path": str(chart_path),
                "summary": summary.to_dict(orient="records"),
                "shortcut_diagnostic": shortcut.to_dict(orient="records"),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create the separate A–D + VisualStat-Ridge comparison report.")
    parser.add_argument("--run-root", type=Path, default=None, help="Existing A–D run root. Defaults to latest completed run.")
    parser.add_argument("--baseline-root", type=Path, default=None, help="VisualStat-Ridge artifact root.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Comparison report directory.")
    parser.add_argument("--graph-dir", type=Path, default=None, help="Comparison graph directory.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report_path = write_baseline_comparison(
        args.run_root,
        baseline_root=args.baseline_root,
        output_dir=args.output_dir,
        graph_dir=args.graph_dir,
    )
    print(f"[OK] Saved baseline comparison report: {report_path}")


if __name__ == "__main__":
    main()
