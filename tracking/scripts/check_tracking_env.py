from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


TRACKING_ROOT = Path(__file__).resolve().parents[1]
GMR_ROOT = TRACKING_ROOT.parent
for path in (str(TRACKING_ROOT), str(GMR_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def main() -> None:
    parser = argparse.ArgumentParser(description="Check the GMR tracking runtime environment.")
    parser.add_argument("--robot", default="unitree_g1")
    parser.add_argument(
        "--motion_path",
        default=str(GMR_ROOT / "outputs" / "dance1_subject2_unitree_g1.pkl"),
    )
    parser.add_argument("--skip_model_load", action="store_true")
    args = parser.parse_args()

    print("[env] python:", sys.executable)
    print("[env] version:", sys.version.replace("\n", " "))
    print("[env] gmr_root:", GMR_ROOT)
    print("[env] tracking_root:", TRACKING_ROOT)

    modules = ["numpy", "mujoco", "gymnasium", "stable_baselines3", "torch"]
    for module in modules:
        print(f"[env] {module}: {'OK' if has_module(module) else 'MISSING'}")

    from gmr_tracking.motion import load_robot_motion_reference
    from gmr_tracking.paths import get_robot_xml_path

    motion_path = Path(args.motion_path)
    print("[env] robot_xml:", get_robot_xml_path(args.robot))
    print("[env] motion_path:", motion_path)
    if motion_path.exists():
        motion = load_robot_motion_reference(motion_path, max_frames=5)
        print(
            "[env] motion:",
            f"frames={motion.frame_count}",
            f"fps={motion.fps}",
            f"dof={motion.dof_count}",
            f"qpos_dim={motion.qpos_dim}",
        )
    else:
        print("[env] motion: MISSING")

    if not args.skip_model_load and has_module("mujoco") and motion_path.exists():
        from gmr_tracking.mujoco_pd import MuJoCoPDTracker, PDTrackerConfig

        motion = load_robot_motion_reference(motion_path, max_frames=5)
        tracker = MuJoCoPDTracker(
            robot=args.robot,
            motion=motion,
            config=PDTrackerConfig(root_mode="kinematic"),
        )
        tracker.reset(0)
        metrics = tracker.step_to_reference(1)
        tracker.close()
        print("[env] pd_smoke_test: OK", f"dof_rmse={metrics['dof_rmse']:.4f}")
    elif args.skip_model_load:
        print("[env] pd_smoke_test: SKIPPED")
    else:
        print("[env] pd_smoke_test: SKIPPED")


if __name__ == "__main__":
    main()
