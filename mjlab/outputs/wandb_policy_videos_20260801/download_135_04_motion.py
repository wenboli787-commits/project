from __future__ import annotations

from pathlib import Path

import wandb


destination = Path(
    "/mnt/d/GMR_WORK/mjlab/outputs/wandb_policy_videos_20260801/cache/motions/135_04_gmr_v0"
)
destination.mkdir(parents=True, exist_ok=True)
artifact = wandb.Api(timeout=120).artifact(
    "wenboli787-university-of-glasgow/csv_to_npz/135_04_gmr:v0"
)
path = Path(artifact.download(root=str(destination))) / "motion.npz"
if not path.exists():
    raise FileNotFoundError(path)
print(path)
