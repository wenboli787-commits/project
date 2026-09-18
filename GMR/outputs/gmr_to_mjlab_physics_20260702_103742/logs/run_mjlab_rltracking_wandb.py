from __future__ import annotations

import csv
import os
import subprocess
import sys
import time
from pathlib import Path


RUN_ID = "gmr_to_mjlab_physics_20260702_103742"
WORK_ROOT = Path("/mnt/d/GMR_WORK")
MJLAB_ROOT = WORK_ROOT / "mjlab"
RUN_ROOT = WORK_ROOT / "GMR" / "outputs" / RUN_ID
LOG_ROOT = RUN_ROOT / "mjlab" / "rsl_rl_logs"
TRAIN_BIN = MJLAB_ROOT / ".venv" / "bin" / "train"
MANIFEST_PATH = RUN_ROOT / "manifests" / "mjlab_rltracking_wandb_runs.csv"
STDOUT_DIR = RUN_ROOT / "logs" / "mjlab_train_stdout"

REGISTRY_PREFIX = "wenboli787-university-of-glasgow-org/wandb-registry-motions"
MOTIONS = [
    "08_01_gmr",
    "08_04_gmr",
    "08_05_gmr",
    "09_01_gmr",
    "09_12_gmr",
    "10_01_gmr",
    "13_01_gmr",
    "13_11_gmr",
    "13_17_gmr",
]


def newest_run_dir(before: set[Path]) -> str:
    exp_dir = LOG_ROOT / "g1_tracking"
    if not exp_dir.exists():
        return ""
    after = {p for p in exp_dir.iterdir() if p.is_dir()}
    created = sorted(after - before, key=lambda p: p.stat().st_mtime)
    if created:
        return str(created[-1])
    existing = sorted(after, key=lambda p: p.stat().st_mtime)
    return str(existing[-1]) if existing else ""


def read_wandb_url(stdout_path: Path) -> str:
    if not stdout_path.exists():
        return ""
    url = ""
    for line in stdout_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "https://wandb.ai/" in line:
            url = line[line.find("https://wandb.ai/") :].strip()
    return url


def run_motion(motion: str) -> dict[str, str | int | float]:
    registry = f"{REGISTRY_PREFIX}/{motion}:latest"
    run_name = f"{RUN_ID}_{motion}"
    stdout_path = STDOUT_DIR / f"{motion}.log"
    exp_dir = LOG_ROOT / "g1_tracking"
    before = {p for p in exp_dir.iterdir() if p.is_dir()} if exp_dir.exists() else set()

    cmd = [
        str(TRAIN_BIN),
        "Mjlab-Tracking-Flat-Unitree-G1",
        "--registry-name",
        registry,
        "--env.scene.num-envs",
        "128",
        "--agent.max-iterations",
        "20",
        "--agent.save-interval",
        "10",
        "--agent.run-name",
        run_name,
        "--video",
        "True",
        "--video-interval",
        "200",
        "--video-length",
        "120",
        "--log-root",
        str(LOG_ROOT),
    ]

    env = os.environ.copy()
    env["MUJOCO_GL"] = env.get("MUJOCO_GL", "egl")
    env["WANDB_MODE"] = "online"
    env["PYTHONUNBUFFERED"] = "1"

    start = time.time()
    print(f"[mjlab_batch] START {motion}")
    print(f"[mjlab_batch] registry={registry}")
    print(f"[mjlab_batch] stdout={stdout_path}")
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8", errors="ignore") as log:
        proc = subprocess.Popen(
            cmd,
            cwd=str(MJLAB_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            log.write(line)
            log.flush()
            if (
                "View run" in line
                or "Logging experiment" in line
                or "Saving model" in line
                or "Video" in line
                or "[INFO]" in line
            ):
                print(line.rstrip())
        return_code = proc.wait()

    elapsed = time.time() - start
    run_dir = newest_run_dir(before)
    wandb_url = read_wandb_url(stdout_path)
    status = "ok" if return_code == 0 else "failed"
    print(f"[mjlab_batch] DONE {motion} status={status} elapsed_sec={elapsed:.1f}")
    return {
        "motion": motion,
        "registry": registry,
        "status": status,
        "return_code": return_code,
        "elapsed_sec": round(elapsed, 3),
        "local_run_dir": run_dir,
        "stdout_log": str(stdout_path),
        "wandb_url": wandb_url,
    }


def write_manifest(rows: list[dict[str, str | int | float]]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "motion",
        "registry",
        "status",
        "return_code",
        "elapsed_sec",
        "local_run_dir",
        "stdout_log",
        "wandb_url",
    ]
    with MANIFEST_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[mjlab_batch] manifest={MANIFEST_PATH}")


def main() -> int:
    if not TRAIN_BIN.exists():
        print(f"Missing train binary: {TRAIN_BIN}", file=sys.stderr)
        return 2

    rows: list[dict[str, str | int | float]] = []
    for motion in MOTIONS:
        row = run_motion(motion)
        rows.append(row)
        write_manifest(rows)
        if row["status"] != "ok":
            print(f"[mjlab_batch] stopping after failure: {motion}", file=sys.stderr)
            return int(row["return_code"]) or 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
