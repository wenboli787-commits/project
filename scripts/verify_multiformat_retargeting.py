import argparse
import importlib.util
import pickle
import subprocess
import sys
from pathlib import Path

import numpy as np


GMR_ROOT = Path(__file__).resolve().parents[1]


def build_parser():
    parser = argparse.ArgumentParser(
        description="Verify GMR/Direct/BasicIK retargeting for BVH, SMPL-X, AMASS, and Human3D inputs."
    )
    parser.add_argument("--robot", default="unitree_g1")
    parser.add_argument("--max_frames", type=int, default=5)
    parser.add_argument("--verify_root", type=Path, default=GMR_ROOT / "outputs" / "multiformat_verify")
    parser.add_argument("--sample_root", type=Path, default=GMR_ROOT / "data" / "multiformat_verify")
    parser.add_argument(
        "--skip_dependency_check",
        action="store_true",
        help="Skip import checks and try running the commands directly.",
    )
    return parser


def check_dependencies():
    required = ["numpy", "scipy", "mujoco", "mink", "smplx", "qpsolvers", "daqp"]
    missing = []
    print("[verify] Python dependency check:")
    for name in required:
        ok = importlib.util.find_spec(name) is not None
        print(f"  {name:10s}: {'OK' if ok else 'MISSING'}")
        if not ok:
            missing.append(name)
    if missing:
        raise RuntimeError(
            "Missing dependencies: "
            + ", ".join(missing)
            + ". Run: bash scripts/setup_multiformat_retargeting_ubuntu22_04.sh gmr"
        )


def create_samples(sample_root: Path):
    sample_root.mkdir(parents=True, exist_ok=True)
    frames = 12

    poses = np.zeros((frames, 72), dtype=np.float32)
    trans = np.zeros((frames, 3), dtype=np.float32)
    trans[:, 0] = np.linspace(0.0, 0.15, frames)
    betas = np.zeros(16, dtype=np.float32)
    amass_path = sample_root / "synthetic_amass_verify.npz"
    np.savez(
        amass_path,
        poses=poses,
        trans=trans,
        betas=betas,
        gender=np.array("neutral"),
        mocap_framerate=np.array(30),
    )

    base = np.array(
        [
            [0, 0, 950],
            [-90, -10, 900],
            [-95, -10, 500],
            [-100, -10, 60],
            [90, 10, 900],
            [95, 10, 500],
            [100, 10, 60],
            [0, 0, 1150],
            [0, 0, 1400],
            [0, 0, 1520],
            [0, 0, 1700],
            [190, 20, 1400],
            [360, 40, 1220],
            [500, 50, 1050],
            [-190, -20, 1400],
            [-360, -40, 1220],
            [-500, -50, 1050],
        ],
        dtype=np.float32,
    )
    human3d = np.repeat(base[None, :, :], frames, axis=0)
    human3d[:, :, 0] += np.linspace(0.0, 120.0, frames, dtype=np.float32)[:, None]
    human3d[:, 13, 2] += 60.0 * np.sin(np.linspace(0.0, np.pi, frames))
    human3d[:, 16, 2] += 60.0 * np.sin(np.linspace(0.0, np.pi, frames))

    h36m_npy_path = sample_root / "synthetic_h36m17_verify.npy"
    h36m_npz_path = sample_root / "synthetic_h36m17_verify.npz"
    np.save(h36m_npy_path, human3d)
    np.savez(h36m_npz_path, keypoints3d=human3d, fps=np.array(30))

    return amass_path, h36m_npy_path, h36m_npz_path


def tail_text(path: Path, lines: int = 60):
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(text[-lines:])


def run_command(command, log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        log.write("[command] " + " ".join(map(str, command)) + "\n\n")
        log.flush()
        result = subprocess.run(
            list(map(str, command)),
            cwd=GMR_ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
    if result.returncode != 0:
        print(f"[verify] FAILED log: {log_path}")
        print(tail_text(log_path))
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {' '.join(map(str, command))}")


def verify_output(save_path: Path):
    if not save_path.exists():
        raise RuntimeError(f"Missing output pkl: {save_path}")
    with save_path.open("rb") as f:
        data = pickle.load(f)
    frames = len(data["root_pos"])
    if frames <= 0:
        raise RuntimeError(f"Empty robot motion: {save_path}")
    return frames, data["fps"]


def run_case(method, script, case_name, motion_file, motion_format, args, extra_args):
    save_path = args.verify_root / f"{case_name}_{args.robot}_{method}.pkl"
    log_path = args.verify_root / "logs" / f"{case_name}_{method}.log"
    command = [
        sys.executable,
        script,
        "--motion_file",
        motion_file,
        "--motion_format",
        motion_format,
        "--robot",
        args.robot,
        "--max_frames",
        str(args.max_frames),
        "--no_visualize",
        "--save_path",
        save_path,
        *extra_args,
    ]
    print(f"[verify] RUN method={method:14s} case={case_name:13s} format={motion_format}")
    run_command(command, log_path)
    frames, fps = verify_output(save_path)
    print(f"[verify] OK  {save_path} frames={frames} fps={fps}")


def run_all_methods(case_name, motion_file, motion_format, args, extra_args=None):
    extra_args = extra_args or []
    methods = [
        ("gmr", "scripts/motion_to_robot.py"),
        ("direct_mapping", "direct mapping/run_direct_mapping.py"),
        ("basic_ik", "Basic IK retargeting/run_basic_ik_retargeting.py"),
    ]
    for method, script in methods:
        run_case(method, script, case_name, motion_file, motion_format, args, extra_args)


def main():
    args = build_parser().parse_args()
    args.verify_root = args.verify_root.expanduser().resolve()
    args.sample_root = args.sample_root.expanduser().resolve()
    args.verify_root.mkdir(parents=True, exist_ok=True)

    print(f"[verify] GMR_ROOT   : {GMR_ROOT}")
    print(f"[verify] ROBOT      : {args.robot}")
    print(f"[verify] MAX_FRAMES : {args.max_frames}")
    print(f"[verify] VERIFY_ROOT: {args.verify_root}")

    if not args.skip_dependency_check:
        check_dependencies()

    amass_path, h36m_npy_path, h36m_npz_path = create_samples(args.sample_root)
    bvh_path = GMR_ROOT / "data" / "lafan1_sample" / "push1_subject2.bvh"
    smplx_path = GMR_ROOT / "data" / "smplx_sample" / "synthetic_smplx_wave_stageii.npz"
    for path in (bvh_path, smplx_path, amass_path, h36m_npy_path, h36m_npz_path):
        if not path.exists():
            raise FileNotFoundError(path)

    run_all_methods("bvh_lafan1", bvh_path, "bvh_lafan1", args)
    run_all_methods("smplx_npz", smplx_path, "smplx_npz", args)
    run_all_methods("amass_npz", amass_path, "amass_npz", args)
    human3d_args = [
        "--joint_skeleton",
        "h36m_17",
        "--position_unit",
        "mm",
        "--axis_order",
        "xyz",
        "--actual_human_height",
        "1.75",
    ]
    run_all_methods("human3d_npy", h36m_npy_path, "joint_positions_npy", args, human3d_args)
    run_all_methods(
        "human3d_npz",
        h36m_npz_path,
        "joint_positions_npz",
        args,
        ["--joint_array_key", "keypoints3d", *human3d_args],
    )

    print("[verify] All multiformat retargeting checks completed successfully.")
    print(f"[verify] Outputs: {args.verify_root}")
    print(f"[verify] Logs   : {args.verify_root / 'logs'}")


if __name__ == "__main__":
    main()
