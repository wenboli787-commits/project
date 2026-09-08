from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np


TRACKING_ROOT = Path(__file__).resolve().parents[1]
GMR_ROOT = TRACKING_ROOT.parent
for path in (str(TRACKING_ROOT), str(GMR_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from gmr_tracking.mujoco_pd import summarize_metrics


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate a trained RL tracking policy or zero-action baseline.")
    parser.add_argument("--robot", default="unitree_g1")
    parser.add_argument("--robot_motion_path", required=True)
    parser.add_argument("--policy_path", type=Path, default=None)
    parser.add_argument("--root_mode", choices=["free", "kinematic"], default="free")
    parser.add_argument("--kp", type=float, default=80.0)
    parser.add_argument("--kd", type=float, default=4.0)
    parser.add_argument("--control_limit_mode", choices=["auto", "model", "joint", "none"], default="auto")
    parser.add_argument("--max_torque", type=float, default=None)
    parser.add_argument("--steps_per_frame", type=int, default=None)
    parser.add_argument("--no_match_motion_dt", action="store_true")
    parser.add_argument("--no_clip_target_to_joint_limits", action="store_true")
    parser.add_argument("--action_scale", type=float, default=0.25)
    parser.add_argument("--max_episode_steps", type=int, default=None)
    parser.add_argument("--start_frame", type=int, default=0)
    parser.add_argument("--max_frames", type=int, default=None)
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--metrics_path", type=Path, default=None)
    parser.add_argument("--summary_path", type=Path, default=None)
    return parser


def format_tag(value: float) -> str:
    return f"{value:g}".replace("-", "m").replace(".", "p")


def default_output_paths(
    motion_path: Path,
    robot: str,
    policy_path: Path | None,
    root_mode: str,
    kp: float,
    kd: float,
    action_scale: float,
) -> tuple[Path, Path]:
    out_dir = GMR_ROOT / "outputs" / "rl_tracking"
    policy_tag = "zero_action" if policy_path is None else policy_path.stem
    stem = (
        f"{motion_path.stem}_{robot}_{root_mode}_"
        f"kp{format_tag(kp)}_kd{format_tag(kd)}_as{format_tag(action_scale)}_"
        f"{policy_tag}_eval"
    )
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


def main() -> None:
    args = build_parser().parse_args()
    try:
        from gmr_tracking.rl_env import GMRMotionTrackingEnv
    except ImportError as exc:
        raise SystemExit(str(exc)) from exc

    motion_path = Path(args.robot_motion_path).expanduser().resolve()
    metrics_path, summary_path = default_output_paths(
        motion_path,
        args.robot,
        args.policy_path,
        args.root_mode,
        args.kp,
        args.kd,
        args.action_scale,
    )
    metrics_path = args.metrics_path or metrics_path
    summary_path = args.summary_path or summary_path

    model = None
    if args.policy_path is not None:
        try:
            from stable_baselines3 import PPO
        except ImportError as exc:
            raise SystemExit(
                "stable-baselines3 is required when --policy_path is used. "
                "Install with `WITH_RL=1 bash tracking/scripts/setup_tracking_ubuntu22_04.sh` "
                "or `pip install -r tracking/requirements-rl.txt` first."
            ) from exc
        model = PPO.load(args.policy_path)

    env = GMRMotionTrackingEnv(
        robot=args.robot,
        robot_motion_path=motion_path,
        root_mode=args.root_mode,
        kp=args.kp,
        kd=args.kd,
        control_limit_mode=args.control_limit_mode,
        max_torque=args.max_torque,
        steps_per_frame=args.steps_per_frame,
        match_motion_dt=not args.no_match_motion_dt,
        clip_target_to_joint_limits=not args.no_clip_target_to_joint_limits,
        action_scale=args.action_scale,
        max_episode_steps=args.max_episode_steps,
        random_start=False,
        start_frame=args.start_frame,
        max_frames=args.max_frames,
        render_mode="human" if args.render else None,
    )

    obs, _ = env.reset()
    rows: list[dict[str, float]] = []
    terminated = False
    truncated = False
    while not (terminated or truncated):
        if model is None:
            action = np.zeros(env.action_space.shape, dtype=np.float32)
        else:
            action, _ = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(action)
        row = {key: float(value) for key, value in info.items() if isinstance(value, (int, float))}
        row["reward"] = float(reward)
        rows.append(row)

    env.close()
    summary = summarize_metrics(rows)
    summary.update(
        {
            "robot": args.robot,
            "motion_path": str(motion_path),
            "policy_path": str(args.policy_path) if args.policy_path else "zero_action",
            "root_mode": args.root_mode,
            "kp": args.kp,
            "kd": args.kd,
            "action_scale": args.action_scale,
            "steps": len(rows),
            "reward_mean": float(np.mean([row["reward"] for row in rows])) if rows else 0.0,
            "reward_sum": float(np.sum([row["reward"] for row in rows])) if rows else 0.0,
        }
    )
    write_metrics_csv(metrics_path, rows)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[rl_tracking] metrics saved: {metrics_path}")
    print(f"[rl_tracking] summary saved: {summary_path}")
    print(
        "[rl_tracking] summary: "
        f"steps={len(rows)}, reward_mean={summary['reward_mean']:.4f}, "
        f"dof_rmse_mean={summary.get('dof_rmse_mean', float('nan')):.4f}"
    )


if __name__ == "__main__":
    main()
