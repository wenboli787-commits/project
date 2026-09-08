from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import mujoco as mj
import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError as exc:  # pragma: no cover - exercised only when optional deps are missing.
    raise ImportError(
        "RL tracking requires gymnasium. Install tracking extras with "
        "`WITH_RL=1 bash tracking/scripts/setup_tracking_ubuntu22_04.sh` or "
        "`pip install -r tracking/requirements-rl.txt`."
    ) from exc

from .motion import load_robot_motion_reference
from .mujoco_pd import MuJoCoPDTracker, PDTrackerConfig
from .quaternion import quat_error_vector_wxyz


@dataclass
class RewardWeights:
    alive: float = 0.2
    dof: float = 1.0
    root_pos: float = 0.35
    root_quat: float = 0.25
    action: float = 0.01
    ctrl: float = 0.0001
    scales: dict[str, float] = field(
        default_factory=lambda: {
            "dof": 8.0,
            "root_pos": 4.0,
            "root_quat": 2.0,
        }
    )


class GMRMotionTrackingEnv(gym.Env):
    """Gymnasium environment for RL residual motion tracking.

    The policy action is a residual joint target in radians/meters. A torque PD
    controller tracks reference_dof + action_scale * action at each frame.
    """

    metadata = {"render_modes": ["human"], "render_fps": 30}

    def __init__(
        self,
        robot: str,
        robot_motion_path: str | Path,
        root_mode: str = "free",
        kp: float = 80.0,
        kd: float = 4.0,
        action_scale: float = 0.25,
        max_episode_steps: int | None = None,
        random_start: bool = True,
        start_frame: int = 0,
        max_frames: int | None = None,
        min_root_height: float = 0.35,
        max_root_height: float = 2.5,
        control_limit_mode: str = "auto",
        max_torque: float | None = None,
        steps_per_frame: int | None = None,
        match_motion_dt: bool = True,
        clip_target_to_joint_limits: bool = True,
        render_mode: str | None = None,
        reward_weights: RewardWeights | None = None,
    ) -> None:
        super().__init__()
        if render_mode not in (None, "human"):
            raise ValueError("render_mode must be None or 'human'.")

        self.robot = robot
        self.motion = load_robot_motion_reference(
            robot_motion_path,
            start_frame=start_frame,
            max_frames=max_frames,
        )
        self.action_scale = float(action_scale)
        self.random_start = bool(random_start)
        self.min_root_height = float(min_root_height)
        self.max_root_height = float(max_root_height)
        self.max_episode_steps = max_episode_steps or (self.motion.frame_count - 1)
        self.render_mode = render_mode
        self.reward_weights = reward_weights or RewardWeights()
        self.np_random: np.random.Generator

        config = PDTrackerConfig(
            kp=kp,
            kd=kd,
            root_mode=root_mode,
            control_limit_mode=control_limit_mode,
            max_torque=max_torque,
            steps_per_frame=steps_per_frame,
            match_motion_dt=match_motion_dt,
            clip_target_to_joint_limits=clip_target_to_joint_limits,
            render=render_mode == "human",
            rate_limit=render_mode == "human",
        )
        self.tracker = MuJoCoPDTracker(robot=robot, motion=self.motion, config=config)
        self.actuator_map = self.tracker.actuator_map
        self.frame_index = 0
        self.episode_steps = 0

        self.action_space = spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(self.actuator_map.size,),
            dtype=np.float32,
        )
        self.tracker.reset(0)
        obs = self._get_obs()
        high = np.full(obs.shape, np.inf, dtype=np.float32)
        self.observation_space = spaces.Box(-high, high, dtype=np.float32)

    def _sample_start_frame(self) -> int:
        if not self.random_start:
            return 0
        upper = max(1, self.motion.frame_count - self.max_episode_steps - 1)
        return int(self.np_random.integers(0, upper))

    def _reference_indices(self) -> tuple[int, int]:
        current = int(np.clip(self.frame_index, 0, self.motion.frame_count - 1))
        nxt = int(np.clip(current + 1, 0, self.motion.frame_count - 1))
        return current, nxt

    def _get_obs(self) -> np.ndarray:
        current_idx, next_idx = self._reference_indices()
        data = self.tracker.data
        current_q = data.qpos[self.actuator_map.qpos_indices]
        current_v = data.qvel[self.actuator_map.qvel_indices]
        ref_q = self.motion.qpos[current_idx, self.actuator_map.qpos_indices]
        ref_v = self.motion.dof_vel[current_idx, self.actuator_map.dof_indices]
        next_ref_q = self.motion.qpos[next_idx, self.actuator_map.qpos_indices]
        root_pos_error = data.qpos[:3] - self.motion.qpos[current_idx, :3]
        root_quat_error = quat_error_vector_wxyz(data.qpos[3:7], self.motion.qpos[current_idx, 3:7])
        phase = 2.0 * np.pi * current_idx / max(1, self.motion.frame_count - 1)
        obs = np.concatenate(
            [
                current_q - ref_q,
                current_v - ref_v,
                ref_q,
                next_ref_q,
                root_pos_error,
                root_quat_error,
                data.qvel[:6],
                np.asarray([np.sin(phase), np.cos(phase)], dtype=np.float64),
            ]
        )
        return obs.astype(np.float32)

    def _compute_reward(
        self,
        action: np.ndarray,
        metrics: dict[str, float],
    ) -> float:
        weights = self.reward_weights
        dof_term = np.exp(-weights.scales["dof"] * metrics["actuated_dof_rmse"] ** 2)
        root_pos_term = np.exp(-weights.scales["root_pos"] * metrics["root_pos_error"] ** 2)
        root_quat_term = np.exp(-weights.scales["root_quat"] * metrics["root_quat_error_rad"] ** 2)
        action_penalty = float(np.mean(np.square(action)))
        ctrl_penalty = metrics["ctrl_abs_mean"]
        return float(
            weights.alive
            + weights.dof * dof_term
            + weights.root_pos * root_pos_term
            + weights.root_quat * root_quat_term
            - weights.action * action_penalty
            - weights.ctrl * ctrl_penalty
        )

    def _is_terminated(self) -> bool:
        data = self.tracker.data
        if not np.all(np.isfinite(data.qpos)) or not np.all(np.isfinite(data.qvel)):
            return True
        if self.tracker.config.root_mode == "kinematic":
            return False
        height = float(data.qpos[2])
        return height < self.min_root_height or height > self.max_root_height

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        if options and "start_frame" in options:
            self.frame_index = int(options["start_frame"])
        else:
            self.frame_index = self._sample_start_frame()
        self.episode_steps = 0
        self.tracker.reset(self.frame_index)
        obs = self._get_obs()
        return obs, {"frame_index": self.frame_index}

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        action = np.asarray(action, dtype=np.float64)
        action = np.clip(action, -1.0, 1.0)
        target_idx = int(np.clip(self.frame_index + 1, 0, self.motion.frame_count - 1))
        action_offset = self.action_scale * action
        metrics = self.tracker.step_to_reference(target_idx, action_offset=action_offset)
        self.frame_index = target_idx
        self.episode_steps += 1
        reward = self._compute_reward(action, metrics)
        terminated = self._is_terminated()
        truncated = (
            self.episode_steps >= self.max_episode_steps
            or self.frame_index >= self.motion.frame_count - 1
        )
        obs = self._get_obs()
        info: dict[str, Any] = dict(metrics)
        info.update(
            {
                "frame_index": self.frame_index,
                "episode_steps": self.episode_steps,
                "reward": reward,
            }
        )
        return obs, reward, terminated, truncated, info

    def render(self) -> None:
        self.tracker.render()

    def close(self) -> None:
        self.tracker.close()
        super().close()
