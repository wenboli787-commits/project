from __future__ import annotations

import argparse
import sys
from pathlib import Path


TRACKING_ROOT = Path(__file__).resolve().parents[1]
GMR_ROOT = TRACKING_ROOT.parent
for path in (str(TRACKING_ROOT), str(GMR_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

import numpy as np

from gmr_tracking.motion import load_robot_motion_reference
from gmr_tracking.mujoco_pd import MuJoCoPDTracker, PDTrackerConfig, summarize_metrics


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Diagnose whether a GMR pkl is suitable for PD/RL tracking.")
    parser.add_argument("--robot", default="unitree_g1")
    parser.add_argument("--robot_motion_path", required=True)
    parser.add_argument("--max_frames", type=int, default=120)
    parser.add_argument("--kp", type=float, default=80.0)
    parser.add_argument("--kd", type=float, default=4.0)
    parser.add_argument("--control_limit_mode", choices=["auto", "model", "joint", "none"], default="auto")
    parser.add_argument("--max_torque", type=float, default=None)
    parser.add_argument("--steps_per_frame", type=int, default=None)
    return parser


def run_short_pd(robot: str, motion_path: str, args: argparse.Namespace, root_mode: str) -> dict[str, float]:
    motion = load_robot_motion_reference(motion_path, max_frames=args.max_frames)
    tracker = MuJoCoPDTracker(
        robot=robot,
        motion=motion,
        config=PDTrackerConfig(
            kp=args.kp,
            kd=args.kd,
            root_mode=root_mode,
            control_limit_mode=args.control_limit_mode,
            max_torque=args.max_torque,
            steps_per_frame=args.steps_per_frame,
        ),
    )
    tracker.reset(0)
    rows = []
    try:
        for target_idx in range(1, motion.frame_count):
            rows.append(tracker.step_to_reference(target_idx))
    finally:
        tracker.close()
    summary = summarize_metrics(rows)
    summary["frames"] = float(motion.frame_count)
    summary["steps_per_frame"] = float(tracker.steps_per_frame)
    summary["sim_dt"] = float(tracker.model.opt.timestep)
    return summary


def print_summary(name: str, summary: dict[str, float]) -> None:
    print(f"\n[{name}]")
    for key in (
        "frames",
        "steps_per_frame",
        "sim_dt",
        "actuated_dof_rmse_mean",
        "actuated_dof_rmse_max",
        "root_pos_error_mean",
        "root_xy_error_mean",
        "root_height_error_mean",
        "torque_saturation_fraction_mean",
        "target_joint_limit_clip_fraction_mean",
        "ctrl_abs_max_max",
    ):
        if key in summary:
            print(f"  {key}: {summary[key]:.6f}")


def main() -> None:
    args = build_parser().parse_args()
    motion = load_robot_motion_reference(args.robot_motion_path, max_frames=args.max_frames)
    tracker = MuJoCoPDTracker(
        robot=args.robot,
        motion=motion,
        config=PDTrackerConfig(
            kp=args.kp,
            kd=args.kd,
            root_mode="kinematic",
            control_limit_mode=args.control_limit_mode,
            max_torque=args.max_torque,
            steps_per_frame=args.steps_per_frame,
        ),
    )
    try:
        ctrl_ranges = tracker.model.actuator_ctrlrange[tracker.actuator_map.actuator_ids]
        print("[motion/model]")
        print(f"  robot: {args.robot}")
        print(f"  motion_path: {motion.path}")
        print(f"  xml_path: {tracker.xml_path}")
        print(f"  motion_frames: {motion.frame_count}")
        print(f"  motion_fps: {motion.fps}")
        print(f"  model_nq/model_nv/model_nu: {tracker.model.nq}/{tracker.model.nv}/{tracker.model.nu}")
        print(f"  motion_qpos_dim/dof_count: {motion.qpos_dim}/{motion.dof_count}")
        print(f"  actuated_dof_count: {tracker.actuator_map.size}")
        print(f"  original_xml_dt: {tracker.original_timestep:.6f}")
        print(f"  tracking_sim_dt: {tracker.model.opt.timestep:.6f}")
        print(f"  steps_per_frame: {tracker.steps_per_frame}")
        print(f"  control_limit_mode: {args.control_limit_mode}")
        print(f"  ctrl_abs_range_median: {np.median(np.max(np.abs(ctrl_ranges), axis=1)):.6f}")
        print(f"  first_8_actuators: {tracker.actuator_map.actuator_names[:8]}")
        print(f"  first_8_joints: {tracker.actuator_map.joint_names[:8]}")
    finally:
        tracker.close()

    kin = run_short_pd(args.robot, args.robot_motion_path, args, "kinematic")
    free = run_short_pd(args.robot, args.robot_motion_path, args, "free")
    print_summary("kinematic_pd", kin)
    print_summary("free_pd", free)

    print("\n[diagnosis]")
    kin_err = kin.get("actuated_dof_rmse_mean", 999.0)
    kin_sat = kin.get("torque_saturation_fraction_mean", 0.0)
    free_root = free.get("root_pos_error_mean", 999.0)
    free_height = free.get("root_height_error_mean", 999.0)
    if kin_err > 0.5:
        print("  - Kinematic PD joint error is high. Check robot/motion match, kp/kd, actuator limits, and joint order.")
    else:
        print("  - Kinematic PD joint error is in a usable range for a first pass.")
    if kin_sat > 0.5:
        print("  - Torque saturation is high. Try lowering kp, increasing kd slightly, or reviewing max_torque/control_limit_mode.")
    if free_root > 0.3 or free_height > 0.2:
        print("  - Free-root tracking drifts/falls. This means the retargeted motion is not dynamically stable yet; use RL after PD tuning.")
    else:
        print("  - Free-root drift is moderate in this short test.")


if __name__ == "__main__":
    main()
