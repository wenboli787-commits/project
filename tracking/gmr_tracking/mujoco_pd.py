from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mujoco as mj
import numpy as np

from .motion import RobotMotionReference
from .paths import get_robot_base_name, get_robot_xml_path, get_viewer_camera_distance
from .quaternion import quat_angle_error_wxyz


@dataclass(frozen=True)
class ActuatorJointMap:
    actuator_ids: np.ndarray
    joint_ids: np.ndarray
    qpos_indices: np.ndarray
    qvel_indices: np.ndarray
    dof_indices: np.ndarray
    joint_limited: np.ndarray
    joint_ranges: np.ndarray
    joint_names: list[str]
    actuator_names: list[str]

    @property
    def size(self) -> int:
        return int(self.actuator_ids.shape[0])


@dataclass
class PDTrackerConfig:
    kp: float = 80.0
    kd: float = 4.0
    root_mode: str = "free"
    control_limit_mode: str = "auto"
    max_torque: float | None = None
    steps_per_frame: int | None = None
    match_motion_dt: bool = True
    clip_target_to_joint_limits: bool = True
    render: bool = False
    rate_limit: bool = False
    camera_follow: bool = True


def build_actuator_joint_map(model: mj.MjModel) -> ActuatorJointMap:
    actuator_ids: list[int] = []
    joint_ids: list[int] = []
    qpos_indices: list[int] = []
    qvel_indices: list[int] = []
    dof_indices: list[int] = []
    joint_limited: list[bool] = []
    joint_ranges: list[np.ndarray] = []
    joint_names: list[str] = []
    actuator_names: list[str] = []

    for actuator_id in range(model.nu):
        joint_id = int(model.actuator_trnid[actuator_id, 0])
        if joint_id < 0:
            continue
        joint_type = int(model.jnt_type[joint_id])
        if joint_type not in (int(mj.mjtJoint.mjJNT_HINGE), int(mj.mjtJoint.mjJNT_SLIDE)):
            continue
        qpos_index = int(model.jnt_qposadr[joint_id])
        qvel_index = int(model.jnt_dofadr[joint_id])
        if qpos_index < 7:
            continue
        actuator_ids.append(actuator_id)
        joint_ids.append(joint_id)
        qpos_indices.append(qpos_index)
        qvel_indices.append(qvel_index)
        dof_indices.append(qpos_index - 7)
        joint_limited.append(bool(model.jnt_limited[joint_id]))
        joint_ranges.append(model.jnt_range[joint_id].copy())
        joint_names.append(model.joint(joint_id).name)
        actuator_names.append(model.actuator(actuator_id).name)

    if not actuator_ids:
        raise RuntimeError("No hinge/slide joint actuators were found in the MuJoCo model.")

    return ActuatorJointMap(
        actuator_ids=np.asarray(actuator_ids, dtype=np.int32),
        joint_ids=np.asarray(joint_ids, dtype=np.int32),
        qpos_indices=np.asarray(qpos_indices, dtype=np.int32),
        qvel_indices=np.asarray(qvel_indices, dtype=np.int32),
        dof_indices=np.asarray(dof_indices, dtype=np.int32),
        joint_limited=np.asarray(joint_limited, dtype=bool),
        joint_ranges=np.asarray(joint_ranges, dtype=np.float64),
        joint_names=joint_names,
        actuator_names=actuator_names,
    )


