from __future__ import annotations

from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def plot_bar(df: pd.DataFrame, metric: str, out_path: str | Path, *, title: str | None = None, ylabel: str | None = None) -> bool:
    """Generate a method-level bar chart for a metric."""
    if df.empty or metric not in df.columns:
        return False
    data = df.groupby("method", as_index=False)[metric].mean(numeric_only=True)
    values = pd.to_numeric(data[metric], errors="coerce")
    if values.notna().sum() == 0:
        return False
    plt.figure(figsize=(8, 5))
    bars = plt.bar(data["method"].astype(str), values)
    plt.title(title or metric)
    plt.xlabel("method")
    plt.ylabel(ylabel or metric)
    plt.grid(axis="y", alpha=0.3)
    for bar, value in zip(bars, values):
        if pd.notna(value):
            plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{value:.3g}", ha="center", va="bottom", fontsize=9)
    plt.tight_layout()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=180)
    plt.close()
    return True

