#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import math
from pathlib import Path
from typing import Dict, List

from PIL import Image, ImageDraw, ImageFont


METHODS = ["Direct Mapping", "Basic IK", "GMR"]
COLORS = {
    "Direct Mapping": "#E4572E",
    "Basic IK": "#4C78A8",
    "GMR": "#54A24B",
}


def main() -> None:
    args = build_parser().parse_args()
    input_csv = Path(args.input_csv)
    output_png = Path(args.output_png)
    output_svg = Path(args.output_svg)
    data = load_global_errors(input_csv)
    output_png.parent.mkdir(parents=True, exist_ok=True)
    output_svg.parent.mkdir(parents=True, exist_ok=True)
    draw_png(data, output_png)
    draw_svg(data, output_svg)
    print(f"PNG: {output_png}")
    print(f"SVG: {output_svg}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plot per-motion global body position errors for retargeting methods.")
    parser.add_argument(
        "--input_csv",
        default=r"D:\GMR_WORK\GMR\outputs\pkl_method_evaluation\per_motion_pkl_metrics.csv",
    )
    parser.add_argument(
        "--output_png",
        default=r"D:\GMR_WORK\GMR\outputs\pkl_method_evaluation\global_body_error_by_motion.png",
    )
    parser.add_argument(
        "--output_svg",
        default=r"D:\GMR_WORK\GMR\outputs\pkl_method_evaluation\global_body_error_by_motion.svg",
    )
    return parser


def load_global_errors(path: Path) -> Dict[str, Dict[str, float]]:
    data: Dict[str, Dict[str, float]] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            motion = row.get("motion", "")
            method = row.get("method", "")
            if method not in METHODS or not motion:
                continue
            try:
                value = float(row.get("global_body_position_error_to_reference_mm", "nan"))
            except ValueError:
                value = math.nan
            data.setdefault(motion, {})[method] = value
    return {motion: data[motion] for motion in sorted(data)}


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\calibrib.ttf" if bold else r"C:\Windows\Fonts\calibri.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default()


def nice_ticks(max_value: float, count: int = 6) -> List[float]:
    if not math.isfinite(max_value) or max_value <= 0:
        return [0.0, 1.0]
    raw_step = max_value / max(count - 1, 1)
    magnitude = 10 ** math.floor(math.log10(raw_step))
    residual = raw_step / magnitude
    if residual <= 1:
        step = magnitude
    elif residual <= 2:
        step = 2 * magnitude
    elif residual <= 5:
        step = 5 * magnitude
    else:
        step = 10 * magnitude
    top = math.ceil(max_value / step) * step
    ticks = []
    current = 0.0
    while current <= top + step * 0.5:
        ticks.append(current)
        current += step
    return ticks


def draw_png(data: Dict[str, Dict[str, float]], path: Path) -> None:
    width, height = 1600, 900
    margin_left, margin_right = 110, 55
    margin_top, margin_bottom = 105, 145
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    title_font = load_font(34, bold=True)
    axis_font = load_font(22)
    small_font = load_font(18)
    label_font = load_font(16)

    motions = list(data)
    values = [value for row in data.values() for value in row.values() if math.isfinite(value)]
    y_ticks = nice_ticks(max(values) if values else 1.0)
    y_max = y_ticks[-1]

    draw.text((margin_left, 35), "Global Body Position Error by Motion", fill="#222222", font=title_font)
    draw.text((margin_left, 74), "Reference method: GMR  |  unit: mm", fill="#555555", font=axis_font)

    for tick in y_ticks:
        y = margin_top + plot_h - (tick / y_max) * plot_h
        draw.line((margin_left, y, width - margin_right, y), fill="#E5E7EB", width=1)
        draw.text((margin_left - 95, y - 11), f"{tick:.0f}", fill="#555555", font=small_font)
    draw.line((margin_left, margin_top, margin_left, margin_top + plot_h), fill="#333333", width=2)
    draw.line((margin_left, margin_top + plot_h, width - margin_right, margin_top + plot_h), fill="#333333", width=2)

    group_w = plot_w / max(len(motions), 1)
    bar_w = min(38, group_w * 0.22)
    offsets = [-bar_w * 1.15, 0.0, bar_w * 1.15]
    for idx, motion in enumerate(motions):
        center = margin_left + group_w * (idx + 0.5)
        for method, offset in zip(METHODS, offsets):
            value = data[motion].get(method, math.nan)
            if not math.isfinite(value):
                continue
            bar_h = 0.0 if y_max == 0 else (value / y_max) * plot_h
            x0 = center + offset - bar_w / 2
            x1 = center + offset + bar_w / 2
            y0 = margin_top + plot_h - bar_h
            y1 = margin_top + plot_h
            draw.rounded_rectangle((x0, y0, x1, y1), radius=4, fill=COLORS[method])
            if value > 0:
                label = f"{value:.0f}"
                bbox = draw.textbbox((0, 0), label, font=label_font)
                draw.text((x0 + (bar_w - (bbox[2] - bbox[0])) / 2, max(margin_top + 4, y0 - 22)), label, fill="#222222", font=label_font)
        bbox = draw.textbbox((0, 0), motion, font=axis_font)
        draw.text((center - (bbox[2] - bbox[0]) / 2, margin_top + plot_h + 18), motion, fill="#333333", font=axis_font)

    draw.text((margin_left, height - 52), "Motion ID", fill="#333333", font=axis_font)
    draw.text((margin_left - 2, margin_top - 34), "Error (mm)", fill="#333333", font=axis_font)

    legend_x = width - margin_right - 520
    legend_y = 43
    for idx, method in enumerate(METHODS):
        x = legend_x + idx * 175
        draw.rounded_rectangle((x, legend_y + 4, x + 28, legend_y + 24), radius=4, fill=COLORS[method])
        draw.text((x + 38, legend_y), method, fill="#333333", font=small_font)

    image.save(path)


