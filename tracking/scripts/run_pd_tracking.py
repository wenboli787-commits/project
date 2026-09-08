from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


TRACKING_ROOT = Path(__file__).resolve().parents[1]
GMR_ROOT = TRACKING_ROOT.parent
for path in (str(TRACKING_ROOT), str(GMR_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from gmr_tracking.motion import load_robot_motion_reference
from gmr_tracking.mujoco_pd import MuJoCoPDTracker, PDTrackerConfig, summarize_metrics


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run torque PD tracking for a GMR robot motion pkl.")
    parser.add_argument("--robot", default="unitree_g1")
    parser.add_argument("--robot_motion_path", required=True)
    parser.add_argument("--start_frame", type=int, default=0)
    parser.add_argument("--max_frames", type=int, default=None)
    parser.add_argument("--root_mode", choices=["free", "kinematic"], default="free")
    parser.add_argument("--kp", type=float, default=80.0)
    parser.add_argument("--kd", type=float, default=4.0)
    parser.add_argument(
        "--control_limit_mode",
        choices=["auto", "model", "joint", "none"],
        default="auto",
        help="auto uses joint actuator-force ranges when model motor ctrlrange looks like [-1, 1].",
    )
    parser.add_argument("--max_torque", type=float, default=None)
    parser.add_argument("--steps_per_frame", type=int, default=None)
    parser.add_argument(
        "--no_match_motion_dt",
        action="store_true",
        help="Keep the MuJoCo XML timestep instead of adjusting dt so each reference frame is exactly 1/fps.",
    )
    parser.add_argument(
        "--no_clip_target_to_joint_limits",
        action="store_true",
        help="Do not clip PD or RL residual targets to MuJoCo joint ranges.",
    )
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--rate_limit", action="store_true")
    parser.add_argument("--metrics_path", type=Path, default=None)
    parser.add_argument("--summary_path", type=Path, default=None)
    parser.add_argument("--print_every", type=int, default=30)
    return parser


def format_tag(value: float) -> str:
    return f"{value:g}".replace("-", "m").replace(".", "p")


def default_output_paths(motion_path: Path, robot: str, root_mode: str, kp: float, kd: float) -> tuple[Path, Path]:
    out_dir = GMR_ROOT / "outputs" / "pd_tracking"
    stem = f"{motion_path.stem}_{robot}_{root_mode}_kp{format_tag(kp)}_kd{format_tag(kd)}_pd"
    return out_dir / f"{stem}_metrics.csv", out_dir / f"{stem}_summary.json"


def write_metrics_csv(path: Path, rows: list[dict[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary_json(path: Path, summary: dict[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def main() -> None:
    args = build_parser().parse_args()
    motion_path = Path(args.robot_motion_path).expanduser().resolve()
    metrics_path, summary_path = default_output_paths(
        motion_path,
        args.robot,
        args.root_mode,
        args.kp,
        args.kd,
    )
    metrics_path = args.metrics_path or metrics_path
    summary_path = args.summary_path or summary_path

    motion = load_robot_motion_reference(
        motion_path,
        start_frame=args.start_frame,
        max_frames=args.max_frames,
    )
    config = PDTrackerConfig(
        kp=args.kp,
        kd=args.kd,
        root_mode=args.root_mode,
        control_limit_mode=args.control_limit_mode,
        max_torque=args.max_torque,
        steps_per_frame=args.steps_per_frame,
        match_motion_dt=not args.no_match_motion_dt,
        clip_target_to_joint_limits=not args.no_clip_target_to_joint_limits,
        render=args.render,
        rate_limit=args.rate_limit,
    )
    tracker = MuJoCoPDTracker(robot=args.robot, motion=motion, config=config)
    tracker.reset(0)

    print(
        f"[pd_tracking] robot={args.robot}, frames={motion.frame_count}, "
        f"fps={motion.fps}, steps_per_frame={tracker.steps_per_frame}, "
        f"sim_dt={tracker.model.opt.timestep:.6f}, root_mode={args.root_mode}"
    )
    print(f"[pd_tracking] xml={tracker.xml_path}")
    print(f"[pd_tracking] actuators={tracker.actuator_map.size}, dof={motion.dof_count}")

    rows: list[dict[str, float]] = []
    try:
        for target_idx in range(1, motion.frame_count):
            metrics = tracker.step_to_reference(target_idx)
            metrics["frame"] = float(target_idx)
            rows.append(metrics)
            if args.print_every > 0 and target_idx % args.print_every == 0:
                print(
                    "[pd_tracking] "
                    f"frame={target_idx}/{motion.frame_count - 1} "
                    f"dof_rmse={metrics['dof_rmse']:.4f} "
                    f"root_pos={metrics['root_pos_error']:.4f} "
                    f"ctrl_max={metrics['ctrl_abs_max']:.2f}"
                )
    finally:
        tracker.close()

    summary = summarize_metrics(rows)
    summary.update(
        {
            "robot": args.robot,
            "motion_path": str(motion.path),
            "root_mode": args.root_mode,
            "kp": args.kp,
            "kd": args.kd,
            "frames": motion.frame_count,
            "fps": motion.fps,
            "steps_per_frame": tracker.steps_per_frame,
            "sim_dt": float(tracker.model.opt.timestep),
            "original_xml_dt": float(tracker.original_timestep),
            "match_motion_dt": not args.no_match_motion_dt,
            "clip_target_to_joint_limits": not args.no_clip_target_to_joint_limits,
        }
    )
    write_metrics_csv(metrics_path, rows)
    write_summary_json(summary_path, summary)
    print(f"[pd_tracking] metrics saved: {metrics_path}")
    print(f"[pd_tracking] summary saved: {summary_path}")
    print(
        "[pd_tracking] summary: "
        f"dof_rmse_mean={summary.get('dof_rmse_mean', float('nan')):.4f}, "
        f"root_pos_error_mean={summary.get('root_pos_error_mean', float('nan')):.4f}, "
        f"torque_sat_mean={summary.get('torque_saturation_fraction_mean', float('nan')):.4f}"
    )


if __name__ == "__main__":
    main()
