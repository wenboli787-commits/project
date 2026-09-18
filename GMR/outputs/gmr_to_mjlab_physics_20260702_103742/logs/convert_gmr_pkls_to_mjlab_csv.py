from pathlib import Path
import csv
import sys


GMR_ROOT = Path("/mnt/d/GMR_WORK/GMR")
RUN_ROOT = GMR_ROOT / "outputs" / "gmr_to_mjlab_physics_20260702_103742"
PKL_DIR = RUN_ROOT / "gmr" / "pkl"
CSV_DIR = RUN_ROOT / "mjlab" / "csv"
MANIFEST_PATH = RUN_ROOT / "manifests" / "mjlab_csv_manifest.csv"

sys.path.insert(0, str(GMR_ROOT / "scripts" / "mjlab_tools"))
from pkl_to_mjlab_csv import convert  # noqa: E402


def main() -> None:
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for pkl_path in sorted(PKL_DIR.glob("*_poses_unitree_g1_gmr.pkl")):
        csv_name = pkl_path.name.replace("_poses_unitree_g1_gmr.pkl", "_gmr.csv")
        csv_path = CSV_DIR / csv_name
        convert(pkl_path, csv_path)
        rows.append(
            {
                "motion_name": csv_name.replace("_gmr.csv", ""),
                "source_pkl": str(pkl_path),
                "output_csv": str(csv_path),
                "status": "ok" if csv_path.exists() and csv_path.stat().st_size > 0 else "missing",
            }
        )

    with MANIFEST_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["motion_name", "source_pkl", "output_csv", "status"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"converted={len(rows)}")
    print(f"manifest={MANIFEST_PATH}")


if __name__ == "__main__":
    main()
