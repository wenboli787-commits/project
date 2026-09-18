from pathlib import Path

import numpy as np
from PIL import Image


frame_dir = Path(__file__).parent / "135_04_future_green_pose_aligned_frames"

for frame_file in sorted(frame_dir.glob("*.png")):
    rgb = np.asarray(Image.open(frame_file).convert("RGB"), dtype=float)
    yy, _ = np.indices(rgb.shape[:2])
    mask = (
        (rgb[:, :, 1] > rgb[:, :, 0] * 1.10)
        & (rgb[:, :, 1] > rgb[:, :, 2] * 1.05)
        & (yy > 76)
    )
    y, x = np.where(mask)
    print(
        frame_file.name,
        "bbox",
        int(x.min()),
        int(y.min()),
        int(x.max()),
        int(y.max()),
        "centroid",
        round(float(x.mean()), 1),
        round(float(y.mean()), 1),
    )
