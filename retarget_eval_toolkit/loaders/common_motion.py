from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


KEYPOINT_ALIASES: Dict[str, List[str]] = {
    "pelvis": ["pelvis", "root", "hips", "hip", "Hips"],
    "root": ["root", "pelvis", "hips", "Hips"],
    "head": ["head", "Head", "head_link"],
    "left_hand": ["left_hand", "left_wrist", "LeftHand", "LeftWrist", "left_rubber_hand", "left_wrist_yaw_link"],
    "right_hand": ["right_hand", "right_wrist", "RightHand", "RightWrist", "right_rubber_hand", "right_wrist_yaw_link"],
    "left_foot": ["left_foot", "left_ankle", "LeftFoot", "LeftToe", "LeftFootMod", "left_toe_link", "left_ankle_roll_link"],
    "right_foot": ["right_foot", "right_ankle", "RightFoot", "RightToe", "RightFootMod", "right_toe_link", "right_ankle_roll_link"],
    "left_knee": ["left_knee", "LeftLeg", "LeftKnee", "left_knee_link"],
    "right_knee": ["right_knee", "RightLeg", "RightKnee", "right_knee_link"],
    "left_elbow": ["left_elbow", "LeftForeArm", "LeftElbow", "left_elbow_link"],
    "right_elbow": ["right_elbow", "RightForeArm", "RightElbow", "right_elbow_link"],
    "torso": ["torso", "spine3", "Spine2", "Chest", "torso_link"],
}


