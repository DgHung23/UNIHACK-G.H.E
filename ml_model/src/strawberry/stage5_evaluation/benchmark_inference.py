"""Reproducible warm-inference benchmark for the strawberry A/B/C/D models.

The benchmark intentionally measures only a loaded model's forward pass.  It
does not include image decoding, strawberry segmentation, tensor preparation,
host-to-device transfer, HTTP, or lazy checkpoint loading.  Those costs are
shared application concerns and must be measured separately as API E2E latency.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import platform
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd
import torch

from strawberry.training.models import build_model


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUN_PARENT = PROJECT_ROOT / "output" / "runs" / "strawberry"

MODEL_LABELS = {
    "A": "EfficientNet-B0 + CBAM + GRU",
    "B": "MobileNetV2 + CBAM + LSTM",
    "C": "EfficientNet-B0 + CBAM + LSTM",
    "D": "MobileNetV2 + CBAM + GRU",
}


def _resolve_run_root(value: str | Path | None) -> Path:
    if value is not None:
        path = Path(value)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if not (path / "fold_results.csv").exists():
            raise FileNotFoundError(f"Missing fold_results.csv under run root: {path}")
        return path

    candidates = [path for path in DEFAULT_RUN_PARENT.glob("*") if (path / "fold_results.csv").exists()]
    if not candidates:
        raise FileNotFoundError(f"No completed strawberry run under: {DEFAULT_RUN_PARENT}")
    return max(candidates, key=lambda path: (path / "fold_results.csv").stat().st_mtime)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _checkpoint_path(run_root: Path, model_key: str, fold_name: str, run_config: dict[str, Any]) -> Path:
    fold_results = pd.read_csv(run_root / "fold_results.csv")
    match = fold_results.loc[
        (fold_results["model_key"].astype(str).str.upper() == model_key)
        & (fold_results["fold_name"].astype(str) == fold_name)
    ]
    if not match.empty:
        raw_path = str(match.iloc[0].get("checkpoint_path", ""))
        candidate = Path(raw_path)
        if raw_path and candidate.exists():
            return candidate

    checkpoint_root = Path(str(run_config.get("checkpoint_root", "models/strawberry/runs")))
    if not checkpoint_root.is_absolute():
        checkpoint_root = PROJECT_ROOT / checkpoint_root
    candidate = checkpoint_root / run_root.name / model_key / fold_name / "best_model.pt"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"Missing checkpoint for Model {model_key}, {fold_name}: {candidate}")


def _synchronize(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def _torch_load(path: Path, device: torch.device) -> dict[str, Any]:
    """Load old and current PyTorch checkpoint formats without a warning."""
    try:
        checkpoint = torch.load(path, map_location=device, weights_only=False)
    except TypeError:  # pragma: no cover - compatibility with older PyTorch releases
        checkpoint = torch.load(path, map_location=device)
    if not isinstance(checkpoint, dict):
        raise ValueError(f"Unexpected checkpoint format: {path}")
    return checkpoint


def _load_model(checkpoint_path: Path, expected_key: str, device: torch.device) -> tuple[torch.nn.Module, dict[str, Any], float]:
    start = perf_counter()
    checkpoint = _torch_load(checkpoint_path, device)
    checkpoint_config = checkpoint.get("config") or {}
    checkpoint_key = str(checkpoint.get("model_key") or checkpoint_config.get("model_key") or expected_key).upper()
    if checkpoint_key != expected_key:
        raise ValueError(f"Checkpoint {checkpoint_path} is Model {checkpoint_key}, expected Model {expected_key}")

    model = build_model(
        checkpoint_key,
        hidden_size=int(checkpoint_config.get("hidden_size", 160)),
        env_hidden_size=int(checkpoint_config.get("env_hidden_size", 64)),
        dropout=float(checkpoint_config.get("dropout", 0.25)),
        backbone_dropout=float(checkpoint_config.get("backbone_dropout", 0.1)),
        temporal_pooling=str(checkpoint_config.get("temporal_pooling", "last_mean_max")),
        fusion_mode=str(checkpoint_config.get("fusion_mode", "image_only")),
        pretrained_backbone=False,
    ).to(device)
    state_dict = checkpoint.get("model_state_dict") or checkpoint.get("state_dict") or checkpoint.get("model")
    if not isinstance(state_dict, dict):
        raise ValueError(f"Checkpoint lacks model weights: {checkpoint_path}")
    model.load_state_dict(state_dict, strict=True)
    model.eval()
    _synchronize(device)
    return model, checkpoint_config, (perf_counter() - start) * 1_000.0


def _percentile(values: list[float], q: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=np.float64), q))


def _measure_forward(
    model: torch.nn.Module,
    images: torch.Tensor,
    env: torch.Tensor,
    device: torch.device,
    warmup: int,
    iterations: int,
) -> list[float]:
    with torch.inference_mode():
        for _ in range(warmup):
            model(images, env)
        _synchronize(device)

        timings_ms: list[float] = []
        for _ in range(iterations):
            _synchronize(device)
            start = perf_counter()
            model(images, env)
            _synchronize(device)
            timings_ms.append((perf_counter() - start) * 1_000.0)
    return timings_ms


def _device_name(device: torch.device) -> str:
    if device.type == "cuda":
        return torch.cuda.get_device_name(device)
    return os.environ.get("PROCESSOR_IDENTIFIER") or platform.processor() or platform.machine()


def _resolve_devices(values: list[str] | None) -> list[torch.device]:
    requested = values or ["cpu", "cuda"]
    devices: list[torch.device] = []
    for raw in requested:
        value = raw.lower()
        if value == "cuda" and not torch.cuda.is_available():
            if values:
                raise RuntimeError("CUDA was requested but is not available.")
            continue
        device = torch.device(value)
        if device.type not in {"cpu", "cuda"}:
            raise ValueError(f"Only cpu and cuda devices are supported, received: {raw}")
        devices.append(device)
    if not devices:
        raise RuntimeError("No benchmark device is available.")
    return devices


def _accuracy_by_model(run_root: Path) -> dict[str, dict[str, float]]:
    fold = pd.read_csv(run_root / "fold_results.csv")
    summary = fold.groupby("model_key", as_index=False).agg(
        loocv_mae_mean_h=("test_mae", "mean"),
        loocv_mae_std_h=("test_mae", "std"),
    )
    return {
        str(row.model_key).upper(): {
            "loocv_mae_mean_h": float(row.loocv_mae_mean_h),
            "loocv_mae_std_h": float(row.loocv_mae_std_h),
        }
        for row in summary.itertuples(index=False)
    }


def _backend_readiness(run_config: dict[str, Any]) -> dict[str, Any]:
    config_path = PROJECT_ROOT / "src" / "strawberry" / "config_app" / "config.json"
    result: dict[str, Any] = {
        "config_path": str(config_path.relative_to(PROJECT_ROOT)),
        "config_json_valid": False,
        "config_error": None,
        "configured_model_path": None,
        "configured_model_exists": False,
        "configured_device": "cpu (predictor default when absent)",
        "training_image_size": int(run_config.get("image_size", 224)),
    }
    try:
        # The application loader intentionally accepts a UTF-8 BOM, so use the
        # same encoding here and report the substantive configuration problem.
        with config_path.open("r", encoding="utf-8-sig") as handle:
            app_config = json.load(handle)
        if not isinstance(app_config, dict):
            raise ValueError(f"Expected JSON object: {config_path}")
        result["config_json_valid"] = True
        model_config = app_config.get("model") or {}
        raw_model_path = model_config.get("path") or app_config.get("model_path")
        if raw_model_path:
            model_path = Path(str(raw_model_path))
            if not model_path.is_absolute():
                model_path = PROJECT_ROOT / model_path
            result["configured_model_path"] = str(model_path.relative_to(PROJECT_ROOT))
            result["configured_model_exists"] = model_path.exists()
        result["configured_device"] = str(app_config.get("device", "cpu (predictor default when absent)"))
        result["configured_crop_width"] = (app_config.get("image") or {}).get("crop_width")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        result["config_error"] = f"{type(error).__name__}: {error}"
    return result


def _hardware_metadata(devices: list[torch.device]) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "platform": platform.platform(),
        "cpu": _device_name(torch.device("cpu")),
        "logical_cpu_count": os.cpu_count(),
        "torch_version": torch.__version__,
        "torch_num_threads": torch.get_num_threads(),
        "torch_num_interop_threads": torch.get_num_interop_threads(),
        "cuda_available": torch.cuda.is_available(),
        "cudnn_benchmark": bool(torch.backends.cudnn.benchmark) if torch.cuda.is_available() else None,
    }
    if any(device.type == "cuda" for device in devices):
        metadata["cuda_device"] = _device_name(torch.device("cuda"))
        metadata["cuda_runtime"] = torch.version.cuda
        metadata["cuda_total_memory_mib"] = round(torch.cuda.get_device_properties(0).total_memory / (1024**2), 1)
        metadata["allow_tf32_matmul"] = bool(torch.backends.cuda.matmul.allow_tf32)
        metadata["allow_tf32_cudnn"] = bool(torch.backends.cudnn.allow_tf32)
    return metadata


def _format_latency(row: pd.Series, prefix: str) -> str:
    p50 = row.get(f"{prefix}_p50_ms")
    p95 = row.get(f"{prefix}_p95_ms")
    if pd.isna(p50) or pd.isna(p95):
        return "n/a"
    return f"{p50:.2f} / {p95:.2f}"


def _write_latency_chart(results: pd.DataFrame, output_path: Path, benchmark_config: dict[str, Any]) -> None:
    """Render a report-ready P50/P95 latency chart for every measured device."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    device_order = [device for device in ("cpu", "cuda") if device in set(results["device"])]
    panels = max(len(device_order), 1)
    figure, axes = plt.subplots(1, panels, figsize=(6.1 * panels, 4.7), squeeze=False)
    axes_list = axes.ravel().tolist()
    colors = {"A": "#1E88E5", "B": "#FB8C00", "C": "#43A047", "D": "#D81B60"}

    for axis, device in zip(axes_list, device_order):
        frame = results.loc[results["device"] == device].sort_values("model_key")
        positions = np.arange(len(frame))
        p50 = frame["p50_ms"].to_numpy(dtype=float)
        p95 = frame["p95_ms"].to_numpy(dtype=float)
        bars = axis.bar(
            positions,
            p50,
            width=0.66,
            color=[colors.get(key, "#666666") for key in frame["model_key"]],
            edgecolor="#333333",
            linewidth=0.6,
            alpha=0.9,
        )
        axis.vlines(positions, p50, p95, color="#212121", linewidth=1.8, zorder=3)
        axis.scatter(positions, p95, color="#212121", marker="_", s=140, linewidths=2.2, zorder=4)
        limit = max(p95) * 1.22
        axis.set_ylim(0, limit)
        for bar, p50_value, p95_value in zip(bars, p50, p95):
            axis.text(
                bar.get_x() + bar.get_width() / 2,
                p95_value + limit * 0.025,
                f"{p50_value:.1f} / {p95_value:.1f}",
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
            )
        device_name = str(frame["device_name"].iloc[0]) if not frame.empty else device.upper()
        axis.set_title(f"{device.upper()} — {device_name}", fontweight="bold", fontsize=10)
        axis.set_xticks(positions)
        axis.set_xticklabels([f"Model {key}" for key in frame["model_key"]])
        axis.set_ylabel("Model-forward latency (ms)")
        axis.grid(True, axis="y", alpha=0.25)
        axis.set_axisbelow(True)

    figure.legend(
        handles=[
            Line2D([0], [0], color="#212121", linewidth=1.8, marker="_", markersize=10, label="P50 → P95"),
        ],
        loc="lower center",
        ncol=1,
        frameon=False,
        bbox_to_anchor=(0.5, -0.01),
    )
    figure.suptitle(
        "Strawberry RUL — Prediction Inference Latency\n"
        f"batch={benchmark_config['batch_size']}, sequence={benchmark_config['seq_len']} × "
        f"{benchmark_config['image_size']}×{benchmark_config['image_size']}, FP32",
        fontsize=14,
        fontweight="bold",
        y=1.04,
    )
    figure.tight_layout(rect=(0, 0.07, 1, 0.96))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)


