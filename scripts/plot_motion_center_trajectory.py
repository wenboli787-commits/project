import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


GMR_ROOT = Path(__file__).resolve().parents[1]
WORK_ROOT = GMR_ROOT.parent
DEFAULT_BVH = (
    WORK_ROOT
    / "ubisoft-laforge-animation-dataset"
    / "lafan1"
    / "extracted"
    / "dance1_subject2.bvh"
)
DEFAULT_OUT_DIR = GMR_ROOT / "outputs" / "trajectory"

TOKENS = {
    "surface": "#FCFCFD",
    "panel": "#FFFFFF",
    "ink": "#1F2430",
    "muted": "#6F768A",
    "grid": "#E6E8F0",
    "axis": "#D7DBE7",
}
BLUE = {
    "base": "#A3BEFA",
    "mid": "#5477C4",
    "dark": "#2E4780",
}
ORANGE = {
    "base": "#F0986E",
    "dark": "#804126",
}


def parse_root_positions_from_bvh(bvh_path):
    """Read the root Hips translation channels from a LAFAN1 BVH file."""
    bvh_path = Path(bvh_path)
    lines = bvh_path.read_text(encoding="utf-8", errors="ignore").splitlines()

    motion_idx = None
    frame_count = None
    frame_time = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "MOTION":
            motion_idx = idx
        elif stripped.startswith("Frames:"):
            frame_count = int(stripped.split(":", 1)[1].strip())
        elif stripped.startswith("Frame Time:"):
            frame_time = float(stripped.split(":", 1)[1].strip())
            break

    if motion_idx is None or frame_count is None or frame_time is None:
        raise ValueError(f"Could not find MOTION metadata in {bvh_path}")

    data_start = idx + 1
    raw_positions_cm = []
    for line in lines[data_start : data_start + frame_count]:
        if not line.strip():
            continue
        values = [float(value) for value in line.split()]
        if len(values) < 3:
            continue
        raw_positions_cm.append(values[:3])

    if not raw_positions_cm:
        raise ValueError(f"No motion frames found in {bvh_path}")

    raw_positions_cm = np.asarray(raw_positions_cm, dtype=float)
    # Match GMR's LAFAN1 coordinate conversion: BVH cm, Y-up -> MuJoCo/GMR m, Z-up.
    positions_m = np.column_stack(
        [
            raw_positions_cm[:, 0] / 100.0,
            -raw_positions_cm[:, 2] / 100.0,
            raw_positions_cm[:, 1] / 100.0,
        ]
    )
    return positions_m, frame_time


def add_header(fig, title, subtitle):
    fig.text(
        0.075,
        0.955,
        title,
        ha="left",
        va="top",
        fontsize=18,
        fontweight="bold",
        color=TOKENS["ink"],
    )
    fig.text(
        0.075,
        0.915,
        subtitle,
        ha="left",
        va="top",
        fontsize=10.5,
        color=TOKENS["muted"],
    )


def style_axis(ax):
    ax.set_facecolor(TOKENS["panel"])
    ax.grid(True, color=TOKENS["grid"], linewidth=0.9, linestyle="--", alpha=0.85)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(TOKENS["axis"])
        ax.spines[side].set_linewidth(1.1)
    ax.tick_params(colors=TOKENS["muted"], labelsize=9)
    ax.xaxis.label.set_color(TOKENS["ink"])
    ax.yaxis.label.set_color(TOKENS["ink"])


def save_csv(csv_path, positions, frame_time):
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["frame", "time_s", "center_x_m", "center_y_m", "center_z_m"])
        for frame, (x, y, z) in enumerate(positions):
            writer.writerow([frame, frame * frame_time, x, y, z])