@dataclass
class MotionData:
    """Unified motion representation used by all metrics.

    Quaternion convention: every quaternion stored in this dataclass is `wxyz`.
    Loaders convert file-specific conventions such as GMR PKL `root_rot=xyzw`
    before constructing `MotionData`.
    """

    name: str
    fps: float
    num_frames: int

    root_pos: Optional[np.ndarray] = None
    root_rot: Optional[np.ndarray] = None

    joint_pos: Optional[np.ndarray] = None
    joint_rot: Optional[np.ndarray] = None
    joint_names: Optional[List[str]] = None

    qpos: Optional[np.ndarray] = None
    qvel: Optional[np.ndarray] = None
    qacc: Optional[np.ndarray] = None
    dof_pos: Optional[np.ndarray] = None
    dof_names: Optional[List[str]] = None
    joint_limits_lower: Optional[np.ndarray] = None
    joint_limits_upper: Optional[np.ndarray] = None
    joint_velocity_limits: Optional[np.ndarray] = None

    left_foot_pos: Optional[np.ndarray] = None
    right_foot_pos: Optional[np.ndarray] = None
    left_hand_pos: Optional[np.ndarray] = None
    right_hand_pos: Optional[np.ndarray] = None
    head_pos: Optional[np.ndarray] = None
    pelvis_pos: Optional[np.ndarray] = None

    contacts: Optional[Dict[str, np.ndarray]] = None
    keypoints: Dict[str, np.ndarray] = field(default_factory=dict)
    keypoint_quats: Dict[str, np.ndarray] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    source_path: Optional[str] = None
    method: Optional[str] = None

    def copy(self) -> "MotionData":
        """Return a deep copy of the motion."""
        import copy

        return copy.deepcopy(self)

    def refresh_num_frames(self) -> None:
        """Refresh `num_frames` from the first available time-varying field."""
        candidates = [
            self.root_pos,
            self.root_rot,
            self.joint_pos,
            self.qpos,
            self.qvel,
            self.qacc,
            self.dof_pos,
            self.left_foot_pos,
            self.right_foot_pos,
            self.left_hand_pos,
            self.right_hand_pos,
            self.head_pos,
            self.pelvis_pos,
        ]
        for arr in candidates:
            if arr is not None:
                self.num_frames = int(np.asarray(arr).shape[0])
                return
        for mapping in [self.keypoints, self.keypoint_quats, self.contacts]:
            if mapping:
                self.num_frames = int(np.asarray(next(iter(mapping.values()))).shape[0])
                return
        self.num_frames = 0

    def ensure_keypoint_aliases(self) -> None:
        """Populate standard keypoint fields from known aliases when possible."""
        if self.pelvis_pos is not None:
            self.keypoints.setdefault("pelvis", self.pelvis_pos)
            self.keypoints.setdefault("root", self.pelvis_pos)
        if self.root_pos is not None:
            self.keypoints.setdefault("root", self.root_pos)
            self.keypoints.setdefault("pelvis", self.root_pos)
            self.pelvis_pos = self.pelvis_pos if self.pelvis_pos is not None else self.root_pos
        for field_name in ["left_foot", "right_foot", "left_hand", "right_hand", "head", "pelvis"]:
            value = getattr(self, f"{field_name}_pos", None)
            if value is not None:
                self.keypoints.setdefault(field_name, value)

        if self.joint_pos is not None and self.joint_names:
            lower_to_name = {normalize_name(name): name for name in self.joint_names}
            for standard, aliases in KEYPOINT_ALIASES.items():
                if standard in self.keypoints:
                    continue
                for alias in aliases:
                    idx_name = lower_to_name.get(normalize_name(alias))
                    if idx_name is None:
                        continue
                    idx = self.joint_names.index(idx_name)
                    self.keypoints[standard] = np.asarray(self.joint_pos)[:, idx, :]
                    break

        for standard, aliases in KEYPOINT_ALIASES.items():
            if standard in self.keypoints:
                continue
            for alias in aliases:
                if alias in self.keypoints:
                    self.keypoints[standard] = self.keypoints[alias]
                    break

        self.left_foot_pos = self.left_foot_pos if self.left_foot_pos is not None else self.keypoints.get("left_foot")
        self.right_foot_pos = self.right_foot_pos if self.right_foot_pos is not None else self.keypoints.get("right_foot")
        self.left_hand_pos = self.left_hand_pos if self.left_hand_pos is not None else self.keypoints.get("left_hand")
        self.right_hand_pos = self.right_hand_pos if self.right_hand_pos is not None else self.keypoints.get("right_hand")
        self.head_pos = self.head_pos if self.head_pos is not None else self.keypoints.get("head")
        self.pelvis_pos = self.pelvis_pos if self.pelvis_pos is not None else self.keypoints.get("pelvis")
        if self.root_pos is None and self.pelvis_pos is not None:
            self.root_pos = self.pelvis_pos
        if self.root_rot is not None:
            self.keypoint_quats.setdefault("root", self.root_rot)
            self.keypoint_quats.setdefault("pelvis", self.root_rot)

    def infer_missing_derivatives(self) -> None:
        """Infer qvel/qacc from qpos or dof_pos using finite differences."""
        if self.qpos is None and self.root_pos is not None and self.root_rot is not None and self.dof_pos is not None:
            self.qpos = np.concatenate([self.root_pos, self.root_rot, self.dof_pos], axis=1)
        if self.dof_pos is None and self.qpos is not None:
            self.dof_pos = self.qpos[:, 7:] if self.qpos.shape[1] > 7 else self.qpos
        if self.qvel is None:
            source = self.qpos if self.qpos is not None else self.dof_pos
            self.qvel = finite_difference(source, self.fps) if source is not None else None
        if self.qacc is None:
            self.qacc = finite_difference(self.qvel, self.fps) if self.qvel is not None else None

    def get_keypoint(self, name: str) -> Optional[np.ndarray]:
        """Return a standard keypoint trajectory, or `None` if unavailable."""
        if name in {"root", "pelvis"} and self.root_pos is not None:
            return self.root_pos
        self.ensure_keypoint_aliases()
        return self.keypoints.get(name)

    def get_quat(self, name: str) -> Optional[np.ndarray]:
        """Return a standard orientation trajectory in wxyz, or `None`."""
        if name in {"root", "pelvis"} and self.root_rot is not None:
            return self.root_rot
        return self.keypoint_quats.get(name)


def normalize_name(name: str) -> str:
    """Normalize names for robust matching."""
    return str(name).strip().lower().replace(" ", "_").replace("-", "_")


def finite_difference(arr: Optional[np.ndarray], fps: float) -> Optional[np.ndarray]:
    """Compute a time derivative with edge-order-safe gradients."""
    if arr is None:
        return None
    arr = np.asarray(arr, dtype=float)
    if arr.shape[0] < 2:
        return np.zeros_like(arr, dtype=float)
    return np.gradient(arr, 1.0 / float(fps), axis=0)