def _write_markdown_report(
    output_path: Path,
    run_root: Path,
    benchmark_config: dict[str, Any],
    hardware: dict[str, Any],
    readiness: dict[str, Any],
    results: pd.DataFrame,
    chart_path: Path,
) -> None:
    wide = results.pivot(index="model_key", columns="device", values=["p50_ms", "p95_ms", "throughput_predictions_per_second"])
    wide.columns = [f"{device}_{metric}" for metric, device in wide.columns]
    wide = wide.reset_index()
    static_columns = [
        "model_key",
        "architecture",
        "loocv_mae_mean_h",
        "loocv_mae_std_h",
        "parameter_count",
        "checkpoint_size_mib",
    ]
    table = results[static_columns].drop_duplicates("model_key").merge(wide, on="model_key", how="left")
    table = table.sort_values("model_key").reset_index(drop=True)
    table["loocv_mae"] = table.apply(lambda row: f"{row.loocv_mae_mean_h:.2f} +/- {row.loocv_mae_std_h:.2f}", axis=1)
    table["parameters_m"] = table["parameter_count"].map(lambda value: f"{value / 1_000_000:.3f}")
    table["checkpoint_mib"] = table["checkpoint_size_mib"].map(lambda value: f"{value:.2f}")
    table["cpu_latency"] = table.apply(lambda row: _format_latency(row, "cpu"), axis=1)
    table["gpu_latency"] = table.apply(lambda row: _format_latency(row, "cuda"), axis=1)
    table["cpu_throughput"] = table.get("cpu_throughput_predictions_per_second", pd.Series(np.nan, index=table.index)).map(
        lambda value: "n/a" if pd.isna(value) else f"{value:.1f}"
    )
    table["gpu_throughput"] = table.get("cuda_throughput_predictions_per_second", pd.Series(np.nan, index=table.index)).map(
        lambda value: "n/a" if pd.isna(value) else f"{value:.1f}"
    )

    models = table["model_key"].tolist()
    mae_winner = table.loc[table["loocv_mae_mean_h"].idxmin(), "model_key"]
    recommendations: list[str] = []
    if "cpu_p50_ms" in table:
        cpu_winner = table.loc[table["cpu_p50_ms"].idxmin(), "model_key"]
        recommendations.append(f"- CPU warm-forward nhanh nhất trong lần đo này: **Model {cpu_winner}**.")
    if "cuda_p50_ms" in table:
        cuda_winner = table.loc[table["cuda_p50_ms"].idxmin(), "model_key"]
        recommendations.append(f"- GPU warm-forward nhanh nhất trong lần đo này: **Model {cuda_winner}**.")
    recommendations.append(f"- MAE LOOCV tốt nhất của run hiện tại: **Model {mae_winner}**.")

    lines = [
        "# Báo cáo so sánh tốc độ dự đoán — Strawberry RUL",
        "",
        "## Phạm vi và phương pháp",
        "",
        f"- Run đánh giá: `{run_root.relative_to(PROJECT_ROOT)}`",
        f"- Checkpoint đại diện: `{benchmark_config['checkpoint_fold']}` cho mỗi A/B/C/D.",
        f"- Input: batch={benchmark_config['batch_size']}, sequence={benchmark_config['seq_len']} ảnh, 3×{benchmark_config['image_size']}×{benchmark_config['image_size']}; fusion=`{benchmark_config['fusion_mode']}`.",
        f"- Chế độ: FP32, `model.eval()`, `torch.inference_mode()`, warm-up={benchmark_config['warmup']}, đo={benchmark_config['iterations']} lượt/device.",
        "- Latency là **steady-state model-forward**. Tensor đã nằm trên device; không gồm JPEG decode, segmentation, resize/normalization, CPU→GPU transfer, HTTP/network hay lazy model loading.",
        "- Vì vậy đây là bảng so sánh kiến trúc công bằng, không phải API end-to-end latency.",
        "",
        "## Môi trường benchmark",
        "",
        f"- OS: {hardware['platform']}",
        f"- CPU: {hardware['cpu']} ({hardware['logical_cpu_count']} logical CPUs; PyTorch threads={hardware['torch_num_threads']})",
        f"- PyTorch: {hardware['torch_version']}",
    ]
    if hardware.get("cuda_available"):
        lines.extend(
            [
                f"- GPU: {hardware.get('cuda_device')} ({hardware.get('cuda_total_memory_mib')} MiB), CUDA {hardware.get('cuda_runtime')}",
                f"- CUDA flags: cudnn.benchmark={hardware.get('cudnn_benchmark')}, TF32 matmul={hardware.get('allow_tf32_matmul')}, TF32 cuDNN={hardware.get('allow_tf32_cudnn')}",
            ]
        )

    lines.extend(
        [
            "",
            "## Bảng so sánh",
            "",
            "| Model | Kiến trúc | LOOCV MAE (h) | Params (M) | Checkpoint (MiB) | CPU P50 / P95 (ms) | CPU seq/s | GPU P50 / P95 (ms) | GPU seq/s |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in table.itertuples(index=False):
        lines.append(
            "| {model} | {architecture} | {mae} | {params} | {size} | {cpu_latency} | {cpu_tps} | {gpu_latency} | {gpu_tps} |".format(
                model=row.model_key,
                architecture=row.architecture,
                mae=row.loocv_mae,
                params=row.parameters_m,
                size=row.checkpoint_mib,
                cpu_latency=row.cpu_latency,
                cpu_tps=row.cpu_throughput,
                gpu_latency=row.gpu_latency,
                gpu_tps=row.gpu_throughput,
            )
        )

    chart_relative_path = Path(os.path.relpath(chart_path, output_path.parent)).as_posix()
    lines.extend(
        [
            "",
            "## Biểu đồ latency",
            "",
            "Cột là P50; đường đen từ đỉnh cột đến vạch ngang là khoảng P50 → P95.",
            "",
            f"![Biểu đồ latency dự đoán]({chart_relative_path})",
        ]
    )
    lines.extend(["", "## Kết luận deployment", "", *recommendations, ""])
    if mae_winner in models:
        winner = table.loc[table["model_key"] == mae_winner].iloc[0]
        lines.append(
            f"- Với dữ liệu hiện tại, **Model {mae_winner}** là điểm xuất phát ưu tiên vì có MAE LOOCV thấp nhất "
            f"({winner.loocv_mae_mean_h:.2f} h) và checkpoint {winner.checkpoint_size_mib:.2f} MiB."
        )
    lines.extend(
        [
            "",
            "## Điều kiện để gọi là real deployment",
            "",
            "- Cần đo riêng API end-to-end sau khi backend chạy được: upload/decode → segmentation → tensor preparation/H2D → model → response.",
            "- LOOCV đánh giá chuỗi 8 frame theo thời gian; API hiện nhận một ảnh và lặp ảnh đó thành sequence. Vì vậy accuracy của API một-ảnh chưa được xác nhận tương đương LOOCV.",
            f"- Backend config JSON hợp lệ: **{readiness['config_json_valid']}**.",
        ]
    )
    if readiness.get("config_error"):
        lines.append(f"- Lỗi config hiện tại: `{readiness['config_error']}`")
    if readiness.get("configured_model_path"):
        lines.append(
            f"- Production checkpoint theo config: `{readiness['configured_model_path']}`; tồn tại: **{readiness['configured_model_exists']}**."
        )
    lines.extend(
        [
            f"- Kích thước benchmark/training: {readiness['training_image_size']}×{readiness['training_image_size']}. Cần bảo đảm backend dùng cùng kích thước trước khi benchmark API.",
            "",
            "## Tái lập",
            "",
            "```powershell",
            "$env:PYTHONPATH = \"src\"",
            ".\\.venv\\Scripts\\python -m strawberry.stage5_evaluation.benchmark_inference --run-root output\\runs\\strawberry\\strawberry_loocv_seq8_image_only --devices cpu cuda",
            "```",
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_benchmark(
    run_root: str | Path | None = None,
    *,
    devices: list[str] | None = None,
    models: list[str] | None = None,
    checkpoint_fold: str = "holdout_F01",
    warmup: int = 20,
    iterations: int = 100,
    batch_size: int = 1,
    output_dir: str | Path | None = None,
    graph_dir: str | Path | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    if warmup < 0 or iterations < 1 or batch_size < 1:
        raise ValueError("warmup must be >= 0; iterations and batch_size must be >= 1")

    root = _resolve_run_root(run_root)
    run_config = _load_json(root / "config.json")
    selected_models = [key.upper() for key in (models or ["A", "B", "C", "D"])]
    invalid = sorted(set(selected_models).difference(MODEL_LABELS))
    if invalid:
        raise ValueError(f"Unknown model keys: {', '.join(invalid)}")
    benchmark_devices = _resolve_devices(devices)
    target_output_dir = Path(output_dir) if output_dir is not None else PROJECT_ROOT / "output" / "reports" / "evaluation" / root.name
    if not target_output_dir.is_absolute():
        target_output_dir = PROJECT_ROOT / target_output_dir
    target_output_dir.mkdir(parents=True, exist_ok=True)
    target_graph_dir = Path(graph_dir) if graph_dir is not None else PROJECT_ROOT / "output" / "graphs" / "evaluation" / root.name
    if not target_graph_dir.is_absolute():
        target_graph_dir = PROJECT_ROOT / target_graph_dir

    sequence_length = int(run_config.get("seq_len", 8))
    image_size = int(run_config.get("image_size", 224))
    fusion_mode = str(run_config.get("fusion_mode", "image_only"))
    accuracy = _accuracy_by_model(root)
    rows: list[dict[str, Any]] = []

    for device in benchmark_devices:
        for model_key in selected_models:
            if device.type == "cuda":
                torch.cuda.empty_cache()
            checkpoint_path = _checkpoint_path(root, model_key, checkpoint_fold, run_config)
            model, checkpoint_config, load_time_ms = _load_model(checkpoint_path, model_key, device)
            model_seq_len = int(checkpoint_config.get("seq_len", sequence_length))
            model_image_size = int(checkpoint_config.get("image_size", image_size))
            if (model_seq_len, model_image_size) != (sequence_length, image_size):
                raise ValueError(
                    f"Run config and checkpoint input disagree for Model {model_key}: "
                    f"run=({sequence_length}, {image_size}), checkpoint=({model_seq_len}, {model_image_size})"
                )

            generator = torch.Generator(device=device.type).manual_seed(seed)
            images = torch.randn(
                batch_size,
                sequence_length,
                3,
                image_size,
                image_size,
                generator=generator,
                device=device,
                dtype=torch.float32,
            )
            env = torch.zeros(batch_size, sequence_length, 4, device=device, dtype=torch.float32)
            samples_ms = _measure_forward(model, images, env, device, warmup, iterations)
            mean_ms = float(np.mean(samples_ms))
            count = sum(parameter.numel() for parameter in model.parameters())
            rows.append(
                {
                    "model_key": model_key,
                    "architecture": MODEL_LABELS[model_key],
                    "device": device.type,
                    "device_name": _device_name(device),
                    "checkpoint_fold": checkpoint_fold,
                    "checkpoint_path": str(checkpoint_path.relative_to(PROJECT_ROOT)),
                    "checkpoint_size_mib": checkpoint_path.stat().st_size / (1024**2),
                    "parameter_count": count,
                    "batch_size": batch_size,
                    "seq_len": sequence_length,
                    "image_size": image_size,
                    "fusion_mode": fusion_mode,
                    "warmup_iterations": warmup,
                    "measured_iterations": iterations,
                    "load_time_ms": load_time_ms,
                    "mean_ms": mean_ms,
                    "std_ms": float(np.std(samples_ms, ddof=0)),
                    "p50_ms": _percentile(samples_ms, 50),
                    "p95_ms": _percentile(samples_ms, 95),
                    "min_ms": float(np.min(samples_ms)),
                    "max_ms": float(np.max(samples_ms)),
                    "throughput_predictions_per_second": 1_000.0 * batch_size / mean_ms,
                    **accuracy.get(model_key, {}),
                }
            )
            del images, env, model
            gc.collect()
            if device.type == "cuda":
                torch.cuda.empty_cache()

    results = pd.DataFrame(rows).sort_values(["model_key", "device"]).reset_index(drop=True)
    results.to_csv(target_output_dir / "inference_speed_comparison.csv", index=False)
    benchmark_config = {
        "checkpoint_fold": checkpoint_fold,
        "batch_size": batch_size,
        "seq_len": sequence_length,
        "image_size": image_size,
        "fusion_mode": fusion_mode,
        "warmup": warmup,
        "iterations": iterations,
        "precision": "float32",
        "scope": "loaded_model_forward_only; input tensors already resident on target device",
    }
    hardware = _hardware_metadata(benchmark_devices)
    readiness = _backend_readiness(run_config)
    chart_path = target_graph_dir / "inference_speed_comparison.png"
    _write_latency_chart(results, chart_path, benchmark_config)
    payload = {
        "run_root": str(root.relative_to(PROJECT_ROOT)),
        "benchmark_config": benchmark_config,
        "hardware": hardware,
        "deployment_readiness": readiness,
        "chart_path": str(chart_path.relative_to(PROJECT_ROOT)),
        "results": results.to_dict(orient="records"),
    }
    (target_output_dir / "inference_speed_comparison.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _write_markdown_report(
        target_output_dir / "inference_speed_comparison.md",
        root,
        benchmark_config,
        hardware,
        readiness,
        results,
        chart_path,
    )
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark warm forward-pass speed of the strawberry A/B/C/D models.")
    parser.add_argument("--run-root", type=Path, default=None, help="Completed strawberry run root. Defaults to the latest run.")
    parser.add_argument("--devices", nargs="+", choices=["cpu", "cuda"], default=None, help="Devices to benchmark. Default: cpu and cuda when available.")
    parser.add_argument("--models", nargs="+", default=None, help="Subset of model keys, e.g. A B C D.")
    parser.add_argument("--checkpoint-fold", default="holdout_F01", help="Representative LOOCV checkpoint to load for every model.")
    parser.add_argument("--warmup", type=int, default=20, help="Unreported warm-up forwards per model/device.")
    parser.add_argument("--iterations", type=int, default=100, help="Timed forwards per model/device.")
    parser.add_argument("--batch-size", type=int, default=1, help="Deployment batch size.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Where CSV/JSON/Markdown are written.")
    parser.add_argument("--graph-dir", type=Path, default=None, help="Where the latency PNG is written.")
    parser.add_argument("--seed", type=int, default=42, help="Seed for synthetic benchmark inputs.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = run_benchmark(
        args.run_root,
        devices=args.devices,
        models=args.models,
        checkpoint_fold=args.checkpoint_fold,
        warmup=args.warmup,
        iterations=args.iterations,
        batch_size=args.batch_size,
        output_dir=args.output_dir,
        graph_dir=args.graph_dir,
        seed=args.seed,
    )
    print("\nWarm model-forward latency (ms):")
    print(
        results[
            [
                "model_key",
                "device",
                "mean_ms",
                "p50_ms",
                "p95_ms",
                "throughput_predictions_per_second",
            ]
        ].to_string(index=False, float_format=lambda value: f"{value:.3f}")
    )


if __name__ == "__main__":
    main()
