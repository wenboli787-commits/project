from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def plot_curve(df: pd.DataFrame, metric: str, out_path: str | Path, *, title: str | None = None, ylabel: str | None = None) -> bool:
    """Generate per-frame line curves for one metric."""
    if df.empty or metric not in df.columns:
        return False
    plotted = False
    plt.figure(figsize=(10, 5))
    for label_cols, group in df.groupby(["motion", "method"]):
        values = pd.to_numeric(group[metric], errors="coerce")
        if values.notna().sum() == 0:
            continue
        x = pd.to_numeric(group.get("time", group["frame"]), errors="coerce")
        label = " / ".join(map(str, label_cols))
        plt.plot(x, values, linewidth=1.5, label=label)
        plotted = True
    if not plotted:
        plt.close()
        return False
    plt.title(title or metric)
    plt.xlabel("time (s)")
    plt.ylabel(ylabel or metric)
    plt.grid(alpha=0.3)
    plt.legend(fontsize=7, ncol=2)
    plt.tight_layout()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=180)
    plt.close()
    return True


def plot_single_motion_curves(df: pd.DataFrame, out_dir: str | Path) -> list[str]:
    """Generate required per-frame curves grouped by motion/method."""
    metrics = [
        "root_position_error_per_frame",
        "mpjpe_per_frame",
        "left_foot_penetration_per_frame",
        "right_foot_penetration_per_frame",
        "left_foot_sliding_per_frame",
        "right_foot_sliding_per_frame",
    ]
    out_dir = Path(out_dir)
    files = []
    for (motion, method), group in df.groupby(["motion", "method"]):
        for metric in metrics:
            if metric not in group.columns:
                continue
            path = out_dir / f"{motion}_{method}_{metric}.png"
            if plot_curve(group, metric, path, title=f"{motion} / {method} / {metric}"):
                files.append(str(path))
    return files

