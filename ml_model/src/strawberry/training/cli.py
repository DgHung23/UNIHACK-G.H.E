from __future__ import annotations

import argparse
from pathlib import Path

from .baseline_mean import run_train_mean_baseline
from .baseline_ridge import run_visual_stat_ridge_baseline
from .config import TrainingConfig, load_training_config
from .engine import train_loocv_run
from .evaluate import summarize_run
from .lab_search import run_lab_search


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Strawberry RUL training and lab utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    train_parser = subparsers.add_parser("train", help="Run LOOCV training for strawberry models")
    train_parser.add_argument("--config", type=Path, default=None, help="Path to a JSON training config")
    train_parser.add_argument("--models", nargs="*", default=None, help="Optional subset of model keys A B C D")

    eval_parser = subparsers.add_parser("evaluate", help="Summarize a completed training run")
    eval_parser.add_argument("--run-root", type=Path, required=True, help="Path to the run root directory")

    lab_parser = subparsers.add_parser("lab", help="Run the small-model lab sweep")
    lab_parser.add_argument("--config", type=Path, default=None, help="Optional JSON config for the lab")

    baseline_parser = subparsers.add_parser("baseline", help="Run a standalone strawberry LOFO baseline")
    baseline_parser.add_argument("--config", type=Path, default=None, help="Path to the strawberry training config")
    baseline_parser.add_argument(
        "--kind",
        choices=("ridge", "mean", "all"),
        default="ridge",
        help="Baseline to run: image-only Ridge, no-input train mean, or both (default: ridge)",
    )
    baseline_parser.add_argument("--no-comparison-report", action="store_true", help="Skip the separate baseline-vs-A–D report")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "train":
        config = load_training_config(args.config)
        train_loocv_run(config, model_keys=args.models)
        return

    if args.command == "evaluate":
        summarize_run(args.run_root)
        return

    if args.command == "lab":
        run_lab_search(args.config)
        return

    if args.command == "baseline":
        config = load_training_config(args.config)
        if args.kind in {"ridge", "all"}:
            fold_results = run_visual_stat_ridge_baseline(config)
            print("\n[VisualStat-Ridge]")
            print(fold_results.to_string(index=False))
        if args.kind in {"mean", "all"}:
            fold_results = run_train_mean_baseline(config)
            print("\n[Train-mean predictor]")
            print(fold_results.to_string(index=False))
        if not args.no_comparison_report:
            from strawberry.stage5_evaluation.baselines_comparison import write_baselines_comparison

            run_root = config.artifact_root_path(Path(__file__).resolve().parents[3]) / config.run_name
            report_path = write_baselines_comparison(run_root)
            print(f"[OK] Saved unified baseline comparison report: {report_path}")
        return

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
