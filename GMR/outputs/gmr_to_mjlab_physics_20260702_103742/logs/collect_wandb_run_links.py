from __future__ import annotations

import csv
from pathlib import Path


RUN_ROOT = Path("/mnt/d/GMR_WORK/GMR/outputs/gmr_to_mjlab_physics_20260702_103742")
MANIFEST_PATH = RUN_ROOT / "manifests" / "mjlab_rltracking_wandb_runs.csv"
LINKS_PATH = RUN_ROOT / "manifests" / "mjlab_wandb_run_links.csv"


def extract_run_url(log_path: Path) -> str:
    run_url = ""
    if not log_path.exists():
        return run_url
    for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "https://wandb.ai/" not in line or "/runs/" not in line:
            continue
        run_url = line[line.find("https://wandb.ai/") :].strip()
    return run_url


def main() -> None:
    rows = []
    with MANIFEST_PATH.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["wandb_run_url"] = extract_run_url(Path(row["stdout_log"]))
            rows.append(row)

    fieldnames = [
        "motion",
        "status",
        "wandb_run_url",
        "registry",
        "local_run_dir",
        "stdout_log",
        "elapsed_sec",
    ]
    with LINKS_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})

    # Also repair the original manifest's wandb_url column for convenience.
    original_fieldnames = list(rows[0].keys()) if rows else []
    for row in rows:
        if row.get("wandb_run_url"):
            row["wandb_url"] = row["wandb_run_url"]
    with MANIFEST_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=original_fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"links={LINKS_PATH}")
    print(f"updated={MANIFEST_PATH}")


if __name__ == "__main__":
    main()