class MuJoCoPDTracker:
    def __init__(
        self,
        robot: str,
        motion: RobotMotionReference,
        config: PDTrackerConfig | None = None,
        xml_path: str | Path | None = None,
    ) -> None:
        self.robot = robot
        self.motion = motion
        self.config = config or PDTrackerConfig()
        self.xml_path = Path(xml_path).resolve() if xml_path is not None else get_robot_xml_path(robot)
        self.model = mj.MjModel.from_xml_path(str(self.xml_path))
        self.data = mj.MjData(self.model)
        self.original_timestep = float(self.model.opt.timestep)
        self.actuator_map = build_actuator_joint_map(self.model)

        if self.model.nq != motion.qpos_dim:
            raise ValueError(
                f"Model nq={self.model.nq} does not match motion qpos_dim={motion.qpos_dim}. "
                "Check --robot and --robot_motion_path."
            )
        max_dof_index = int(np.max(self.actuator_map.dof_indices))
        if max_dof_index >= motion.dof_count:
            raise ValueError(
                f"Actuated dof index {max_dof_index} exceeds motion dof_count={motion.dof_count}."
            )
        if self.config.root_mode not in ("free", "kinematic"):
            raise ValueError("root_mode must be 'free' or 'kinematic'")

        self.steps_per_frame = self._resolve_steps_per_frame()
        if self.config.match_motion_dt:
            self.model.opt.timestep = (1.0 / self.motion.fps) / self.steps_per_frame
        self._configure_control_limits()
        self.viewer = None
        self._next_render_time: float | None = None
        self._base_body_id = self._resolve_base_body_id()
        self.last_ctrl = np.zeros(self.model.nu, dtype=np.float64)
        self.last_target_clip_fraction = 0.0

    def _resolve_steps_per_frame(self) -> int:
        if self.config.steps_per_frame is not None:
            if self.config.steps_per_frame <= 0:
                raise ValueError("steps_per_frame must be positive.")
            return int(self.config.steps_per_frame)
        frame_dt = 1.0 / self.motion.fps
        return max(1, int(round(frame_dt / float(self.model.opt.timestep))))

    def _resolve_base_body_id(self) -> int | None:
        base_name = get_robot_base_name(self.robot)
        if not base_name:
            return None
        try:
            return int(self.model.body(base_name).id)
        except KeyError:
            return None

    def _configure_control_limits(self) -> None:
        mode = self.config.control_limit_mode
        if mode not in ("auto", "model", "joint", "none"):
            raise ValueError("control_limit_mode must be auto, model, joint or none.")

        if mode == "none":
            self.model.actuator_ctrllimited[:] = False
            return

        use_joint_ranges = mode == "joint"
        if mode == "auto":
            ranges = self.model.actuator_ctrlrange[self.actuator_map.actuator_ids]
            max_abs = np.max(np.abs(ranges), axis=1)
            use_joint_ranges = bool(np.median(max_abs) <= 1.0)

        if use_joint_ranges:
            for actuator_id in self.actuator_map.actuator_ids:
                joint_id = int(self.model.actuator_trnid[actuator_id, 0])
                if bool(self.model.jnt_actfrclimited[joint_id]):
                    self.model.actuator_ctrlrange[actuator_id] = self.model.jnt_actfrcrange[joint_id]
                    self.model.actuator_ctrllimited[actuator_id] = True

        if self.config.max_torque is not None:
            limit = abs(float(self.config.max_torque))
            self.model.actuator_ctrlrange[self.actuator_map.actuator_ids, 0] = -limit
            self.model.actuator_ctrlrange[self.actuator_map.actuator_ids, 1] = limit
            self.model.actuator_ctrllimited[self.actuator_map.actuator_ids] = True

    def reset(self, frame_index: int = 0) -> None:
        frame_index = int(np.clip(frame_index, 0, self.motion.frame_count - 1))
        mj.mj_resetData(self.model, self.data)
        self.data.qpos[:] = self.motion.qpos[frame_index]
        self.data.qvel[:] = 0.0
        self.data.qvel[self.actuator_map.qvel_indices] = self.motion.dof_vel[
            frame_index, self.actuator_map.dof_indices
        ]
        mj.mj_forward(self.model, self.data)
        self.last_ctrl[:] = 0.0

    def _pin_root(self, target_qpos: np.ndarray) -> None:
        self.data.qpos[:7] = target_qpos[:7]
        self.data.qvel[:6] = 0.0
        mj.mj_forward(self.model, self.data)

    def _clip_ctrl(self, ctrl: np.ndarray) -> tuple[np.ndarray, float]:
        limited = self.model.actuator_ctrllimited.astype(bool)
        clipped = ctrl.copy()
        if np.any(limited):
            low = self.model.actuator_ctrlrange[:, 0]
            high = self.model.actuator_ctrlrange[:, 1]
            before = clipped.copy()
            clipped[limited] = np.clip(clipped[limited], low[limited], high[limited])
            changed = np.abs(before - clipped) > 1e-9
            saturation_fraction = float(np.mean(changed[self.actuator_map.actuator_ids]))
        else:
            saturation_fraction = 0.0
        return clipped, saturation_fraction

    def apply_pd_control(
        self,
        target_frame_index: int,
        action_offset: np.ndarray | None = None,
    ) -> float:
        target_qpos = self.motion.qpos[target_frame_index]
        target_q = target_qpos[self.actuator_map.qpos_indices].copy()
        if action_offset is not None:
            action_offset = np.asarray(action_offset, dtype=np.float64)
            if action_offset.shape != target_q.shape:
                raise ValueError(
                    f"action_offset shape {action_offset.shape} does not match target shape {target_q.shape}"
                )
            target_q += action_offset
        target_q, self.last_target_clip_fraction = self._clip_target_q(target_q)

        current_q = self.data.qpos[self.actuator_map.qpos_indices]
        current_v = self.data.qvel[self.actuator_map.qvel_indices]
        target_v = self.motion.dof_vel[target_frame_index, self.actuator_map.dof_indices]
        torque = self.config.kp * (target_q - current_q) + self.config.kd * (target_v - current_v)

        ctrl = np.zeros(self.model.nu, dtype=np.float64)
        ctrl[self.actuator_map.actuator_ids] = torque
        ctrl, saturation_fraction = self._clip_ctrl(ctrl)
        self.data.ctrl[:] = ctrl
        self.last_ctrl[:] = ctrl
        return saturation_fraction

    def _clip_target_q(self, target_q: np.ndarray) -> tuple[np.ndarray, float]:
        if not self.config.clip_target_to_joint_limits:
            return target_q, 0.0
        limited = self.actuator_map.joint_limited
        if not np.any(limited):
            return target_q, 0.0
        clipped = target_q.copy()
        lows = self.actuator_map.joint_ranges[:, 0]
        highs = self.actuator_map.joint_ranges[:, 1]
        before = clipped.copy()
        clipped[limited] = np.clip(clipped[limited], lows[limited], highs[limited])
        changed = np.abs(before - clipped) > 1e-9
        return clipped, float(np.mean(changed))

    def step_to_reference(
        self,
        target_frame_index: int,
        action_offset: np.ndarray | None = None,
    ) -> dict[str, float]:
        target_frame_index = int(np.clip(target_frame_index, 0, self.motion.frame_count - 1))
        target_qpos = self.motion.qpos[target_frame_index]
        saturation_values: list[float] = []
        target_clip_values: list[float] = []

        for _ in range(self.steps_per_frame):
            if self.config.root_mode == "kinematic":
                self._pin_root(target_qpos)
            saturation_values.append(self.apply_pd_control(target_frame_index, action_offset))
            target_clip_values.append(self.last_target_clip_fraction)
            mj.mj_step(self.model, self.data)
            if self.config.root_mode == "kinematic":
                self._pin_root(target_qpos)

        metrics = self.compute_metrics(target_frame_index)
        metrics["torque_saturation_fraction"] = float(np.mean(saturation_values))
        metrics["target_joint_limit_clip_fraction"] = float(np.mean(target_clip_values))
        metrics["target_frame_index"] = float(target_frame_index)
        metrics["sim_time"] = float(self.data.time)
        if self.config.render:
            self.render()
        return metrics

    def compute_metrics(self, target_frame_index: int) -> dict[str, float]:
        target_qpos = self.motion.qpos[target_frame_index]
        dof_error = self.data.qpos[7:] - target_qpos[7:]
        act_error = self.data.qpos[self.actuator_map.qpos_indices] - target_qpos[
            self.actuator_map.qpos_indices
        ]
        root_pos_error = self.data.qpos[:3] - target_qpos[:3]
        root_quat_error = quat_angle_error_wxyz(self.data.qpos[3:7], target_qpos[3:7])
        actuator_ctrl = self.last_ctrl[self.actuator_map.actuator_ids]
        root_xy_error = float(np.linalg.norm(root_pos_error[:2]))
        root_height_error = float(abs(root_pos_error[2]))
        return {
            "dof_rmse": float(np.sqrt(np.mean(np.square(dof_error)))),
            "actuated_dof_rmse": float(np.sqrt(np.mean(np.square(act_error)))),
            "root_pos_error": float(np.linalg.norm(root_pos_error)),
            "root_xy_error": root_xy_error,
            "root_height_error": root_height_error,
            "root_quat_error_rad": float(root_quat_error),
            "root_height": float(self.data.qpos[2]),
            "ctrl_abs_mean": float(np.mean(np.abs(actuator_ctrl))),
            "ctrl_abs_max": float(np.max(np.abs(actuator_ctrl))),
        }

    def render(self) -> None:
        if self.viewer is None:
            import mujoco.viewer as mjv

            self.viewer = mjv.launch_passive(
                model=self.model,
                data=self.data,
                show_left_ui=False,
                show_right_ui=False,
            )
        if self.config.camera_follow and self._base_body_id is not None:
            self.viewer.cam.lookat = self.data.xpos[self._base_body_id]
            self.viewer.cam.distance = get_viewer_camera_distance(self.robot)
            self.viewer.cam.elevation = -10
        self.viewer.sync()
        if self.config.rate_limit:
            now = time.perf_counter()
            frame_dt = 1.0 / self.motion.fps
            if self._next_render_time is None:
                self._next_render_time = now + frame_dt
            else:
                sleep_time = self._next_render_time - now
                if sleep_time > 0:
                    time.sleep(sleep_time)
                self._next_render_time += frame_dt

    def close(self) -> None:
        if self.viewer is not None:
            self.viewer.close()
            self.viewer = None


def summarize_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    if not rows:
        return {}
    keys = [
        "dof_rmse",
        "actuated_dof_rmse",
        "root_pos_error",
        "root_xy_error",
        "root_height_error",
        "root_quat_error_rad",
        "ctrl_abs_mean",
        "ctrl_abs_max",
        "torque_saturation_fraction",
        "target_joint_limit_clip_fraction",
    ]
    summary: dict[str, float] = {}
    for key in keys:
        values = np.asarray([float(row[key]) for row in rows if key in row], dtype=np.float64)
        if values.size == 0:
            continue
        summary[f"{key}_mean"] = float(np.mean(values))
        summary[f"{key}_max"] = float(np.max(values))
    return summary
