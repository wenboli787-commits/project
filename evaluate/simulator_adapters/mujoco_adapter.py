"""MuJoCo ingestion adapter with optional forward kinematics and effort proxy."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np

from canonical_motion import CanonicalMotion
from loaders import load_canonical_motion, read_motion_file
from simulator_adapters.base_adapter import SimulatorAdapter
from utils import finite_difference


class MuJoCoAdapter(SimulatorAdapter):
    """Use MuJoCo only here; all downstream metrics remain simulator-neutral."""

    def __init__(self, robot_model: Optional[Path] = None) -> None:
        super().__init__(robot_model)
        self.model = None
        self.mj = None

    def load_motion(self, motion_path: Path, config: dict[str, Any]) -> CanonicalMotion:
        expected = dict(config.get("mujoco", {}).get("expected_keys", {}))
        expected["quaternion_order"] = config.get("input", {}).get("quaternion_order", "xyzw")
        expected["fps"] = config.get("input", {}).get("fps", 30.0)
        loader_config = {"expected_keys": expected, "input": config.get("input", {}), "quaternion_order": expected["quaternion_order"], "fps": expected["fps"]}
        motion = load_canonical_motion(motion_path, loader_config, simulator="mujoco")
        self._try_load_model()
        self._contact_body_names = {
            name for name in (
                config.get("robot", {}).get("left_foot_body"),
                config.get("robot", {}).get("right_foot_body"),
            ) if name
        }
        payload = read_motion_file(motion_path)
        if not isinstance(payload, dict):
            payload = {}
        qpos_key = str(expected.get("qpos", "qpos"))
        qvel_key = str(expected.get("qvel", "qvel"))
        qpos = payload.get(qpos_key)
        qvel = payload.get(qvel_key)
        if qpos is not None and self.model is not None:
            self._convert_qpos(motion, np.asarray(qpos, dtype=float), None if qvel is None else np.asarray(qvel, dtype=float))
        elif qpos is not None and "dof_pos" not in payload:
            # A free-joint qpos must never be silently treated as ordinary
            # articulated DOFs when the model is unavailable.
            motion.dof_pos = None
            motion.dof_vel = None
            self.warnings.append(f"{motion.name}: qpos was logged but MuJoCo model is unavailable, so free-joint-safe dof conversion is unavailable.")
        if self.model is not None and motion.dof_pos is not None:
            lower, upper = self.get_joint_limits()
            if lower is not None and lower.shape[0] == motion.dof_pos.shape[1]:
                motion.dof_limits_lower, motion.dof_limits_upper = lower, upper
            motion = self.compute_forward_kinematics(motion)
            motion = self.estimate_contacts(motion)
            motion = self.estimate_effort(motion)
        elif self.robot_model:
            self.warnings.append("MuJoCo model was unavailable; qpos/FK/limit extraction was skipped.")
        return motion

    def _try_load_model(self) -> None:
        if self.model is not None or not self.robot_model:
            return
        if not self.robot_model.is_file():
            self.warnings.append(f"MuJoCo model file not found: {self.robot_model}")
            return
        try:
            import mujoco
        except ImportError:
            self.warnings.append("Python package 'mujoco' is not installed; using logged fields only.")
            return
        try:
            self.mj = mujoco
            self.model = mujoco.MjModel.from_xml_path(str(self.robot_model))
        except Exception as exc:  # model parsing errors must not erase offline metrics
            self.warnings.append(f"Could not load MuJoCo model '{self.robot_model}': {exc}")
            self.model, self.mj = None, None

    def _free_joint_id(self) -> Optional[int]:
        if self.model is None:
            return None
        free_type = self.mj.mjtJoint.mjJNT_FREE
        for joint_id in range(self.model.njnt):
            if self.model.jnt_type[joint_id] == free_type:
                return joint_id
        return None

    def _qpos_joint_indices(self) -> list[int]:
        """Only articulated qpos values; excludes free-joint translation/quaternion."""
        if self.model is None:
            return []
        result: list[int] = []
        free_type = self.mj.mjtJoint.mjJNT_FREE
        for joint_id in range(self.model.njnt):
            if self.model.jnt_type[joint_id] == free_type:
                continue
            start = int(self.model.jnt_qposadr[joint_id])
            end = int(self.model.jnt_qposadr[joint_id + 1]) if joint_id + 1 < self.model.njnt else int(self.model.nq)
            result.extend(range(start, end))
        return result

    def _qvel_joint_indices(self) -> list[int]:
        if self.model is None:
            return []
        result: list[int] = []
        free_type = self.mj.mjtJoint.mjJNT_FREE
        for joint_id in range(self.model.njnt):
            if self.model.jnt_type[joint_id] == free_type:
                continue
            start = int(self.model.jnt_dofadr[joint_id])
            end = int(self.model.jnt_dofadr[joint_id + 1]) if joint_id + 1 < self.model.njnt else int(self.model.nv)
            result.extend(range(start, end))
        return result

    def _convert_qpos(self, motion: CanonicalMotion, qpos: np.ndarray, qvel: Optional[np.ndarray]) -> None:
        if qpos.ndim != 2 or qpos.shape[1] != self.model.nq:
            self.warnings.append(f"{motion.name}: qpos shape {qpos.shape} does not match MuJoCo nq={self.model.nq}; kept generic input.")
            return
        free_id = self._free_joint_id()
        if free_id is not None:
            root_start = int(self.model.jnt_qposadr[free_id])
            motion.root_pos = qpos[:, root_start:root_start + 3]
            # MuJoCo qpos quaternions are already wxyz, unlike GMR root_rot.
            motion.root_quat = qpos[:, root_start + 3:root_start + 7]
        positions = self._qpos_joint_indices()
        motion.dof_pos = qpos[:, positions] if positions else None
        if qvel is not None and qvel.ndim == 2 and qvel.shape[1] == self.model.nv:
            velocity_indices = self._qvel_joint_indices()
            motion.dof_vel = qvel[:, velocity_indices] if velocity_indices else None
            if free_id is not None:
                root_velocity = int(self.model.jnt_dofadr[free_id])
                motion.root_lin_vel = qvel[:, root_velocity:root_velocity + 3]
                motion.root_ang_vel = qvel[:, root_velocity + 3:root_velocity + 6]
        names: list[str] = []
        for joint_id in range(self.model.njnt):
            if self.model.jnt_type[joint_id] == self.mj.mjtJoint.mjJNT_FREE:
                continue
            joint_name = self.mj.mj_id2name(self.model, self.mj.mjtObj.mjOBJ_JOINT, joint_id) or f"joint_{joint_id}"
            count = (int(self.model.jnt_qposadr[joint_id + 1]) if joint_id + 1 < self.model.njnt else self.model.nq) - int(self.model.jnt_qposadr[joint_id])
            names.extend([joint_name] if count == 1 else [f"{joint_name}_{i}" for i in range(count)])
        motion.dof_names = names
        motion.metadata["qpos_converted_by"] = "MuJoCoAdapter; free joint excluded from dof_pos"

    def get_joint_limits(self):
        if self.model is None:
            return None, None
        lower: list[float] = []
        upper: list[float] = []
        free_type = self.mj.mjtJoint.mjJNT_FREE
        for joint_id in range(self.model.njnt):
            if self.model.jnt_type[joint_id] == free_type:
                continue
            start = int(self.model.jnt_qposadr[joint_id])
            end = int(self.model.jnt_qposadr[joint_id + 1]) if joint_id + 1 < self.model.njnt else int(self.model.nq)
            count = end - start
            if count == 1 and self.model.jnt_limited[joint_id]:
                lo, hi = self.model.jnt_range[joint_id]
            else:
                lo, hi = -np.inf, np.inf
            lower.extend([lo] * count)
            upper.extend([hi] * count)
        return np.asarray(lower, dtype=float), np.asarray(upper, dtype=float)

    def compute_forward_kinematics(self, motion: CanonicalMotion) -> CanonicalMotion:
        if self.model is None or motion.dof_pos is None:
            return motion
        # Reassemble qpos only when a free base + articulated positions are known.
        free_id = self._free_joint_id()
        if free_id is not None and (motion.root_pos is None or motion.root_quat is None):
            self.warnings.append(f"{motion.name}: no root pose available to run MuJoCo FK.")
            return motion
        qpos_indices = self._qpos_joint_indices()
        if len(qpos_indices) != motion.dof_pos.shape[1]:
            self.warnings.append(f"{motion.name}: dof_pos dimensionality does not match MuJoCo articulated qpos; FK skipped.")
            return motion
        data = self.mj.MjData(self.model)
        body_positions: dict[str, np.ndarray] = {self.mj.mj_id2name(self.model, self.mj.mjtObj.mjOBJ_BODY, index) or f"body_{index}": np.empty((motion.num_frames, 3)) for index in range(1, self.model.nbody)}
        body_quats: dict[str, np.ndarray] = {name: np.empty((motion.num_frames, 4)) for name in body_positions}
        for frame in range(motion.num_frames):
            data.qpos[:] = self.model.qpos0
            if free_id is not None:
                start = int(self.model.jnt_qposadr[free_id])
                data.qpos[start:start + 3] = motion.root_pos[frame]
                data.qpos[start + 3:start + 7] = motion.root_quat[frame]
            data.qpos[qpos_indices] = motion.dof_pos[frame]
            self.mj.mj_forward(self.model, data)
            for body_id in range(1, self.model.nbody):
                body_name = self.mj.mj_id2name(self.model, self.mj.mjtObj.mjOBJ_BODY, body_id) or f"body_{body_id}"
                body_positions[body_name][frame] = data.xpos[body_id]
                body_quats[body_name][frame] = data.xquat[body_id]
        motion.body_positions = body_positions
        motion.body_quats = body_quats
        motion.metadata["forward_kinematics"] = "MuJoCo mj_forward"
        return motion

    def estimate_contacts(self, motion: CanonicalMotion) -> CanonicalMotion:
        if self.model is None or motion.dof_pos is None or not getattr(self, "_contact_body_names", None):
            return motion
        free_id = self._free_joint_id()
        indices = self._qpos_joint_indices()
        if len(indices) != motion.dof_pos.shape[1] or (free_id is not None and (motion.root_pos is None or motion.root_quat is None)):
            return motion
        available = {self.mj.mj_id2name(self.model, self.mj.mjtObj.mjOBJ_BODY, body_id) or f"body_{body_id}" for body_id in range(self.model.nbody)}
        wanted = self._contact_body_names & available
        if not wanted:
            self.warnings.append(f"{motion.name}: configured foot bodies were not found in the MuJoCo model; exact contacts skipped.")
            return motion
        contacts = {name: np.zeros(motion.num_frames, dtype=bool) for name in wanted}
        data = self.mj.MjData(self.model)
        for frame in range(motion.num_frames):
            data.qpos[:] = self.model.qpos0
            if free_id is not None:
                start = int(self.model.jnt_qposadr[free_id])
                data.qpos[start:start + 3] = motion.root_pos[frame]
                data.qpos[start + 3:start + 7] = motion.root_quat[frame]
            data.qpos[indices] = motion.dof_pos[frame]
            self.mj.mj_forward(self.model, data)
            for contact_index in range(data.ncon):
                contact = data.contact[contact_index]
                body_a = self.mj.mj_id2name(self.model, self.mj.mjtObj.mjOBJ_BODY, int(self.model.geom_bodyid[contact.geom1]))
                body_b = self.mj.mj_id2name(self.model, self.mj.mjtObj.mjOBJ_BODY, int(self.model.geom_bodyid[contact.geom2]))
                for body_name in (body_a, body_b):
                    if body_name in contacts:
                        contacts[body_name][frame] = True
        motion.foot_contacts = {**(motion.foot_contacts or {}), **contacts}
        motion.metadata["contact_source"] = "MuJoCo geometric contacts"
        return motion

    def estimate_effort(self, motion: CanonicalMotion) -> CanonicalMotion:
        if motion.torques is not None or self.model is None or motion.dof_pos is None:
            return motion
        if motion.dof_vel is None:
            self.warnings.append(f"{motion.name}: no torque/ctrl or dof_vel; inverse-dynamics effort is unavailable.")
            return motion
        free_id = self._free_joint_id()
        qpos_indices, qvel_indices = self._qpos_joint_indices(), self._qvel_joint_indices()
        if len(qpos_indices) != motion.dof_pos.shape[1] or len(qvel_indices) != motion.dof_vel.shape[1]:
            self.warnings.append(f"{motion.name}: cannot map logged dofs back to MuJoCo inverse dynamics.")
            return motion
        if free_id is not None and (motion.root_pos is None or motion.root_quat is None):
            return motion
        data = self.mj.MjData(self.model)
        acceleration = finite_difference(motion.dof_vel, motion.fps)
        effort = np.empty_like(motion.dof_vel)
        for frame in range(motion.num_frames):
            data.qpos[:] = self.model.qpos0
            data.qvel[:] = 0.0
            data.qacc[:] = 0.0
            if free_id is not None:
                qpos_start, qvel_start = int(self.model.jnt_qposadr[free_id]), int(self.model.jnt_dofadr[free_id])
                data.qpos[qpos_start:qpos_start + 3] = motion.root_pos[frame]
                data.qpos[qpos_start + 3:qpos_start + 7] = motion.root_quat[frame]
                if motion.root_lin_vel is not None:
                    data.qvel[qvel_start:qvel_start + 3] = motion.root_lin_vel[frame]
                if motion.root_ang_vel is not None:
                    data.qvel[qvel_start + 3:qvel_start + 6] = motion.root_ang_vel[frame]
            data.qpos[qpos_indices] = motion.dof_pos[frame]
            data.qvel[qvel_indices] = motion.dof_vel[frame]
            data.qacc[qvel_indices] = acceleration[frame]
            self.mj.mj_inverse(self.model, data)
            effort[frame] = data.qfrc_inverse[qvel_indices]
        motion.torques = effort
        motion.metadata["torque_source"] = "MuJoCo inverse dynamics qfrc_inverse (effort proxy)"
        return motion