def plot_trajectory(bvh_path, output_png, output_csv):
    positions, frame_time = parse_root_positions_from_bvh(bvh_path)
    frames = np.arange(len(positions))
    time_s = frames * frame_time

    total_distance_xy = float(np.sum(np.linalg.norm(np.diff(positions[:, :2], axis=0), axis=1)))
    displacement_xy = float(np.linalg.norm(positions[-1, :2] - positions[0, :2]))
    height_range = float(np.max(positions[:, 2]) - np.min(positions[:, 2]))

    output_png.parent.mkdir(parents=True, exist_ok=True)
    save_csv(output_csv, positions, frame_time)

    plt.rcParams.update(
        {
            "font.family": ["Segoe UI", "DejaVu Sans", "Arial", "sans-serif"],
            "axes.titleweight": "bold",
            "figure.facecolor": TOKENS["surface"],
            "savefig.facecolor": TOKENS["surface"],
        }
    )

    fig = plt.figure(figsize=(12.8, 7.2), dpi=150)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.45, 1.0], height_ratios=[1.0, 0.42])
    ax_xy = fig.add_subplot(gs[:, 0])
    ax_z = fig.add_subplot(gs[0, 1])
    ax_stats = fig.add_subplot(gs[1, 1])

    add_header(
        fig,
        "LAFAN1 motion center trajectory",
        f"Source: {Path(bvh_path).name}; center point = BVH Hips/root translated to GMR coordinates, meters.",
    )

    style_axis(ax_xy)
    ax_xy.plot(positions[:, 0], positions[:, 1], color=BLUE["mid"], linewidth=2.2)
    ax_xy.scatter(positions[0, 0], positions[0, 1], s=70, color=ORANGE["base"], edgecolor=ORANGE["dark"], zorder=3)
    ax_xy.scatter(positions[-1, 0], positions[-1, 1], s=70, color=BLUE["base"], edgecolor=BLUE["dark"], zorder=3)
    ax_xy.annotate(
        "start",
        xy=(positions[0, 0], positions[0, 1]),
        xytext=(8, 8),
        textcoords="offset points",
        color=ORANGE["dark"],
        fontsize=9,
        fontweight="bold",
    )
    ax_xy.annotate(
        "end",
        xy=(positions[-1, 0], positions[-1, 1]),
        xytext=(8, -14),
        textcoords="offset points",
        color=BLUE["dark"],
        fontsize=9,
        fontweight="bold",
    )
    ax_xy.set_title("Top-view path on the ground plane", loc="left", color=TOKENS["ink"], fontsize=12)
    ax_xy.set_xlabel("X position (m)")
    ax_xy.set_ylabel("Y position (m)")
    ax_xy.axis("equal")

    style_axis(ax_z)
    ax_z.plot(time_s, positions[:, 2], color=BLUE["mid"], linewidth=1.9)
    ax_z.fill_between(time_s, positions[:, 2], np.min(positions[:, 2]), color=BLUE["base"], alpha=0.22)
    ax_z.set_title("Vertical center height over time", loc="left", color=TOKENS["ink"], fontsize=12)
    ax_z.set_xlabel("Time (s)")
    ax_z.set_ylabel("Z height (m)")

    ax_stats.axis("off")
    ax_stats.set_facecolor(TOKENS["panel"])
    stats = [
        ("Frames", f"{len(positions):,}"),
        ("Duration", f"{time_s[-1]:.2f} s"),
        ("XY path length", f"{total_distance_xy:.2f} m"),
        ("XY displacement", f"{displacement_xy:.2f} m"),
        ("Height range", f"{height_range:.2f} m"),
    ]
    y = 0.9
    for label, value in stats:
        ax_stats.text(0.0, y, label, color=TOKENS["muted"], fontsize=10, va="center")
        ax_stats.text(0.98, y, value, color=TOKENS["ink"], fontsize=11, fontweight="bold", ha="right", va="center")
        y -= 0.16

    fig.subplots_adjust(left=0.075, right=0.965, top=0.84, bottom=0.09, wspace=0.28, hspace=0.38)
    fig.savefig(output_png, bbox_inches="tight")
    plt.close(fig)

    return {
        "frames": len(positions),
        "duration_s": time_s[-1],
        "xy_path_length_m": total_distance_xy,
        "xy_displacement_m": displacement_xy,
        "height_range_m": height_range,
        "output_png": str(output_png),
        "output_csv": str(output_csv),
    }


def main():
    parser = argparse.ArgumentParser(description="Plot the center/root trajectory of a LAFAN1 BVH motion.")
    parser.add_argument("--bvh_file", type=Path, default=DEFAULT_BVH)
    parser.add_argument("--output_png", type=Path, default=None)
    parser.add_argument("--output_csv", type=Path, default=None)
    args = parser.parse_args()

    stem = args.bvh_file.stem
    output_png = args.output_png or (DEFAULT_OUT_DIR / f"{stem}_center_trajectory.png")
    output_csv = args.output_csv or (DEFAULT_OUT_DIR / f"{stem}_center_trajectory.csv")
    stats = plot_trajectory(args.bvh_file, output_png, output_csv)
    for key, value in stats.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
