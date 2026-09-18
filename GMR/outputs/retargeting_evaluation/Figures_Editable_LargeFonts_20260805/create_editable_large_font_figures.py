"""Generate publication-sized editable SVG/PDF figures and matching PNGs.

The numerical content, method order, colours, labels, representative frames,
camera views, and source data are unchanged.  Text is kept as SVG text
(`svg.fonttype = 'none'`) so it can be edited in Inkscape or Illustrator.
"""

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import colors as mcolors
from matplotlib import font_manager
from PIL import Image


ROOT = Path("/mnt/d/GMR_WORK/GMR")
EVAL_DIR = ROOT / "outputs" / "retargeting_evaluation"
INPUT_CSV = EVAL_DIR / "per_motion_metrics.csv"
FRAME_DIR = EVAL_DIR / "academic_figures" / "uniform_camera_frames"
OUTPUT_DIR = EVAL_DIR / "Figures_Editable_LargeFonts_20260805"

METHODS = ["direct_mapping", "basic_ik", "gmr"]
METHOD_LABELS = {
    "direct_mapping": "Direct Mapping",
    "basic_ik": "Basic IK",
    "gmr": "GMR",
}
METHOD_COLORS = {
    "direct_mapping": "#767676",
    "basic_ik": "#C69320",
    "gmr": "#2F5D8A",
}
REPRESENTATIVE_FRAMES = {"05_04": 180, "135_04": 99}


def configure_fonts() -> None:
    for path in [
        Path("/mnt/c/Windows/Fonts/times.ttf"),
        Path("/mnt/c/Windows/Fonts/timesbd.ttf"),
        Path("/mnt/c/Windows/Fonts/timesi.ttf"),
    ]:
        if path.exists():
            font_manager.fontManager.addfont(str(path))
    plt.rcParams.update(
        {
            "font.family": "Times New Roman",
            "font.size": 10,
            "axes.titlesize": 11.5,
            "axes.titleweight": "bold",
            "axes.labelsize": 10,
            "xtick.labelsize": 9.5,
            "ytick.labelsize": 9.5,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.edgecolor": "#414141",
            "text.color": "#191919",
            "axes.labelcolor": "#292929",
            "xtick.color": "#373737",
            "ytick.color": "#252525",
        }
    )


def bootstrap_mean_ci(values: Iterable[float], seed: int, iterations: int = 20_000) -> tuple[float, float, float]:
    arr = np.asarray(list(values), dtype=float)
    rng = np.random.default_rng(seed)
    samples = rng.choice(arr, size=(iterations, len(arr)), replace=True).mean(axis=1)
    low, high = np.quantile(samples, [0.025, 0.975])
    return float(arr.mean()), float(low), float(high)


def nice_axis_max(max_value: float) -> float:
    if max_value <= 0:
        return 1.0
    rough = max_value / 5.0
    exponent = 10 ** math.floor(math.log10(rough))
    fraction = rough / exponent
    step_fraction = 1 if fraction <= 1 else 2 if fraction <= 2 else 2.5 if fraction <= 2.5 else 5 if fraction <= 5 else 10
    step = step_fraction * exponent
    return math.ceil(max_value / step) * step


def format_tick(value: float, axis_max: float) -> str:
    if axis_max <= 1:
        return f"{value:.2f}"
    if axis_max <= 10:
        return f"{value:.1f}"
    return f"{value:.0f}"


def light_color(color: str, amount: float = 0.55) -> tuple[float, float, float]:
    rgb = np.asarray(mcolors.to_rgb(color))
    return tuple(rgb * (1.0 - amount) + amount)


def save_figure(fig: plt.Figure, stem: str) -> None:
    fig.savefig(OUTPUT_DIR / f"{stem}.svg", format="svg", facecolor="white")
    fig.savefig(OUTPUT_DIR / f"{stem}.pdf", format="pdf", facecolor="white")
    fig.savefig(OUTPUT_DIR / f"{stem}.png", format="png", dpi=400, facecolor="white")
    plt.close(fig)