def as_array(value: Any, dtype=float) -> Optional[np.ndarray]:
    """Convert a value to ndarray while preserving missing values."""
    if value is None:
        return None
    arr = np.asarray(value, dtype=dtype)
    if arr.dtype == object and arr.shape == ():
        return as_array(arr.item(), dtype=dtype)
    return arr


def unwrap_np_value(value: Any) -> Any:
    """Unwrap scalar object arrays returned by numpy loads."""
    if isinstance(value, np.ndarray) and value.dtype == object and value.shape == ():
        return value.item()
    return value


def read_names(value: Any) -> Optional[List[str]]:
    """Decode a list of string names from numpy/list payloads."""
    if value is None:
        return None
    if isinstance(value, np.ndarray):
        value = value.tolist()
    if not isinstance(value, (list, tuple)):
        return None
    names = []
    for item in value:
        if isinstance(item, bytes):
            names.append(item.decode("utf-8", errors="ignore"))
        else:
            names.append(str(item))
    return names


def first_existing(raw: Dict[str, Any], names: List[str]) -> Any:
    """Return the first existing key from a dict."""
    for name in names:
        if name in raw:
            return raw[name]
    return None


def motion_name_from_path(path: str | Path) -> str:
    """Return a stable motion name from a file path."""
    return Path(path).stem


def quat_xyzw_to_wxyz(q: np.ndarray) -> np.ndarray:
    """Convert quaternion array from xyzw to wxyz."""
    q = np.asarray(q, dtype=float)
    return q[..., [3, 0, 1, 2]]


def quat_wxyz_to_xyzw(q: np.ndarray) -> np.ndarray:
    """Convert quaternion array from wxyz to xyzw."""
    q = np.asarray(q, dtype=float)
    return q[..., [1, 2, 3, 0]]


def rotvec_to_wxyz(rotvec: np.ndarray) -> np.ndarray:
    """Convert axis-angle rotation vectors to wxyz quaternions."""
    rotvec = np.asarray(rotvec, dtype=float)
    try:
        from scipy.spatial.transform import Rotation as R

        return quat_xyzw_to_wxyz(R.from_rotvec(rotvec.reshape(-1, 3)).as_quat()).reshape(rotvec.shape[:-1] + (4,))
    except Exception:
        angle = np.linalg.norm(rotvec, axis=-1, keepdims=True)
        axis = np.divide(rotvec, angle, out=np.zeros_like(rotvec), where=angle > 1e-12)
        half = 0.5 * angle
        return np.concatenate([np.cos(half), axis * np.sin(half)], axis=-1)


def make_motion(
    path: str | Path,
    fps: float,
    *,
    method: Optional[str] = None,
    root_pos: Optional[np.ndarray] = None,
    root_rot: Optional[np.ndarray] = None,
    joint_pos: Optional[np.ndarray] = None,
    joint_names: Optional[List[str]] = None,
    qpos: Optional[np.ndarray] = None,
    qvel: Optional[np.ndarray] = None,
    qacc: Optional[np.ndarray] = None,
    dof_pos: Optional[np.ndarray] = None,
    extra: Optional[Dict[str, Any]] = None,
    warnings: Optional[List[str]] = None,
) -> MotionData:
    """Construct and finalize a MotionData instance."""
    motion = MotionData(
        name=motion_name_from_path(path),
        fps=float(fps),
        num_frames=0,
        root_pos=root_pos,
        root_rot=root_rot,
        joint_pos=joint_pos,
        joint_names=joint_names,
        qpos=qpos,
        qvel=qvel,
        qacc=qacc,
        dof_pos=dof_pos,
        extra=extra or {},
        warnings=warnings or [],
        source_path=str(path),
        method=method,
    )
    if joint_pos is not None and joint_names:
        motion.keypoints.update({name: np.asarray(joint_pos)[:, i, :] for i, name in enumerate(joint_names[: joint_pos.shape[1]])})
    motion.ensure_keypoint_aliases()
    motion.infer_missing_derivatives()
    motion.refresh_num_frames()
    return motion

