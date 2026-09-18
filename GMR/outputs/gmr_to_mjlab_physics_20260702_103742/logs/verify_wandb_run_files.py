from __future__ import annotations

import csv
from pathlib import Path

import wandb


RUN_ROOT = Path("/mnt/d/GMR_WORK/GMR/outputs/gmr_to_mjlab_physics_20260702_103742")
LINKS_PATH = RUN_ROOT / "manifests" / "mjlab_wandb_run_links.csv"
CHECK_PATH = RUN_ROOT / "manifests" / "wandb_run_file_check.csv"


def run_path_from_url(url: str) -> str:
    marker = "https://wandb.ai/"
    if marker not in url:
        return ""
    return url.split(marker, 1)[1].replace("/runs/", "/")


def main() -> None:
    api = wandb.Api()
    rows = []
    with LINKS_PATH.open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            run_path = run_path_from_url(row["wandb_run_url"])
            files = list(api.run(run_path).files())
            names = [file.name for file in files]
            rows.append(
                {
                    "motion": row["motion"],
                    "run_path": run_path,
                    "file_count": len(names),
                    "has_model_19": any(name.endswith("model_19.pt") for name in names),
                    "has_onnx": any(name.endswith(".onnx") for name in names),
                    "media_file_count": sum(1 for name in names if name.startswith("media/")),
                    "wandb_run_url": row["wandb_run_url"],
                }
            )

    with CHECK_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "motion",
                "run_path",
                "file_count",
                "has_model_19",
                "has_onnx",
                "media_file_count",
                "wandb_run_url",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    for row in rows:
        print(
            row["motion"],
            row["file_count"],
            row["has_model_19"],
            row["has_onnx"],
            row["media_file_count"],
        )
    print(f"check={CHECK_PATH}")


if __name__ == "__main__":
    main()