def create_four_panel(
    df: pd.DataFrame,
    stem: str,
    title: str,
    panels: list[tuple[str, str, float]],
    seed: int,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(6.35, 4.76))
    fig.subplots_adjust(left=0.175, right=0.985, top=0.855, bottom=0.135, wspace=0.60, hspace=0.57)
    fig.suptitle(title, fontsize=15.5, fontweight="bold", y=0.965)

    y_positions = np.array([2.0, 1.0, 0.0])
    jitter = np.linspace(-0.14, 0.14, 9)
    for panel_index, (ax, (column, panel_title, multiplier)) in enumerate(zip(axes.flat, panels)):
        all_values = pd.to_numeric(df[column], errors="coerce").to_numpy(dtype=float) * multiplier
        axis_max = nice_axis_max(float(np.nanmax(all_values)) * 1.07)
        ax.set_xlim(0.0, axis_max)
        ax.set_ylim(-0.42, 2.42)
        ticks = np.linspace(0.0, axis_max, 6)
        ax.set_xticks(ticks, [format_tick(value, axis_max) for value in ticks])
        ax.set_yticks(y_positions, [METHOD_LABELS[method] for method in METHODS])
        ax.set_title(panel_title, pad=7)
        ax.grid(axis="x", color="#DEDEDE", linewidth=0.7)
        ax.tick_params(axis="x", length=3, width=0.7, pad=3)
        ax.tick_params(axis="y", length=0, pad=5)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_linewidth(0.8)

        for method_index, (method, y) in enumerate(zip(METHODS, y_positions)):
            values = pd.to_numeric(
                df[df["method"] == method].sort_values("motion_name")[column], errors="coerce"
            ).to_numpy(dtype=float) * multiplier
            mean, ci_low, ci_high = bootstrap_mean_ci(values, seed + 100 * panel_index + method_index)
            color = METHOD_COLORS[method]
            ax.scatter(
                values,
                y + jitter,
                s=17,
                color=light_color(color),
                edgecolor=color,
                linewidth=0.55,
                zorder=3,
            )
            ax.errorbar(
                mean,
                y,
                xerr=np.array([[mean - ci_low], [ci_high - mean]]),
                fmt="none",
                ecolor=color,
                elinewidth=1.7,
                capsize=3.5,
                capthick=1.25,
                zorder=4,
            )
            ax.scatter(mean, y, marker="D", s=38, color=color, edgecolor="#202020", linewidth=0.55, zorder=5)
            align_right = mean > axis_max * 0.82
            ax.annotate(
                format_tick(mean, axis_max),
                (mean, y),
                xytext=(-5 if align_right else 5, 7),
                textcoords="offset points",
                ha="right" if align_right else "left",
                va="center",
                fontsize=9.2,
                bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.6, "alpha": 0.9},
                zorder=6,
            )

    fig.text(
        0.5,
        0.035,
        "Lower is better. Points show individual motions; diamonds show arithmetic means; bars show 95% bootstrap CIs (n = 9).",
        ha="center",
        va="center",
        fontsize=8.6,
        color="#464646",
    )
    save_figure(fig, stem)


def create_jerk(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(6.35, 2.38))
    fig.subplots_adjust(left=0.205, right=0.985, top=0.76, bottom=0.31)
    fig.suptitle("Temporal consistency across nine motions", fontsize=15.5, fontweight="bold", y=0.955)
    ax.set_xscale("log")
    ticks = [20, 50, 100, 200, 500, 1000, 2000, 5000]
    ax.set_xlim(20, 5000)
    ax.set_xticks(ticks, [f"{value:,}" for value in ticks])
    ax.set_xlabel("RMS joint jerk (rad/s^3, logarithmic scale)", labelpad=5)
    y_positions = np.array([2.0, 1.0, 0.0])
    ax.set_ylim(-0.45, 2.45)
    ax.set_yticks(y_positions, [METHOD_LABELS[method] for method in METHODS])
    ax.grid(axis="x", color="#DEDEDE", linewidth=0.7)
    ax.tick_params(axis="x", length=3, width=0.7, pad=3)
    ax.tick_params(axis="y", length=0, pad=6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_linewidth(0.8)

    jitter = np.linspace(-0.14, 0.14, 9)
    for index, (method, y) in enumerate(zip(METHODS, y_positions)):
        values = pd.to_numeric(
            df[df["method"] == method].sort_values("motion_name")["rms_joint_jerk"], errors="coerce"
        ).to_numpy(dtype=float)
        mean, ci_low, ci_high = bootstrap_mean_ci(values, 20260722 + index)
        color = METHOD_COLORS[method]
        ax.scatter(values, y + jitter, s=18, color=light_color(color), edgecolor=color, linewidth=0.55, zorder=3)
        ax.errorbar(
            mean,
            y,
            xerr=np.array([[mean - ci_low], [ci_high - mean]]),
            fmt="none",
            ecolor=color,
            elinewidth=1.7,
            capsize=3.5,
            capthick=1.25,
            zorder=4,
        )
        ax.scatter(mean, y, marker="D", s=42, color=color, edgecolor="#202020", linewidth=0.55, zorder=5)
        ax.annotate(
            f"{mean:.0f}",
            (mean, y),
            xytext=(6, 7),
            textcoords="offset points",
            fontsize=9.4,
            va="center",
            bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.6, "alpha": 0.9},
        )

    fig.text(
        0.5,
        0.055,
        "Lower is better. The logarithmic axis preserves the large Basic IK values without suppressing the two lower-jerk methods.",
        ha="center",
        va="center",
        fontsize=8.4,
        color="#464646",
    )
    save_figure(fig, "Fig_3X_3_Temporal_Consistency_Editable")


