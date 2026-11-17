"""Create a unified comparison for the strawberry baselines and A--D models.

Unlike the original VisualStat-Ridge report, this module supports more than
one standalone baseline artifact and writes to a new ``with_baselines``
directory.  It never alters A--D or the existing Ridge-only report.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from strawberry.training.baseline_mean import BASELINE_KEY as TRAIN_MEAN_KEY
from strawberry.training.baseline_mean import BASELINE_SLUG as TRAIN_MEAN_SLUG
from strawberry.training.baseline_ridge import BASELINE_KEY as RIDGE_KEY
from strawberry.training.baseline_ridge import BASELINE_SLUG as RIDGE_SLUG

from .common import MODEL_REGISTRY, PROJECT_ROOT, resolve_run_root


DEEP_KEYS = ("A", "B", "C", "D")


@dataclass(frozen=True)
class BaselineSpec:
    key: str
    slug: str
    label: str
    chart_label: str
    input_category: str
    color: str
    description: str


BASELINE_SPECS: tuple[BaselineSpec, ...] = (
    BaselineSpec(
        key=TRAIN_MEAN_KEY,
        slug=TRAIN_MEAN_SLUG,
        label="Train-mean predictor (no input)",
        chart_label="Train-mean\n(no input)",
        input_category="Naïve / no-input",
        color="#9E9E9E",
        description="Predicts the pooled train-target mean separately in every fold; it consumes no images or metadata.",
    ),
    BaselineSpec(
        key=RIDGE_KEY,
        slug=RIDGE_SLUG,
        label="VisualStat-Ridge (36 visual sequence statistics)",
        chart_label="VisualStat-Ridge",
        input_category="Image-only sequence",
        color="#616161",
        description="Uses the same 8-frame image sequence as A–D, reduced to 36 hand-crafted visual statistics.",
    ),
)
SPEC_BY_KEY = {spec.key: spec for spec in BASELINE_SPECS}


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
    if model_key in SPEC_BY_KEY:
        return SPEC_BY_KEY[model_key].label
    return MODEL_REGISTRY.get(model_key, {}).get("label", f"Model {model_key}")


def _input_category(model_key: str) -> str:
    if model_key in SPEC_BY_KEY:
        return SPEC_BY_KEY[model_key].input_category
    return "Image-only sequence"


def _color(model_key: str) -> str:
    if model_key in SPEC_BY_KEY:
        return SPEC_BY_KEY[model_key].color
    return MODEL_REGISTRY.get(model_key, {}).get("color", "#666666")


def _chart_label(model_key: str) -> str:
    if model_key in SPEC_BY_KEY:
        return SPEC_BY_KEY[model_key].chart_label
    return f"Model {model_key}"


def _order(model_key: str) -> int:
    baseline_order = {spec.key: index for index, spec in enumerate(BASELINE_SPECS)}
    deep_order = {key: len(BASELINE_SPECS) + index for index, key in enumerate(DEEP_KEYS)}
    return baseline_order.get(model_key, deep_order.get(model_key, 99))


def _markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
    table = frame.loc[:, columns].copy()
    for column in table.columns:
        if column == "folds":
            table[column] = table[column].map(lambda value: "" if pd.isna(value) else str(int(value)))
        elif pd.api.types.is_numeric_dtype(table[column]):
            table[column] = table[column].map(lambda value: "" if pd.isna(value) else f"{value:.3f}")
    header = "| " + " | ".join(table.columns) + " |"
    separator = "| " + " | ".join("---" for _ in table.columns) + " |"
    rows = ["| " + " | ".join(str(value) for value in row) + " |" for row in table.to_numpy()]
    return "\n".join([header, separator, *rows])


def _validate_baseline_folds(baseline_fold: pd.DataFrame, spec: BaselineSpec, deep_fold: pd.DataFrame) -> None:
    required = {"model_key", "fold_name", "test_group", "val_group", "test_mae", "test_rmse", "test_r2", "test_smape"}
    missing = required.difference(baseline_fold.columns)
    if missing:
        raise ValueError(f"{spec.slug} is missing comparison columns: {sorted(missing)}")
    if set(baseline_fold["model_key"].astype(str)) != {spec.key}:
        raise ValueError(f"Unexpected model key in {spec.slug}; expected only {spec.key}")
    if baseline_fold["test_group"].astype(str).duplicated().any():
        raise ValueError(f"{spec.slug} has more than one row for a held-out fruit")

    expected_test_groups = set(deep_fold["test_group"].astype(str))
    actual_test_groups = set(baseline_fold["test_group"].astype(str))
    if actual_test_groups != expected_test_groups:
        raise ValueError(
            f"{spec.slug} held-out fruits do not match A-D: expected {sorted(expected_test_groups)}, got {sorted(actual_test_groups)}"
        )
    expected_val_by_test = (
        deep_fold[["test_group", "val_group"]]
        .drop_duplicates()
        .assign(test_group=lambda frame: frame["test_group"].astype(str), val_group=lambda frame: frame["val_group"].astype(str))
        .set_index("test_group")["val_group"]
        .to_dict()
    )
    actual_val_by_test = baseline_fold.assign(
        test_group=lambda frame: frame["test_group"].astype(str),
        val_group=lambda frame: frame["val_group"].astype(str),
    ).set_index("test_group")["val_group"].to_dict()
    if actual_val_by_test != expected_val_by_test:
        raise ValueError(f"{spec.slug} validation fruit assignments do not match A-D")


def _discover_baselines(run_root: Path) -> list[tuple[BaselineSpec, Path]]:
    found: list[tuple[BaselineSpec, Path]] = []
    for spec in BASELINE_SPECS:
        artifact_root = run_root / "baselines" / spec.slug
        if (artifact_root / "fold_results.csv").exists():
            found.append((spec, artifact_root))
    if not found:
        expected = ", ".join(str(run_root / "baselines" / spec.slug / "fold_results.csv") for spec in BASELINE_SPECS)
        raise FileNotFoundError(f"No baseline fold results found. Expected one or more of: {expected}")
    return found


def _plot_mae(summary: pd.DataFrame, output_path: Path) -> None:
    ordered = summary.copy()
    ordered["_order"] = ordered["model_key"].map(_order)
    ordered = ordered.sort_values("_order")
    x = np.arange(len(ordered))
    figure, axis = plt.subplots(figsize=(12.2, 5.35))
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
    axis.set_xticklabels([_chart_label(key) for key in ordered["model_key"]])
    axis.set_ylabel("LOFO test MAE (hours, lower is better)")
    axis.set_title("Strawberry RUL: Baselines vs Deep Sequence Models", fontweight="bold")
    axis.grid(True, axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    ymax = float((ordered["test_mae_mean"] + ordered["test_mae_std"]).max())
    axis.set_ylim(0, ymax * 1.23)
    for bar, value in zip(bars, ordered["test_mae_mean"]):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + ymax * 0.035,
            f"{value:.2f}",
            ha="center",
            fontsize=9,
            fontweight="bold",
        )
    figure.text(
        0.5,
        0.01,
        "All rows use the same six held-out fruits. Train-mean is a no-input sanity reference; "
        "VisualStat-Ridge and A–D use image-only 8-frame sequences. Error bars: fold standard deviation.",
        ha="center",
        fontsize=8.3,
    )
    figure.tight_layout(rect=(0, 0.07, 1, 1))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)


def write_baselines_comparison(
    run_root: str | Path | None = None,
    *,
    output_dir: str | Path | None = None,
    graph_dir: str | Path | None = None,
) -> Path:
    """Write a fresh report combining every available standalone baseline with A--D."""
    root = resolve_run_root(run_root)
    default_reports = PROJECT_ROOT / "output" / "reports" / "evaluation" / root.name / "with_baselines"
    default_graphs = PROJECT_ROOT / "output" / "graphs" / "evaluation" / root.name / "with_baselines"
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
    if deep_fold.empty:
        raise ValueError(f"No A-D fold results found under {root}")

    baseline_frames: list[pd.DataFrame] = []
    discovered = _discover_baselines(root)
    for spec, artifact_root in discovered:
        baseline_fold = pd.read_csv(artifact_root / "fold_results.csv")
        _validate_baseline_folds(baseline_fold, spec, deep_fold)
        baseline_frames.append(baseline_fold)

    combined_fold = pd.concat([*baseline_frames, deep_fold], ignore_index=True, sort=False)
    summary = _summarize(combined_fold)
    summary["approach"] = summary["model_key"].map(_display_label)
    summary["input_category"] = summary["model_key"].map(_input_category)
    summary["_order"] = summary["model_key"].map(_order)
    summary = summary.sort_values("_order").drop(columns="_order").reset_index(drop=True)
    summary.to_csv(reports / "model_comparison_with_baselines.csv", index=False)
    combined_fold.to_csv(reports / "fold_results_with_baselines.csv", index=False)

    chart_path = graphs / "baselines_vs_deep_models.png"
    _plot_mae(summary, chart_path)

    shortcut = pd.DataFrame()
    ridge_root = root / "baselines" / RIDGE_SLUG
    shortcut_path = ridge_root / "elapsed_time_shortcut_diagnostic.csv"
    if shortcut_path.exists():
        shortcut = pd.read_csv(shortcut_path)
        shortcut.to_csv(reports / "elapsed_time_shortcut_diagnostic.csv", index=False)

    report_table = summary.copy()
    report_table["mae_mean_std_h"] = report_table.apply(
        lambda row: f"{row.test_mae_mean:.2f} +/- {row.test_mae_std:.2f}", axis=1
    )
    d_row = summary.loc[summary["model_key"] == "D"].iloc[0] if "D" in set(summary["model_key"]) else None
    chart_relative = os.path.relpath(chart_path, reports).replace("\\", "/")
    lines = [
        "# Strawberry RUL — Baseline and deep-model comparison",
        "",
        "## Scope",
        "",
        "This separate report compares the completed A–D image-sequence models with every available standalone baseline. It does not change the original A–D results, checkpoints, or Ridge-only report.",
        "",
        "## Baseline roles and protocol",
        "",
        "- **Train-mean predictor (no input):** a naïve lower-bound sanity reference. For each outer held-out fruit it predicts the pooled mean RUL from only the same four model-fit fruits used by A–D. It does not read an image or any metadata; it is therefore not an image-model comparison.",
        "- **VisualStat-Ridge:** the simple, input-matched visual baseline. It uses the same eight-frame image sequence as A–D, reduced to 36 RGB/brightness/saturation/gradient statistics, then fits `StandardScaler → Ridge`.",
        "- **A–D:** the completed image-only deep sequence models.",
        "",
        "For both baselines, the outer test fruit and the reserved validation fruit are excluded from fitting. The held-out fruit and validation assignments are checked against A–D before this report is generated. Metrics use the raw prediction convention used by the existing fold results.",
        "",
        "## LOFO comparison",
        "",
        _markdown_table(
            report_table,
            [
                "model_key",
                "approach",
                "input_category",
                "folds",
                "mae_mean_std_h",
                "test_rmse_mean",
                "test_r2_mean",
                "test_smape_mean",
            ],
        ),
        "",
        "## MAE chart",
        "",
        f"![Baseline and deep-model LOFO MAE comparison]({chart_relative})",
        "",
        "## Interpretation",
        "",
    ]
    for spec, _ in discovered:
        baseline_row = summary.loc[summary["model_key"] == spec.key].iloc[0]
        lines.append(
            f"- {spec.label} achieved **{baseline_row.test_mae_mean:.2f} +/- {baseline_row.test_mae_std:.2f} h** fold-averaged LOFO MAE. {spec.description}"
        )
        if d_row is not None:
            improvement = float(baseline_row.test_mae_mean - d_row.test_mae_mean)
            if improvement >= 0:
                relative = 100.0 * improvement / float(baseline_row.test_mae_mean)
                lines.append(f"  Model D is **{improvement:.2f} h lower ({relative:.1f}%)** in mean MAE than this reference.")
            else:
                lines.append(f"  Model D is **{abs(improvement):.2f} h higher** in mean MAE than this reference.")
    lines.extend(
        [
            "- With six fruits, these are transparent fold-level benchmarks rather than population-level claims; retain `fold_results_with_baselines.csv` in the supplement.",
            "",
            "## Metadata-control warning (not part of the image-only table)",
            "",
            "`RUL + elapsed_hours_end` is nearly constant within each fruit because RUL is derived from EOL timestamp minus capture timestamp. Elapsed time is deliberately excluded from the image-only A–D and VisualStat-Ridge comparison. A time-only model is an operational control only when the deployment knows the fruit tracking start time and every comparator receives that modality.",
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
            "## Reference for the visual baseline",
            "",
            "- Hoerl, A. E., & Kennard, R. W. (1970). *Ridge Regression: Biased Estimation for Nonorthogonal Problems*. Technometrics, 12(1), 55–67. https://doi.org/10.1080/00401706.1970.10488634",
            "",
        ]
    )
    report_path = reports / "baseline_and_deep_model_comparison.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    (reports / "baseline_and_deep_model_comparison.json").write_text(
        json.dumps(
            {
                "source_run_root": str(root),
                "baseline_roots": {spec.key: str(path) for spec, path in discovered},
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
    parser = argparse.ArgumentParser(description="Create a unified strawberry baselines + A-D comparison report.")
    parser.add_argument("--run-root", type=Path, default=None, help="Existing A-D run root. Defaults to the latest completed run.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Comparison report directory.")
    parser.add_argument("--graph-dir", type=Path, default=None, help="Comparison graph directory.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report_path = write_baselines_comparison(args.run_root, output_dir=args.output_dir, graph_dir=args.graph_dir)
    print(f"[OK] Saved unified baseline comparison report: {report_path}")


if __name__ == "__main__":
    main()
