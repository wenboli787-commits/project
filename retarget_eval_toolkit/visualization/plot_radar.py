from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_radar(df: pd.DataFrame, out_path: str | Path) -> bool:
    """Plot the six category scores on a radar chart."""
    metrics = ["similarity_score", "kinematic_score", "physical_score", "contact_score", "stability_score", "smoothness_score"]
    if df.empty or not all(metric in df.columns for metric in metrics):
        return False
    data = df.groupby("method", as_index=False)[metrics].mean(numeric_only=True)
    if data[metrics].isna().all().all():
        return False
    angles = np.linspace(0, 2 * np.pi, len(metrics), endpoint=False).tolist()
    angles += angles[:1]
    fig = plt.figure(figsize=(7, 7))
    ax = plt.subplot(111, polar=True)
    for _, row in data.iterrows():
        values = [float(row[m]) if pd.notna(row[m]) else 0.0 for m in metrics]
        values += values[:1]
        ax.plot(angles, values, linewidth=2, label=str(row["method"]))
        ax.fill(angles, values, alpha=0.12)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([m.replace("_score", "") for m in metrics], fontsize=9)
    ax.set_ylim(0, 100)
    ax.set_title("Six Category Scores")
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1))
    fig.tight_layout()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return True

