"""The simulator-independent motion representation used by every metric."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np


ArrayDict = Dict[str, np.ndarray]


@dataclass
class CanonicalMotion:
    """One motion in the evaluation package's canonical coordinate convention.

    Positions use metres and quaternions use **w, x, y, z** ordering.  Every
    time-varying array has its first dimension as frames.  Optional fields are
    deliberately kept optional: a missing measurement is reported as
    ``unavailable`` by a metric instead of being silently invented.
    """

    name: str
    source_type: str = "unknown"
    simulator: Optional[str] = None
    fps: float = 30.0
    time: Optional[np.ndarray] = None

    root_pos: Optional[np.ndarray] = None
    root_quat: Optional[np.ndarray] = None
    root_lin_vel: Optional[np.ndarray] = None
    root_ang_vel: Optional[np.ndarray] = None

    dof_pos: Optional[np.ndarray] = None
    dof_vel: Optional[np.ndarray] = None
    dof_acc: Optional[np.ndarray] = None
    dof_names: Optional[List[str]] = None
    dof_limits_lower: Optional[np.ndarray] = None
    dof_limits_upper: Optional[np.ndarray] = None

    body_positions: Optional[ArrayDict] = None
    body_quats: Optional[ArrayDict] = None
    body_lin_vels: Optional[ArrayDict] = None
    body_ang_vels: Optional[ArrayDict] = None
    end_effector_positions: Optional[ArrayDict] = None
    end_effector_quats: Optional[ArrayDict] = None

    foot_contacts: Optional[ArrayDict] = None
    contact_forces: Optional[ArrayDict] = None
    torques: Optional[np.ndarray] = None
    torque_limits_lower: Optional[np.ndarray] = None
    torque_limits_upper: Optional[np.ndarray] = None
    actions: Optional[np.ndarray] = None

    target_dof_pos: Optional[np.ndarray] = None
    target_dof_vel: Optional[np.ndarray] = None
    actual_dof_pos: Optional[np.ndarray] = None
    actual_dof_vel: Optional[np.ndarray] = None
    target_root_pos: Optional[np.ndarray] = None
    actual_root_pos: Optional[np.ndarray] = None
    target_body_positions: Optional[ArrayDict] = None
    actual_body_positions: Optional[ArrayDict] = None
    target_end_effector_positions: Optional[ArrayDict] = None
    actual_end_effector_positions: Optional[ArrayDict] = None

    joint_positions_ref: Optional[np.ndarray] = None
    joint_rotations_ref: Optional[np.ndarray] = None
    joint_names_ref: Optional[List[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.fps = float(self.fps or 30.0)
        if self.fps <= 0:
            raise ValueError(f"{self.name}: fps must be positive, got {self.fps}.")
        self._coerce_arrays()
        self.validate()

    def _coerce_arrays(self) -> None:
        for field_name in (
            "time", "root_pos", "root_quat", "root_lin_vel", "root_ang_vel",
            "dof_pos", "dof_vel", "dof_acc", "dof_limits_lower", "dof_limits_upper", "torque_limits_lower", "torque_limits_upper",
            "torques", "actions", "target_dof_pos", "target_dof_vel",
            "actual_dof_pos", "actual_dof_vel", "target_root_pos", "actual_root_pos", "joint_positions_ref",
            "joint_rotations_ref",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, np.asarray(value, dtype=float))
        for field_name in (
            "body_positions", "body_quats", "body_lin_vels", "body_ang_vels",
            "end_effector_positions", "end_effector_quats", "target_body_positions", "actual_body_positions", "target_end_effector_positions", "actual_end_effector_positions", "foot_contacts",
            "contact_forces",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, {str(k): np.asarray(v) for k, v in value.items()})

    def validate(self) -> None:
        """Validate shapes early, so confusing logs fail with an actionable error."""
        frames = self.num_frames
        for field_name, width in (
            ("root_pos", 3), ("root_quat", 4), ("root_lin_vel", 3), ("root_ang_vel", 3),
            ("target_root_pos", 3), ("actual_root_pos", 3),
        ):
            value = getattr(self, field_name)
            if value is not None:
                self._validate_frame_array(field_name, value, frames, width)
        for field_name in (
            "dof_pos", "dof_vel", "dof_acc", "torques", "actions", "target_dof_pos",
            "target_dof_vel", "actual_dof_pos", "actual_dof_vel",
        ):
            value = getattr(self, field_name)
            if value is not None:
                self._validate_frame_array(field_name, value, frames)
        for field_name, width in (
            ("body_positions", 3), ("body_quats", 4), ("body_lin_vels", 3),
            ("body_ang_vels", 3), ("end_effector_positions", 3),
            ("end_effector_quats", 4), ("target_body_positions", 3),
            ("actual_body_positions", 3), ("target_end_effector_positions", 3),
            ("actual_end_effector_positions", 3),
        ):
            values = getattr(self, field_name)
            if values:
                for key, value in values.items():
                    self._validate_frame_array(f"{field_name}[{key!r}]", value, frames, width)
        if self.time is not None and self.time.ndim != 1:
            raise ValueError(f"{self.name}: time must have shape [T], got {self.time.shape}.")
        if self.joint_positions_ref is not None:
            self._validate_frame_array("joint_positions_ref", self.joint_positions_ref, frames)
            if self.joint_positions_ref.ndim != 3 or self.joint_positions_ref.shape[-1] != 3:
                raise ValueError("joint_positions_ref must have shape [T, J, 3].")

    @staticmethod
    def _validate_frame_array(name: str, value: np.ndarray, frames: int, width: int | None = None) -> None:
        if value.ndim < 1:
            raise ValueError(f"{name} must have a frame dimension.")
        if frames and value.shape[0] != frames:
            raise ValueError(f"{name} has {value.shape[0]} frames but this motion has {frames}.")
        if width is not None and (value.ndim < 2 or value.shape[-1] != width):
            raise ValueError(f"{name} must end in dimension {width}, got {value.shape}.")

    @property
    def num_frames(self) -> int:
        """Number of frames inferred from the first available time-varying field."""
        candidates = (
            self.time, self.root_pos, self.root_quat, self.dof_pos, self.dof_vel,
            self.joint_positions_ref,
        )
        for value in candidates:
            if value is not None and value.ndim:
                return int(value.shape[0])
        for values in (self.body_positions, self.end_effector_positions, self.foot_contacts):
            if values:
                return int(next(iter(values.values())).shape[0])
        return 0

    @property
    def duration(self) -> float:
        return max(0.0, (self.num_frames - 1) / self.fps)

    def copy(self, *, name: Optional[str] = None) -> "CanonicalMotion":
        """Deep-copy numeric values, suitable for normalization or alignment."""
        kwargs: dict[str, Any] = {}
        for key, value in self.__dict__.items():
            if isinstance(value, np.ndarray):
                kwargs[key] = value.copy()
            elif isinstance(value, dict):
                kwargs[key] = {
                    k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in value.items()
                }
            elif isinstance(value, list):
                kwargs[key] = list(value)
            else:
                kwargs[key] = value
        kwargs["metadata"] = dict(self.metadata)
        if name is not None:
            kwargs["name"] = name
        return CanonicalMotion(**kwargs)

    def position(self, name: str) -> Optional[np.ndarray]:
        """Get a named trajectory from end-effectors, bodies, or reference joints."""
        if name in {"root", "pelvis"} and self.root_pos is not None:
            return self.root_pos
        for values in (self.end_effector_positions, self.body_positions):
            if values and name in values:
                return values[name]
        if self.joint_positions_ref is not None and self.joint_names_ref:
            try:
                return self.joint_positions_ref[:, self.joint_names_ref.index(name), :]
            except ValueError:
                pass
        return None

    def quaternion(self, name: str) -> Optional[np.ndarray]:
        if name in {"root", "pelvis"} and self.root_quat is not None:
            return self.root_quat
        for values in (self.end_effector_quats, self.body_quats):
            if values and name in values:
                return values[name]
        if self.joint_rotations_ref is not None and self.joint_names_ref:
            try:
                return self.joint_rotations_ref[:, self.joint_names_ref.index(name), :]
            except ValueError:
                pass
        return None
