"""Run the full evaluator using the files made by create_dummy_data.py."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def main() -> None:
    here = Path(__file__).resolve().parent
    evaluate_dir = here.parent
    subprocess.run([sys.executable, str(here / "create_dummy_data.py")], check=True)
    data = here / "dummy_data"
    output = here / "dummy_evaluation_output"
    command = [
        sys.executable, str(evaluate_dir / "evaluate_retargeting.py"),
        "--simulator", "offline",
        "--ref_motion", str(data / "dummy_reference_motion.npz"),
        "--direct_motion", str(data / "dummy_direct_mapping_result.npz"),
        "--ik_motion", str(data / "dummy_basic_ik_result.npz"),
        "--gmr_motion", str(data / "dummy_gmr_result.npz"),
        "--mapping", str(evaluate_dir / "config" / "eval_mapping_template.yaml"),
        "--out_dir", str(output),
    ]
    subprocess.run(command, check=True)
    print(f"Open the report: {output / 'evaluation_report.md'}")


if __name__ == "__main__":
    main()
