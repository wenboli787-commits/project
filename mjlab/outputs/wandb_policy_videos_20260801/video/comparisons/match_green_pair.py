from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import numpy as np


WIDTH, HEIGHT = 240, 135


def to_wsl(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/")
    return "/mnt/" + value[0].lower() + value[2:]


def read_frames(path: Path) -> np.ndarray:
    result = subprocess.run(
        [
            "wsl",
            "ffmpeg",
            "-loglevel",
            "error",
            "-i",
            to_wsl(path),
            "-vf",
            f"scale={WIDTH}:{HEIGHT}",
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "-",
        ],
        check=True,
        stdout=subprocess.PIPE,
    )
    pixels_per_frame = WIDTH * HEIGHT * 3
    raw = np.frombuffer(result.stdout, dtype=np.uint8)
    count = raw.size // pixels_per_frame
    return raw[: count * pixels_per_frame].reshape(count, HEIGHT, WIDTH, 3)


def green_maps(frames: np.ndarray) -> np.ndarray:
    rgb = frames.astype(np.float32)
    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    maps = np.clip((green - np.maximum(red, blue) - 2.0) / 34.0, 0.0, 1.0)
    maps *= green > 48.0
    maps[:, :8] = 0.0
    maps[:, :, :35] = 0.0
    maps[:, :, 205:] = 0.0
    padded = np.pad(maps, ((0, 0), (2, 2), (2, 2)), mode="constant")
    blurred = np.zeros_like(maps)
    for dy in range(5):
        for dx in range(5):
            blurred += padded[:, dy : dy + HEIGHT, dx : dx + WIDTH]
    return blurred / 25.0


def scores_for(target: np.ndarray, candidates: np.ndarray) -> np.ndarray:
    target_norm = np.sqrt(np.sum(target * target)) + 1e-8
    scores = np.full(candidates.shape[0], -1.0, dtype=np.float32)
    for shift_y in range(-3, 4):
        for shift_x in range(-5, 6):
            shifted = np.roll(candidates, (shift_y, shift_x), axis=(1, 2))
            if shift_y > 0:
                shifted[:, :shift_y] = 0
            elif shift_y < 0:
                shifted[:, shift_y:] = 0
            if shift_x > 0:
                shifted[:, :, :shift_x] = 0
            elif shift_x < 0:
                shifted[:, :, shift_x:] = 0
            dot = np.sum(shifted * target, axis=(1, 2))
            norm = np.sqrt(np.sum(shifted * shifted, axis=(1, 2))) * target_norm + 1e-8
            scores = np.maximum(scores, dot / norm)
    return scores


parser = argparse.ArgumentParser()
parser.add_argument("anchor_video", type=Path)
parser.add_argument("anchor_frame", type=int)
parser.add_argument("candidate_video", type=Path)
args = parser.parse_args()

anchor = read_frames(args.anchor_video)
candidates = read_frames(args.candidate_video)
target = green_maps(anchor[[args.anchor_frame]])[0]
scores = scores_for(target, green_maps(candidates))
ordered = np.argsort(scores)[::-1]
selected: list[int] = []
for frame in ordered:
    frame = int(frame)
    if all(abs(frame - prior) >= 7 for prior in selected):
        selected.append(frame)
    if len(selected) == 12:
        break
print(",".join(f"{frame}:{scores[frame]:.4f}" for frame in selected))
