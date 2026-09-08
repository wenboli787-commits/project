"""Matplotlib-only plots written to the evaluation output's plots directory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from canonical_motion import CanonicalMotion


def _nested(data: dict[str, Any], *keys: str) -> Any:
    value: Any = data
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _numeric(value: Any) -> float | None:
    return float(value) if isinstance(value, (float, int, np.floating, np.integer)) and np.isfinite(value) else None


def save_plots(out_dir: Path, references: dict[str, CanonicalMotion], candidates: dict[str, CanonicalMotion], summaries: dict[str, dict[str, Any]], per_frame: dict[str, dict[str, np.ndarray]]) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    files.extend(_metric_bar_chart(out_dir, summaries))
    files.extend(_root_trajectory_plot(out_dir, references, candidates))
    files.extend(_per_frame_error_plot(out_dir, per_frame))
    return files


def _metric_bar_chart(out_dir: Path, summaries: dict[str, dict[str, Any]]) -> list[Path]:
    metrics = {
        "End-effector mean error (m)": ("end_effector_position_error", "aggregate_mean"),
        "Root position mean error (m)": ("root_trajectory_error", "position", "mean"),
        "Joint-limit violation ratio": ("joint_limit_violation", "violation_frame_ratio"),
        "Fall rate": ("stability", "fall_rate"),
        "Mean DOF jerk": ("smoothness", "dof", "mean_jerk"),
    }
    names = list(summaries)
    values_by_metric: dict[str, list[float | None]] = {}
    for label, path in metrics.items():
        values_by_metric[label] = [_numeric(_nested(summaries[name], *path)) for name in names]
    fig, axes = plt.subplots(len(metrics), 1, figsize=(9, 3.0 * len(metrics)), constrained_layout=True)
    for axis, (label, values) in zip(np.atleast_1d(axes), values_by_metric.items()):
        clean = [value if value is not None else 0.0 for value in values]
        bars = axis.bar(names, clean, color=["#5173b8", "#db9254", "#5b9c73"][:len(names)])
        axis.set_title(label)
        axis.grid(axis="y", alpha=0.25)
        for bar, value in zip(bars, values):
            axis.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), "N/A" if value is None else f"{value:.4g}", ha="center", va="bottom", fontsize=8)
    path = out_dir / "method_comparison.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return [path]


def _root_trajectory_plot(out_dir: Path, references: dict[str, CanonicalMotion], candidates: dict[str, CanonicalMotion]) -> list[Path]:
    fig, axis = plt.subplots(figsize=(8, 6), constrained_layout=True)
    plotted = False
    for method, motion in candidates.items():
        if motion.root_pos is not None:
            axis.plot(motion.root_pos[:, 0], motion.root_pos[:, 1], label=method, linewidth=2)
            plotted = True
        reference = references.get(method)
        if reference is not None and reference.root_pos is not None:
            axis.plot(reference.root_pos[:, 0], reference.root_pos[:, 1], label=f"reference ({method})", linestyle="--", alpha=0.55)
    if not plotted:
        plt.close(fig)
        return []
    axis.set_title("Root XY trajectory")
    axis.set_xlabel("X (m)")
    axis.set_ylabel("Y (m)")
    axis.axis("equal")
    axis.grid(alpha=0.25)
    axis.legend(fontsize=8)
    path = out_dir / "root_xy_trajectory.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return [path]


def _per_frame_error_plot(out_dir: Path, per_frame: dict[str, dict[str, np.ndarray]]) -> list[Path]:
    keys = ("end_effector_error.left_hand", "end_effector_error.right_hand", "end_effector_error.left_foot", "end_effector_error.right_foot", "end_effector_error.head", "root_error.position")
    fig, axis = plt.subplots(figsize=(10, 5), constrained_layout=True)
    plotted = False
    for method, data in per_frame.items():
        for key in keys:
            if key not in data:
                continue
            axis.plot(data[key], label=f"{method}: {key.replace('end_effector_error.', '')}", alpha=0.8)
            plotted = True
    if not plotted:
        plt.close(fig)
        return []
    axis.set_title("Per-frame position error")
    axis.set_xlabel("Frame")
    axis.set_ylabel("Error (m)")
    axis.grid(alpha=0.25)
    axis.legend(fontsize=7, ncol=2)
    path = out_dir / "per_frame_position_errors.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return [path]