def draw_svg(data: Dict[str, Dict[str, float]], path: Path) -> None:
    width, height = 1600, 900
    margin_left, margin_right = 110, 55
    margin_top, margin_bottom = 105, 145
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    motions = list(data)
    values = [value for row in data.values() for value in row.values() if math.isfinite(value)]
    y_ticks = nice_ticks(max(values) if values else 1.0)
    y_max = y_ticks[-1]
    group_w = plot_w / max(len(motions), 1)
    bar_w = min(38, group_w * 0.22)
    offsets = [-bar_w * 1.15, 0.0, bar_w * 1.15]

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="110" y="60" font-family="Arial, sans-serif" font-size="34" font-weight="700" fill="#222">Global Body Position Error by Motion</text>',
        '<text x="110" y="92" font-family="Arial, sans-serif" font-size="22" fill="#555">Reference method: GMR | unit: mm</text>',
    ]
    for tick in y_ticks:
        y = margin_top + plot_h - (tick / y_max) * plot_h
        lines.append(f'<line x1="{margin_left}" y1="{y:.2f}" x2="{width - margin_right}" y2="{y:.2f}" stroke="#E5E7EB"/>')
        lines.append(f'<text x="{margin_left - 16}" y="{y + 7:.2f}" text-anchor="end" font-family="Arial, sans-serif" font-size="18" fill="#555">{tick:.0f}</text>')
    lines.append(f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_h}" stroke="#333" stroke-width="2"/>')
    lines.append(f'<line x1="{margin_left}" y1="{margin_top + plot_h}" x2="{width - margin_right}" y2="{margin_top + plot_h}" stroke="#333" stroke-width="2"/>')

    legend_x, legend_y = width - margin_right - 520, 43
    for idx, method in enumerate(METHODS):
        x = legend_x + idx * 175
        lines.append(f'<rect x="{x}" y="{legend_y + 4}" width="28" height="20" rx="4" fill="{COLORS[method]}"/>')
        lines.append(f'<text x="{x + 38}" y="{legend_y + 21}" font-family="Arial, sans-serif" font-size="18" fill="#333">{html.escape(method)}</text>')

    for idx, motion in enumerate(motions):
        center = margin_left + group_w * (idx + 0.5)
        for method, offset in zip(METHODS, offsets):
            value = data[motion].get(method, math.nan)
            if not math.isfinite(value):
                continue
            bar_h = 0.0 if y_max == 0 else (value / y_max) * plot_h
            x = center + offset - bar_w / 2
            y = margin_top + plot_h - bar_h
            lines.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_w:.2f}" height="{bar_h:.2f}" rx="4" fill="{COLORS[method]}"/>')
            if value > 0:
                lines.append(f'<text x="{x + bar_w / 2:.2f}" y="{max(margin_top + 18, y - 6):.2f}" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" fill="#222">{value:.0f}</text>')
        lines.append(f'<text x="{center:.2f}" y="{margin_top + plot_h + 42}" text-anchor="middle" font-family="Arial, sans-serif" font-size="22" fill="#333">{html.escape(motion)}</text>')

    lines.append(f'<text x="{margin_left}" y="{height - 52}" font-family="Arial, sans-serif" font-size="22" fill="#333">Motion ID</text>')
    lines.append(f'<text x="{margin_left - 2}" y="{margin_top - 34}" font-family="Arial, sans-serif" font-size="22" fill="#333">Error (mm)</text>')
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
