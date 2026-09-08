from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np


FIGURE_FILENAMES = [
    "success_rate_bar.png",
    "global_error_bar.png",
    "root_relative_error_bar.png",
    "foot_sliding_bar.png",
    "ground_penetration_bar.png",
    "self_collision_bar.png",
    "sudden_jumps_bar.png",
    "per_motion_metrics_line.png",
    "overall_score_heatmap.png",
    "overall_radar.png",
    "keypoint_error_heatmap.png",
]


def generate_figures(
    per_motion_rows: List[Dict[str, Any]],
    summary_rows: List[Dict[str, Any]],
    keypoint_rows: List[Dict[str, Any]],
    figures_dir: Path,
) -> Tuple[List[str], List[str]]:
    """Generate PNG figures and return relative filenames plus warnings."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    warnings: List[str] = []
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore

        _generate_matplotlib_figures(plt, per_motion_rows, summary_rows, keypoint_rows, figures_dir)
    except Exception as exc:
        warnings.append(f"matplotlib unavailable or plotting failed ({exc}); generated simplified fallback PNG figures.")
        _generate_fallback_figures(per_motion_rows, summary_rows, keypoint_rows, figures_dir)
    return [str(figures_dir / name) for name in FIGURE_FILENAMES if (figures_dir / name).exists()], warnings


def _generate_matplotlib_figures(plt: Any, per_motion: List[Dict[str, Any]], summary: List[Dict[str, Any]], keypoints: List[Dict[str, Any]], out: Path) -> None:
    method_order = [row["method"] for row in summary]
    _bar(plt, method_order, [row.get("success_rate", np.nan) for row in summary], out / "success_rate_bar.png", "Success Rate", "rate")
    _bar(plt, method_order, [row.get("mean_aligned_global_error_mm", np.nan) for row in summary], out / "global_error_bar.png", "Aligned Global Error", "mm")
    _bar(plt, method_order, [row.get("mean_root_relative_error_mm", np.nan) for row in summary], out / "root_relative_error_bar.png", "Root-relative Error", "mm")
    _bar(plt, method_order, [row.get("mean_total_foot_sliding_m", np.nan) for row in summary], out / "foot_sliding_bar.png", "Foot Sliding", "m")
    _bar(plt, method_order, [row.get("mean_max_ground_penetration_m", np.nan) for row in summary], out / "ground_penetration_bar.png", "Ground Penetration", "m")
    _bar(plt, method_order, [row.get("mean_self_collision_count", np.nan) for row in summary], out / "self_collision_bar.png", "Self Collision Count", "count")
    _bar(plt, method_order, [row.get("mean_sudden_jump_count", np.nan) for row in summary], out / "sudden_jumps_bar.png", "Sudden Jumps", "count")
    _line_per_motion(plt, per_motion, out / "per_motion_metrics_line.png")
    _heatmap(plt, _matrix(per_motion, "motion_name", "method", "overall_score"), out / "overall_score_heatmap.png", "Overall Score")
    _radar(plt, per_motion, method_order, out / "overall_radar.png")
    _heatmap(plt, _matrix(keypoints, "keypoint", "method", "root_relative_error_mm"), out / "keypoint_error_heatmap.png", "Keypoint Root-relative Error (mm)")


def _bar(plt: Any, labels: Sequence[str], values: Sequence[Any], path: Path, title: str, ylabel: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.8))
    vals = [_to_float(v) for v in values]
    ax.bar(labels, vals, color=["#4C78A8", "#F58518", "#54A24B", "#B279A2"][: len(labels)])
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _line_per_motion(plt: Any, rows: List[Dict[str, Any]], path: Path) -> None:
    motions = sorted({str(row.get("motion_name", "")) for row in rows})
    methods = sorted({str(row.get("method", "")) for row in rows})
    fig, ax = plt.subplots(figsize=(10, 5))
    for method in methods:
        values = []
        for motion in motions:
            match = next((row for row in rows if row.get("motion_name") == motion and row.get("method") == method), None)
            values.append(_to_float(match.get("overall_score", np.nan)) if match else np.nan)
        ax.plot(motions, values, marker="o", label=method)
    ax.set_title("Per-motion Overall Score")
    ax.set_ylabel("score")
    ax.grid(alpha=0.25)
    ax.legend()
    ax.tick_params(axis="x", rotation=35)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _heatmap(plt: Any, matrix_data: Tuple[List[str], List[str], np.ndarray], path: Path, title: str) -> None:
    rows, cols, matrix = matrix_data
    fig_w = max(6, 0.55 * len(cols) + 3)
    fig_h = max(4, 0.35 * len(rows) + 2)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    image = ax.imshow(matrix, aspect="auto", cmap="viridis")
    ax.set_title(title)
    ax.set_xticks(np.arange(len(cols)), labels=cols, rotation=25, ha="right")
    ax.set_yticks(np.arange(len(rows)), labels=rows)
    fig.colorbar(image, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _radar(plt: Any, rows: List[Dict[str, Any]], methods: List[str], path: Path) -> None:
    axes = [
        "normalized_success",
        "normalized_root_relative_error",
        "normalized_global_error",
        "normalized_foot_sliding",
        "normalized_ground_penetration",
        "normalized_sudden_jumps",
        "normalized_self_collision",
    ]
    labels = ["Success", "Pose", "Global", "Foot", "Ground", "Jumps", "Collision"]
    theta = np.linspace(0, 2 * np.pi, len(axes), endpoint=False)
    theta = np.concatenate([theta, theta[:1]])
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw={"projection": "polar"})
    for method in methods:
        subset = [row for row in rows if row.get("method") == method]
        values = []
        for axis in axes:
            values.append(_safe_mean([row.get(axis, np.nan) for row in subset]))
        values = np.asarray(values, dtype=float)
        values = np.nan_to_num(values, nan=0.0)
        values = np.concatenate([values, values[:1]])
        ax.plot(theta, values, marker="o", label=method)
        ax.fill(theta, values, alpha=0.12)
    ax.set_xticks(theta[:-1], labels)
    ax.set_ylim(0, 1)
    ax.set_title("Overall Radar")
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1))
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _matrix(rows: List[Dict[str, Any]], row_key: str, col_key: str, value_key: str) -> Tuple[List[str], List[str], np.ndarray]:
    row_names = sorted({str(row.get(row_key, "")) for row in rows if row.get(row_key) is not None})
    col_names = sorted({str(row.get(col_key, "")) for row in rows if row.get(col_key) is not None})
    matrix = np.full((len(row_names), len(col_names)), np.nan, dtype=float)
    for i, rname in enumerate(row_names):
        for j, cname in enumerate(col_names):
            vals = [_to_float(row.get(value_key, np.nan)) for row in rows if str(row.get(row_key, "")) == rname and str(row.get(col_key, "")) == cname]
            matrix[i, j] = _safe_mean(vals)
    if matrix.size == 0:
        matrix = np.zeros((1, 1), dtype=float)
        row_names = ["none"]
        col_names = ["none"]
    return row_names, col_names, matrix


def _generate_fallback_figures(per_motion: List[Dict[str, Any]], summary: List[Dict[str, Any]], keypoints: List[Dict[str, Any]], out: Path) -> None:
    values_by_file = {
        "success_rate_bar.png": [row.get("success_rate", np.nan) for row in summary],
        "global_error_bar.png": [row.get("mean_aligned_global_error_mm", np.nan) for row in summary],
        "root_relative_error_bar.png": [row.get("mean_root_relative_error_mm", np.nan) for row in summary],
        "foot_sliding_bar.png": [row.get("mean_total_foot_sliding_m", np.nan) for row in summary],
        "ground_penetration_bar.png": [row.get("mean_max_ground_penetration_m", np.nan) for row in summary],
        "self_collision_bar.png": [row.get("mean_self_collision_count", np.nan) for row in summary],
        "sudden_jumps_bar.png": [row.get("mean_sudden_jump_count", np.nan) for row in summary],
        "per_motion_metrics_line.png": [row.get("overall_score", np.nan) for row in per_motion],
        "overall_score_heatmap.png": [row.get("overall_score", np.nan) for row in per_motion],
        "overall_radar.png": [row.get("mean_overall_score", np.nan) for row in summary],
        "keypoint_error_heatmap.png": [row.get("root_relative_error_mm", np.nan) for row in keypoints],
    }
    for name, values in values_by_file.items():
        _write_simple_png(out / name, values)


def _write_simple_png(path: Path, values: Sequence[Any], width: int = 900, height: int = 520) -> None:
    """Write a valid simple RGB PNG with colored bars using only stdlib."""
    values = np.asarray([_to_float(v) for v in values], dtype=float)
    finite = np.isfinite(values)
    if not finite.any():
        values = np.asarray([0.0], dtype=float)
        finite = np.asarray([True])
    lo = float(np.nanmin(values[finite]))
    hi = float(np.nanmax(values[finite]))
    denom = hi - lo if abs(hi - lo) > 1e-12 else 1.0
    canvas = np.full((height, width, 3), 255, dtype=np.uint8)
    margin = 60
    plot_w = width - 2 * margin
    plot_h = height - 2 * margin
    canvas[margin : height - margin, margin] = 80
    canvas[height - margin, margin : width - margin] = 80
    colors = np.asarray([[76, 120, 168], [245, 133, 24], [84, 162, 75], [178, 121, 162], [114, 183, 178]], dtype=np.uint8)
    n = max(len(values), 1)
    bar_w = max(3, int(plot_w / (n * 1.4)))
    gap = max(2, int((plot_w - n * bar_w) / max(n, 1)))
    for idx, value in enumerate(values):
        if not np.isfinite(value):
            continue
        norm = (float(value) - lo) / denom
        bar_h = int(norm * (plot_h - 10)) if hi != lo else int(0.65 * plot_h)
        x0 = margin + gap // 2 + idx * (bar_w + gap)
        x1 = min(width - margin, x0 + bar_w)
        y0 = max(margin, height - margin - bar_h)
        canvas[y0 : height - margin, x0:x1] = colors[idx % len(colors)]
    _save_png_rgb(path, canvas)


def _save_png_rgb(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    height, width, _ = image.shape
    raw = b"".join(b"\x00" + image[row].tobytes() for row in range(height))
    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def _safe_mean(values: Sequence[Any]) -> float:
    arr = np.asarray([_to_float(v) for v in values], dtype=float)
    return float(np.nanmean(arr)) if arr.size and np.isfinite(arr).any() else np.nan


def _to_float(value: Any) -> float:
    try:
        return float(np.asarray(value).reshape(-1)[0])
    except Exception:
        return np.nan
