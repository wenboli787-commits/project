"""Create publication-style figures for the retargeting Results section.

The quantitative figures are generated directly from ``per_motion_metrics.csv``.
The qualitative panel uses frames re-rendered from the three PKL trajectories
with one fixed MuJoCo camera and one canonical root pose, so viewpoint,
projection, resolution, robot reference position, and physical scale are
directly comparable.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(r"D:\GMR_WORK")
EVAL_DIR = ROOT / "GMR" / "outputs" / "retargeting_evaluation"
INPUT_CSV = EVAL_DIR / "per_motion_metrics.csv"
FIGURE_DIR = EVAL_DIR / "academic_figures_large_fonts"
# Reuse the already-audited fixed-camera renders; only the figure typography
# and composition are changed in this large-font publication variant.
FRAME_DIR = EVAL_DIR / "academic_figures" / "uniform_camera_frames"

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

VIDEO_DIR = ROOT / "GMR" / "outputs" / "final results"
VIDEO_PATHS = {
    ("05_04", "direct_mapping"): VIDEO_DIR / "videos direct" / "05_04_poses_unitree_g1_direct_mapping_gmr_motion_processing.mp4",
    ("05_04", "basic_ik"): VIDEO_DIR / "videos Basic IK" / "05_04_poses_unitree_g1_basic_ik_pure_unconstrained.mp4",
    ("05_04", "gmr"): VIDEO_DIR / "video gmr" / "05_04_poses_unitree_g1_gmr.mp4",
    ("135_04", "direct_mapping"): VIDEO_DIR / "videos direct" / "135_04_poses_unitree_g1_direct_mapping_gmr_motion_processing.mp4",
    ("135_04", "basic_ik"): VIDEO_DIR / "videos Basic IK" / "135_04_poses_unitree_g1_basic_ik_pure_unconstrained.mp4",
    ("135_04", "gmr"): VIDEO_DIR / "video gmr" / "135_04_poses_unitree_g1_gmr.mp4",
}
REPRESENTATIVE_FRAMES = {
    "05_04": 180,
    "135_04": 99,
}

FONT_REGULAR = Path(r"C:\Windows\Fonts\times.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\timesbd.ttf")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_REGULAR
    return ImageFont.truetype(str(path), size=size)


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def blend(color: str, white_fraction: float) -> tuple[int, int, int]:
    rgb = np.array(hex_rgb(color), dtype=float)
    out = rgb * (1.0 - white_fraction) + 255.0 * white_fraction
    return tuple(int(round(x)) for x in out)


def text_center(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, face, fill=(0, 0, 0)) -> None:
    bbox = draw.textbbox((0, 0), text, font=face)
    draw.text((xy[0] - (bbox[2] - bbox[0]) / 2, xy[1] - (bbox[3] - bbox[1]) / 2), text, font=face, fill=fill)


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


def tick_values(axis_max: float) -> list[float]:
    return [axis_max * index / 5 for index in range(6)]


def format_tick(value: float, axis_max: float) -> str:
    if axis_max <= 1:
        return f"{value:.2f}"
    if axis_max <= 10:
        return f"{value:.1f}"
    return f"{value:.0f}"


def draw_diamond(draw: ImageDraw.ImageDraw, x: float, y: float, radius: int, fill, outline=(20, 20, 20)) -> None:
    points = [(x, y - radius), (x + radius, y), (x, y + radius), (x - radius, y)]
    draw.polygon(points, fill=fill, outline=outline)


def draw_metric_panel(
    draw: ImageDraw.ImageDraw,
    df: pd.DataFrame,
    panel: tuple[int, int, int, int],
    column: str,
    title: str,
    multiplier: float,
    seed: int,
) -> None:
    x0, y0, width, height = panel
    title_font = font(50, bold=True)
    label_font = font(44)
    tick_font = font(40)
    value_font = font(38)
    text_center(draw, (x0 + width / 2, y0 + 42), title, title_font)

    left = x0 + 325
    right = x0 + width - 55
    top = y0 + 115
    bottom = y0 + height - 110

    all_values = pd.to_numeric(df[column], errors="coerce").to_numpy(dtype=float) * multiplier
    axis_max = nice_axis_max(float(np.nanmax(all_values)) * 1.07)
    ticks = tick_values(axis_max)
    for value in ticks:
        x = left + (right - left) * value / axis_max
        draw.line((x, top, x, bottom), fill=(222, 222, 222), width=2)
        label = format_tick(value, axis_max)
        bbox = draw.textbbox((0, 0), label, font=tick_font)
        draw.text((x - (bbox[2] - bbox[0]) / 2, bottom + 16), label, font=tick_font, fill=(55, 55, 55))
    draw.line((left, bottom, right, bottom), fill=(65, 65, 65), width=3)

    y_positions = [top + (bottom - top) * value for value in (0.18, 0.50, 0.82)]
    jitter = np.linspace(-30, 30, 9)
    for method_index, (method, y) in enumerate(zip(METHODS, y_positions)):
        label = METHOD_LABELS[method]
        bbox = draw.textbbox((0, 0), label, font=label_font)
        draw.text((left - 24 - (bbox[2] - bbox[0]), y - (bbox[3] - bbox[1]) / 2), label, font=label_font, fill=(25, 25, 25))

        rows = df[df["method"] == method].sort_values("motion_name")
        values = pd.to_numeric(rows[column], errors="coerce").to_numpy(dtype=float) * multiplier
        mean, ci_low, ci_high = bootstrap_mean_ci(values, seed + method_index)
        color = hex_rgb(METHOD_COLORS[method])
        point_color = blend(METHOD_COLORS[method], 0.38)

        x_low = left + (right - left) * ci_low / axis_max
        x_high = left + (right - left) * ci_high / axis_max
        draw.line((x_low, y, x_high, y), fill=color, width=7)
        draw.line((x_low, y - 13, x_low, y + 13), fill=color, width=5)
        draw.line((x_high, y - 13, x_high, y + 13), fill=color, width=5)

        for value, dy in zip(values, jitter):
            x = left + (right - left) * float(value) / axis_max
            draw.ellipse((x - 11, y + dy - 11, x + 11, y + dy + 11), fill=point_color, outline=color, width=3)

        x_mean = left + (right - left) * mean / axis_max
        draw_diamond(draw, x_mean, y, 19, fill=color)
        mean_label = format_tick(mean, axis_max)
        bbox = draw.textbbox((0, 0), mean_label, font=value_font)
        label_x = min(x_mean + 20, right - (bbox[2] - bbox[0]))
        draw.rectangle((label_x - 4, y - 25, label_x + (bbox[2] - bbox[0]) + 5, y + 27), fill=(255, 255, 255))
        draw.text((label_x, y - 23), mean_label, font=value_font, fill=(20, 20, 20))


def create_multi_panel_figure(
    df: pd.DataFrame,
    output: Path,
    title: str,
    panels: list[tuple[str, str, float]],
    seed: int,
) -> None:
    canvas = Image.new("RGB", (2400, 1800), "white")
    draw = ImageDraw.Draw(canvas)
    text_center(draw, (1200, 76), title, font(68, bold=True))
    positions = [(85, 175, 1085, 700), (1230, 175, 1085, 700), (85, 920, 1085, 700), (1230, 920, 1085, 700)]
    for index, ((column, panel_title, multiplier), position) in enumerate(zip(panels, positions)):
        draw_metric_panel(draw, df, position, column, panel_title, multiplier, seed + 100 * index)
    note = "Lower is better. Points show individual motions; diamonds show arithmetic means; bars show 95% bootstrap CIs (n = 9)."
    text_center(draw, (1200, 1737), note, font(38), fill=(70, 70, 70))
    canvas.save(output, dpi=(300, 300), optimize=True)


def create_jerk_figure(df: pd.DataFrame, output: Path, seed: int = 20260722) -> None:
    canvas = Image.new("RGB", (2400, 900), "white")
    draw = ImageDraw.Draw(canvas)
    text_center(draw, (1200, 72), "Temporal consistency across nine motions", font(68, bold=True))
    left, right, top, bottom = 500, 2270, 195, 650
    ticks = [20, 50, 100, 200, 500, 1000, 2000, 5000]
    log_floor, log_ceiling = 20.0, 5000.0
    all_jerk = pd.to_numeric(df["rms_joint_jerk"], errors="coerce").to_numpy(dtype=float)
    if np.nanmin(all_jerk) < log_floor or np.nanmax(all_jerk) > log_ceiling:
        raise ValueError("RMS jerk values fall outside the explicitly labelled log axis.")
    log_min, log_max = math.log10(log_floor), math.log10(log_ceiling)

    def x_coord(value: float) -> float:
        clipped = min(max(value, log_floor), log_ceiling)
        return left + (right - left) * (math.log10(clipped) - log_min) / (log_max - log_min)

    for value in ticks:
        x = x_coord(value)
        draw.line((x, top, x, bottom), fill=(222, 222, 222), width=2)
        label = f"{value:,}"
        bbox = draw.textbbox((0, 0), label, font=font(40))
        draw.text((x - (bbox[2] - bbox[0]) / 2, bottom + 18), label, font=font(40), fill=(55, 55, 55))
    draw.line((left, bottom, right, bottom), fill=(65, 65, 65), width=3)
    text_center(draw, ((left + right) / 2, 760), "RMS joint jerk (rad/s^3, logarithmic scale)", font(46))

    y_positions = [260, 425, 590]
    jitter = np.linspace(-28, 28, 9)
    for index, (method, y) in enumerate(zip(METHODS, y_positions)):
        label = METHOD_LABELS[method]
        bbox = draw.textbbox((0, 0), label, font=font(48))
        draw.text((left - 30 - (bbox[2] - bbox[0]), y - (bbox[3] - bbox[1]) / 2), label, font=font(48), fill=(25, 25, 25))
        values = pd.to_numeric(df[df["method"] == method].sort_values("motion_name")["rms_joint_jerk"], errors="coerce").to_numpy(dtype=float)
        mean, ci_low, ci_high = bootstrap_mean_ci(values, seed + index)
        color = hex_rgb(METHOD_COLORS[method])
        point_color = blend(METHOD_COLORS[method], 0.38)
        draw.line((x_coord(ci_low), y, x_coord(ci_high), y), fill=color, width=7)
        draw.line((x_coord(ci_low), y - 14, x_coord(ci_low), y + 14), fill=color, width=5)
        draw.line((x_coord(ci_high), y - 14, x_coord(ci_high), y + 14), fill=color, width=5)
        for value, dy in zip(values, jitter):
            x = x_coord(float(value))
            draw.ellipse((x - 12, y + dy - 12, x + 12, y + dy + 12), fill=point_color, outline=color, width=3)
        x_mean = x_coord(mean)
        draw_diamond(draw, x_mean, y, 20, fill=color)
        draw.text((min(x_mean + 26, right - 190), y - 23), f"{mean:.0f}", font=font(40), fill=(20, 20, 20))

    note = "Lower is better. The log scale retains Basic IK while resolving the two lower-jerk methods."
    text_center(draw, (1200, 856), note, font(36), fill=(70, 70, 70))
    canvas.save(output, dpi=(300, 300), optimize=True)


def to_wsl_path(path: Path) -> str:
    drive = path.drive.rstrip(":").lower()
    rest = path.as_posix().split(":", 1)[1]
    return f"/mnt/{drive}{rest}"


def extract_frame(video: Path, frame_index: int, output: Path) -> None:
    if not video.exists():
        raise FileNotFoundError(video)
    output.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        command = [
            "wsl.exe", "-e", "ffmpeg", "-y", "-v", "error",
            "-i", to_wsl_path(video),
            "-vf", f"select=eq(n\\,{frame_index})",
            "-vsync", "0", "-frames:v", "1", to_wsl_path(output),
        ]
    else:
        command = [
            "ffmpeg", "-y", "-v", "error", "-i", str(video),
            "-vf", f"select=eq(n\\,{frame_index})",
            "-vsync", "0", "-frames:v", "1", str(output),
        ]
    subprocess.run(command, check=True)


def fit_image(source: Image.Image, box: tuple[int, int], background=(248, 248, 248)) -> Image.Image:
    target = Image.new("RGB", box, background)
    copy = source.convert("RGB")
    copy.thumbnail(box, Image.Resampling.LANCZOS)
    target.paste(copy, ((box[0] - copy.width) // 2, (box[1] - copy.height) // 2))
    return target


def create_qualitative_figure(output: Path) -> None:
    missing_frames: list[Path] = []
    for motion, frame_index in REPRESENTATIVE_FRAMES.items():
        for method in METHODS:
            frame_path = FRAME_DIR / f"{motion}_{method}_frame_{frame_index}.png"
            if not frame_path.is_file():
                missing_frames.append(frame_path)
    if missing_frames:
        missing_text = "\n".join(str(path) for path in missing_frames)
        raise FileNotFoundError(
            "Uniform-camera frames are missing. Run "
            "bash scripts/render_uniform_comparison_frames.sh in the Ubuntu gmr environment.\n"
            + missing_text
        )

    canvas = Image.new("RGB", (2400, 1320), "white")
    draw = ImageDraw.Draw(canvas)
    text_center(draw, (1200, 68), "Uniform-camera same-frame comparison", font(68, bold=True))

    left_label = 270
    cell_width, cell_height = 650, 480
    gap = 45
    x_positions = [left_label + index * (cell_width + gap) for index in range(3)]
    y_positions = [180, 735]

    for method, x in zip(METHODS, x_positions):
        color = hex_rgb(METHOD_COLORS[method])
        text_center(draw, (x + cell_width / 2, 132), METHOD_LABELS[method], font(50, bold=True), fill=color)
        draw.line((x + 120, 161, x + cell_width - 120, 161), fill=color, width=6)

    row_labels = {
        "05_04": ("05_04", "Whole-body", "Frame 180 / 6.0 s"),
        "135_04": ("135_04", "Front kick", "Frame 99 / 3.3 s"),
    }
    for (motion, frame_index), y in zip(REPRESENTATIVE_FRAMES.items(), y_positions):
        label_a, label_b, label_c = row_labels[motion]
        text_center(draw, (125, y + 180), label_a, font(48, bold=True))
        text_center(draw, (125, y + 238), label_b, font(38))
        text_center(draw, (125, y + 286), label_c, font(34), fill=(80, 80, 80))
        for method, x in zip(METHODS, x_positions):
            frame_path = FRAME_DIR / f"{motion}_{method}_frame_{frame_index}.png"
            frame = fit_image(Image.open(frame_path), (cell_width, cell_height))
            canvas.paste(frame, (x, y))
            draw.rectangle((x, y, x + cell_width, y + cell_height), outline=(120, 120, 120), width=2)

    note = "Fixed camera and scale; root normalised to (0, 0, 0.72 m), yaw 0 deg."
    text_center(draw, (1200, 1274), note, font(38), fill=(70, 70, 70))
    canvas.save(output, dpi=(300, 300), optimize=True)


def main() -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(INPUT_CSV)
    expected = set(METHODS)
    if len(df) != 27 or set(df["method"].unique()) != expected:
        raise ValueError("Expected 27 rows from exactly three methods")

    create_multi_panel_figure(
        df,
        FIGURE_DIR / "figure_motion_preservation.png",
        "Motion-preservation errors across nine motions",
        [
            ("root_relative_position_error_mean", "Root-relative error (m)", 1.0),
            ("scale_normalised_position_error_mean", "Scale-normalised error (m)", 1.0),
            ("end_effector_error_mean", "End-effector error (m)", 1.0),
            ("body_orientation_error_mean", "Body-orientation error (deg)", 1.0),
        ],
        seed=20260722,
    )
    create_multi_panel_figure(
        df,
        FIGURE_DIR / "figure_physical_plausibility.png",
        "Physical-plausibility indicators across nine motions",
        [
            ("total_foot_sliding_distance", "Foot sliding (m)", 1.0),
            ("maximum_ground_penetration", "Max. penetration (cm)", 100.0),
            ("self_collision_frame_ratio", "MuJoCo collision proxy (%)", 100.0),
            ("joint_limit_violation_ratio", "Joint-limit frames (zero tol., %)", 100.0),
        ],
        seed=20260822,
    )
    create_jerk_figure(df, FIGURE_DIR / "figure_temporal_consistency.png")
    create_qualitative_figure(FIGURE_DIR / "figure_same_frame_comparison.png")

    metadata = {
        "source": str(INPUT_CSV),
        "methods": METHODS,
        "motion_count": int(df["motion_name"].nunique()),
        "bootstrap": {"iterations": 20000, "confidence": 0.95, "seed_base": 20260722},
        "qualitative_frames": REPRESENTATIVE_FRAMES,
        "qualitative_camera": {
            "resolution": [1280, 960],
            "camera_distance": 3.2,
            "world_azimuth_degrees": 180.0,
            "camera_elevation_degrees": -12.0,
            "canonical_root_position": [0.0, 0.0, 0.72],
            "fixed_camera_lookat": [0.0, 0.0, 0.87],
            "lookat_z_offset": 0.15,
            "root_pose_normalized": True,
        },
        "figures": [
            "figure_motion_preservation.png",
            "figure_physical_plausibility.png",
            "figure_temporal_consistency.png",
            "figure_same_frame_comparison.png",
        ],
    }
    (FIGURE_DIR / "figure_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(FIGURE_DIR)


if __name__ == "__main__":
    main()
