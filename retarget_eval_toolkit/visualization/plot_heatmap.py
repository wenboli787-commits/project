from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def plot_heatmap(df: pd.DataFrame, out_path: str | Path, metric: str = "overall_score") -> bool:
    """Plot per-motion/method heatmap for one metric."""
    if df.empty or metric not in df.columns:
        return False
    pivot = df.pivot_table(index="motion", columns="method", values=metric, aggfunc="mean")
    if pivot.empty or pivot.isna().all().all():
        return False
    fig, ax = plt.subplots(figsize=(max(7, 1.1 * len(pivot.columns)), max(5, 0.35 * len(pivot.index))))
    im = ax.imshow(pivot.fillna(0.0).to_numpy(), aspect="auto", cmap="viridis", vmin=0, vmax=100 if metric.endswith("score") else None)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=30, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_title(metric)
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            value = pivot.iloc[i, j]
            text = "NA" if pd.isna(value) else f"{value:.1f}"
            ax.text(j, i, text, ha="center", va="center", color="white", fontsize=8)
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return True

