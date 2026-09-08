from __future__ import annotations

import argparse
import sys
from pathlib import Path


TRACKING_ROOT = Path(__file__).resolve().parents[1]
GMR_ROOT = TRACKING_ROOT.parent
for path in (str(TRACKING_ROOT), str(GMR_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train a PPO residual policy for GMR motion tracking.")
    parser.add_argument("--robot", default="unitree_g1")
    parser.add_argument("--robot_motion_path", required=True)
    parser.add_argument("--root_mode", choices=["free", "kinematic"], default="free")
    parser.add_argument("--kp", type=float, default=80.0)
    parser.add_argument("--kd", type=float, default=4.0)
    parser.add_argument("--control_limit_mode", choices=["auto", "model", "joint", "none"], default="auto")
    parser.add_argument("--max_torque", type=float, default=None)
    parser.add_argument("--steps_per_frame", type=int, default=None)
    parser.add_argument("--no_match_motion_dt", action="store_true")
    parser.add_argument("--no_clip_target_to_joint_limits", action="store_true")
    parser.add_argument("--action_scale", type=float, default=0.25)
    parser.add_argument("--total_timesteps", type=int, default=200_000)
    parser.add_argument("--n_envs", type=int, default=1)
    parser.add_argument("--max_episode_steps", type=int, default=None)
    parser.add_argument("--start_frame", type=int, default=0)
    parser.add_argument("--max_frames", type=int, default=None)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--learning_rate", type=float, default=3e-4)
    parser.add_argument("--n_steps", type=int, default=1024)
    parser.add_argument("--batch_size", type=int, default=256)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--save_path", type=Path, default=None)
    parser.add_argument("--tensorboard_log", type=Path, default=None)
    return parser


def format_tag(value: float) -> str:
    return f"{value:g}".replace("-", "m").replace(".", "p")


def main() -> None:
    args = build_parser().parse_args()
    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.monitor import Monitor
        from stable_baselines3.common.vec_env import DummyVecEnv
    except ImportError as exc:
        raise SystemExit(
            "stable-baselines3 is not installed. Install RL dependencies with "
            "`WITH_RL=1 bash tracking/scripts/setup_tracking_ubuntu22_04.sh` or "
            "`pip install -r tracking/requirements-rl.txt` first."
        ) from exc

    from gmr_tracking.rl_env import GMRMotionTrackingEnv

    motion_path = Path(args.robot_motion_path).expanduser().resolve()
    save_path = args.save_path
    if save_path is None:
        out_dir = GMR_ROOT / "outputs" / "rl_tracking"
        stem = (
            f"{motion_path.stem}_{args.robot}_{args.root_mode}_"
            f"kp{format_tag(args.kp)}_kd{format_tag(args.kd)}_as{format_tag(args.action_scale)}_"
            f"ppo_{args.total_timesteps}"
        )
        save_path = out_dir / f"{stem}.zip"
    save_path.parent.mkdir(parents=True, exist_ok=True)

    def make_env(rank: int):
        def _init():
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
                random_start=True,
                start_frame=args.start_frame,
                max_frames=args.max_frames,
            )
            env.reset(seed=args.seed + rank)
            return Monitor(env)

        return _init

    env = DummyVecEnv([make_env(i) for i in range(args.n_envs)])
    model = PPO(
        "MlpPolicy",
        env,
        verbose=1,
        seed=args.seed,
        learning_rate=args.learning_rate,
        n_steps=args.n_steps,
        batch_size=args.batch_size,
        tensorboard_log=str(args.tensorboard_log) if args.tensorboard_log else None,
        device=args.device,
    )
    model.learn(total_timesteps=args.total_timesteps)
    model.save(save_path)
    env.close()
    print(f"[rl_tracking] policy saved: {save_path}")


if __name__ == "__main__":
    main()