def create_same_frame() -> None:
    fig, axes = plt.subplots(2, 3, figsize=(6.35, 3.49))
    fig.subplots_adjust(left=0.17, right=0.99, top=0.79, bottom=0.14, wspace=0.055, hspace=0.11)
    fig.suptitle("Uniform-camera same-frame comparison", fontsize=15.5, fontweight="bold", y=0.965)

    row_labels = {
        "05_04": ("05_04", "Whole-body motion", "Frame 180 / 6.0 s"),
        "135_04": ("135_04", "Front kick", "Frame 99 / 3.3 s"),
    }
    for row_index, (motion, frame_index) in enumerate(REPRESENTATIVE_FRAMES.items()):
        for column_index, method in enumerate(METHODS):
            ax = axes[row_index, column_index]
            frame_path = FRAME_DIR / f"{motion}_{method}_frame_{frame_index}.png"
            if not frame_path.is_file():
                raise FileNotFoundError(frame_path)
            ax.imshow(Image.open(frame_path).convert("RGB"))
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_color("#787878")
                spine.set_linewidth(0.65)
            if row_index == 0:
                ax.set_title(METHOD_LABELS[method], color=METHOD_COLORS[method], fontsize=10.8, pad=5)

        label_a, label_b, label_c = row_labels[motion]
        y = 0.595 if row_index == 0 else 0.285
        fig.text(0.083, y + 0.035, label_a, ha="center", va="center", fontsize=10.5, fontweight="bold")
        fig.text(0.083, y - 0.010, label_b, ha="center", va="center", fontsize=9.2)
        fig.text(0.083, y - 0.052, label_c, ha="center", va="center", fontsize=8.8, color="#505050")

    fig.text(
        0.5,
        0.055,
        "Same frame, fixed world camera, equal scale, and canonical root pose: position (0, 0, 0.72 m), yaw 0 deg.",
        ha="center",
        va="center",
        fontsize=8.5,
        color="#464646",
    )
    save_figure(fig, "Fig_3X_4_Same_Frame_Comparison_Editable")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    configure_fonts()
    df = pd.read_csv(INPUT_CSV)
    if len(df) != 27 or set(df["method"].unique()) != set(METHODS):
        raise ValueError("Expected 27 rows from exactly three methods")

    create_four_panel(
        df,
        "Fig_3X_1_Motion_Preservation_Editable",
        "Motion-preservation errors across nine motions",
        [
            ("root_relative_position_error_mean", "Root-relative error (m)", 1.0),
            ("scale_normalised_position_error_mean", "Scale-normalised error (m)", 1.0),
            ("end_effector_error_mean", "End-effector error (m)", 1.0),
            ("body_orientation_error_mean", "Body-orientation error (deg)", 1.0),
        ],
        seed=20260722,
    )
    create_four_panel(
        df,
        "Fig_3X_2_Physical_Plausibility_Editable",
        "Physical-plausibility indicators across nine motions",
        [
            ("total_foot_sliding_distance", "Foot sliding (m)", 1.0),
            ("maximum_ground_penetration", "Max. penetration (cm)", 100.0),
            ("self_collision_frame_ratio", "MuJoCo collision proxy (%)", 100.0),
            ("joint_limit_violation_ratio", "Joint-limit frames (zero tol., %)", 100.0),
        ],
        seed=20260822,
    )
    create_jerk(df)
    create_same_frame()

    metadata = {
        "source": str(INPUT_CSV),
        "method_order": METHODS,
        "motion_count": int(df["motion_name"].nunique()),
        "figure_width_inches": 6.35,
        "font_family": "Times New Roman",
        "svg_text_editable": True,
        "bootstrap": {"iterations": 20000, "confidence": 0.95, "seed_base": 20260722},
        "qualitative_frames": REPRESENTATIVE_FRAMES,
        "qualitative_source_frames": str(FRAME_DIR),
        "unchanged_content": ["data", "labels", "method_order", "colours", "camera", "robot_pose"],
    }
    (OUTPUT_DIR / "figure_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT_DIR / "README_可编辑图片说明.txt").write_text(
        "SVG：可在 Inkscape、Adobe Illustrator 等软件中编辑文字、线条和数据点。\n"
        "PDF：矢量论文插图版本。\n"
        "PNG：400 DPI，可直接插入 Word。\n"
        "图 3.X-4 的机器人截图来自原始固定相机渲染，因此截图本身为栅格；图中的文字和排版元素在 SVG 中可编辑。\n"
        "所有数值、标签、方法顺序、颜色、帧号、相机参数和机器人姿态均未改变，仅提高图中文字的论文尺寸可读性。\n",
        encoding="utf-8",
    )
    shutil.copy2(Path(__file__), OUTPUT_DIR / Path(__file__).name)
    print(OUTPUT_DIR)


if __name__ == "__main__":
    main()
