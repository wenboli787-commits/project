from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np


ROOT = Path(r"D:\GMR_WORK\mjlab\outputs\wandb_policy_videos_20260801\video")
VIDEO_ROOT = ROOT / "ablation"
RUN_IDS = ["09yrh4qp", "y84gf3sj", "6rlspqk0", "p6vbd18i", "6gq87ju7", "q2l4sxxn"]
ANCHOR_RUN = "09yrh4qp"
ANCHOR_FRAME = 150
WIDTH, HEIGHT = 240, 135


def to_wsl(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/")
    return "/mnt/" + value[0].lower() + value[2:]


def video_for(run_id: str) -> Path:
    matches = list(VIDEO_ROOT.glob(f"*{run_id}.mp4"))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one video for {run_id}, found {matches}")
    return matches[0]


def read_frames(path: Path) -> np.ndarray:
    command = [
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
    ]
    result = subprocess.run(command, check=True, stdout=subprocess.PIPE)
    pixels_per_frame = WIDTH * HEIGHT * 3
    raw = np.frombuffer(result.stdout, dtype=np.uint8)
    frame_count = raw.size // pixels_per_frame
    return raw[: frame_count * pixels_per_frame].reshape(frame_count, HEIGHT, WIDTH, 3)


def green_maps(frames: np.ndarray) -> np.ndarray:
    rgb = frames.astype(np.float32)
    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    excess = green - np.maximum(red, blue)
    maps = np.clip((excess - 2.0) / 34.0, 0.0, 1.0)
    maps *= (green > 48.0)
    maps[:, :8] = 0.0
    maps[:, :, :35] = 0.0
    maps[:, :, 205:] = 0.0
    # A small box blur makes the comparison robust to antialiasing and partial
    # occlusion by the white policy robot.
    padded = np.pad(maps, ((0, 0), (2, 2), (2, 2)), mode="constant")
    blurred = np.zeros_like(maps)
    for dy in range(5):
        for dx in range(5):
            blurred += padded[:, dy : dy + HEIGHT, dx : dx + WIDTH]
    return blurred / 25.0


def best_scores(target: np.ndarray, candidates: np.ndarray) -> np.ndarray:
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


anchor_frames = read_frames(video_for(ANCHOR_RUN))
target = green_maps(anchor_frames[[ANCHOR_FRAME]])[0]

print(f"anchor,{ANCHOR_RUN},{ANCHOR_FRAME}")
for run_id in RUN_IDS:
    frames = anchor_frames if run_id == ANCHOR_RUN else read_frames(video_for(run_id))
    maps = green_maps(frames)
    scores = best_scores(target, maps)
    # Keep candidates separated so the shortlist covers distinct moments.
    ordered = np.argsort(scores)[::-1]
    selected: list[int] = []
    for frame in ordered:
        frame = int(frame)
        if all(abs(frame - prior) >= 8 for prior in selected):
            selected.append(frame)
        if len(selected) == 8:
            break
    print(run_id + "," + ",".join(f"{frame}:{scores[frame]:.4f}" for frame in selected))
