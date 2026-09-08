from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np


STANDARD_KEYPOINTS = [
    "pelvis",
    "torso",
    "head",
    "left_hand",
    "right_hand",
    "left_knee",
    "right_knee",
    "left_foot",
    "right_foot",
]


KEYPOINT_ALIASES: Dict[str, List[str]] = {
    "pelvis": ["pelvis", "root", "hips", "hip", "Hips", "Pelvis"],
    "root": ["root", "pelvis", "hips", "Hips", "Pelvis"],
    "torso": ["torso", "chest", "spine3", "Spine2", "Chest", "torso_link", "waist_yaw_link"],
    "head": ["head", "Head", "head_link", "head_mocap"],
    "left_hand": ["left_hand", "left_wrist", "LeftHand", "LeftWrist", "left_rubber_hand", "left_wrist_yaw_link"],
    "right_hand": ["right_hand", "right_wrist", "RightHand", "RightWrist", "right_rubber_hand", "right_wrist_yaw_link"],
    "left_knee": ["left_knee", "LeftLeg", "LeftKnee", "left_knee_link"],
    "right_knee": ["right_knee", "RightLeg", "RightKnee", "right_knee_link"],
    "left_foot": ["left_foot", "left_ankle", "LeftFoot", "LeftToe", "left_toe_link", "left_ankle_roll_link"],
    "right_foot": ["right_foot", "right_ankle", "RightFoot", "RightToe", "right_toe_link", "right_ankle_roll_link"],
    "left_elbow": ["left_elbow", "LeftForeArm", "LeftElbow", "left_elbow_link"],
    "right_elbow": ["right_elbow", "RightForeArm", "RightElbow", "right_elbow_link"],
    "left_shoulder": ["left_shoulder", "LeftArm", "LeftShoulder", "left_shoulder_pitch_link"],
    "right_shoulder": ["right_shoulder", "RightArm", "RightShoulder", "right_shoulder_pitch_link"],
}


@dataclass
class MotionData:
    """Unified motion container used by loaders, alignment, FK, and metrics."""

    name: str
    path: str
    fps: float
    method: str = ""
    root_pos: Optional[np.ndarray] = None
    root_rot: Optional[np.ndarray] = None  # wxyz
    qpos: Optional[np.ndarray] = None
    dof_pos: Optional[np.ndarray] = None
    joint_names: List[str] = field(default_factory=list)
    keypoints: Dict[str, np.ndarray] = field(default_factory=dict)
    keypoint_quats: Dict[str, np.ndarray] = field(default_factory=dict)
    all_body_pos: Optional[np.ndarray] = None
    all_body_names: List[str] = field(default_factory=list)
    contacts: Dict[str, np.ndarray] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)
    raw_keys: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    unavailable: Dict[str, str] = field(default_factory=dict)

    @property
    def num_frames(self) -> int:
        for value in [
            self.root_pos,
            self.root_rot,
            self.qpos,
            self.dof_pos,
            self.all_body_pos,
            *self.keypoints.values(),
            *self.contacts.values(),
        ]:
            if value is not None:
                arr = np.asarray(value)
                if arr.ndim > 0:
                    return int(arr.shape[0])
        return 0

    @property
    def duration(self) -> float:
        if self.num_frames <= 1:
            return 0.0
        return (self.num_frames - 1) / max(float(self.fps), 1e-9)

    def copy(self) -> "MotionData":
        import copy

        return copy.deepcopy(self)

    def finalize(self) -> "MotionData":
        """Populate common aliases and derivatives that can be inferred safely."""
        if self.root_pos is None:
            self.root_pos = self.keypoints.get("root", self.keypoints.get("pelvis"))
        if self.root_pos is not None:
            self.keypoints.setdefault("root", np.asarray(self.root_pos, dtype=float))
            self.keypoints.setdefault("pelvis", np.asarray(self.root_pos, dtype=float))
        if self.root_rot is not None:
            self.keypoint_quats.setdefault("root", np.asarray(self.root_rot, dtype=float))
            self.keypoint_quats.setdefault("pelvis", np.asarray(self.root_rot, dtype=float))
        if self.dof_pos is None and self.qpos is not None and self.qpos.ndim == 2:
            self.dof_pos = self.qpos[:, 7:] if self.qpos.shape[1] > 7 else self.qpos
        if self.qpos is None and self.root_pos is not None and self.root_rot is not None and self.dof_pos is not None:
            self.qpos = np.concatenate([self.root_pos, self.root_rot, self.dof_pos], axis=1)
        self._fill_keypoint_aliases()
        return self

    def get_keypoint(self, name: str) -> Optional[np.ndarray]:
        self._fill_keypoint_aliases()
        if name in {"root", "pelvis"} and self.root_pos is not None:
            return self.root_pos
        return self.keypoints.get(name)

    def get_quat(self, name: str) -> Optional[np.ndarray]:
        if name in {"root", "pelvis"} and self.root_rot is not None:
            return self.root_rot
        return self.keypoint_quats.get(name)

    def _fill_keypoint_aliases(self) -> None:
        lower_to_name = {normalize_name(k): k for k in self.keypoints}
        if self.all_body_pos is not None and self.all_body_names:
            for idx, body_name in enumerate(self.all_body_names[: self.all_body_pos.shape[1]]):
                self.keypoints.setdefault(body_name, self.all_body_pos[:, idx, :])
                lower_to_name.setdefault(normalize_name(body_name), body_name)
        for standard, aliases in KEYPOINT_ALIASES.items():
            if standard in self.keypoints:
                continue
            for alias in aliases:
                found = lower_to_name.get(normalize_name(alias))
                if found is not None:
                    self.keypoints[standard] = self.keypoints[found]
                    break
        if self.root_pos is None:
            self.root_pos = self.keypoints.get("root", self.keypoints.get("pelvis"))


def normalize_name(name: str) -> str:
    return str(name).strip().lower().replace(" ", "_").replace("-", "_")


def as_array(value: Any, dtype=float) -> Optional[np.ndarray]:
    if value is None:
        return None
    try:
        arr = np.asarray(value, dtype=dtype)
    except Exception:
        return None
    if arr.shape == () and arr.dtype == object:
        return as_array(arr.item(), dtype=dtype)
    return arr


def first_existing(raw: Dict[str, Any], names: Iterable[str]) -> Any:
    for name in names:
        if name in raw and raw[name] is not None:
            return raw[name]
    return None


def read_names(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, np.ndarray):
        value = value.tolist()
    if not isinstance(value, (list, tuple)):
        return []
    names = []
    for item in value:
        if isinstance(item, bytes):
            names.append(item.decode("utf-8", errors="ignore"))
        else:
            names.append(str(item))
    return names


def finite_difference(value: Optional[np.ndarray], fps: float) -> Optional[np.ndarray]:
    if value is None:
        return None
    arr = np.asarray(value, dtype=float)
    if arr.shape[0] < 2:
        return np.zeros_like(arr, dtype=float)
    return np.gradient(arr, 1.0 / max(float(fps), 1e-9), axis=0)


def quat_xyzw_to_wxyz(q: np.ndarray) -> np.ndarray:
    q = np.asarray(q, dtype=float)
    if q.shape[-1] != 4:
        return q
    return q[..., [3, 0, 1, 2]]


def quat_wxyz_to_xyzw(q: np.ndarray) -> np.ndarray:
    q = np.asarray(q, dtype=float)
    if q.shape[-1] != 4:
        return q
    return q[..., [1, 2, 3, 0]]


def quat_normalize(q: np.ndarray) -> np.ndarray:
    q = np.asarray(q, dtype=float)
    norm = np.linalg.norm(q, axis=-1, keepdims=True)
    return np.divide(q, norm, out=np.zeros_like(q, dtype=float), where=norm > 1e-12)


def quat_multiply(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    aw, ax, ay, az = np.moveaxis(np.asarray(a, dtype=float), -1, 0)
    bw, bx, by, bz = np.moveaxis(np.asarray(b, dtype=float), -1, 0)
    out = np.stack(
        [
            aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
        ],
        axis=-1,
    )
    return quat_normalize(out)


def quat_rotate(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    q = quat_normalize(q)
    v = np.asarray(v, dtype=float)
    qv = q[..., 1:]
    uv = np.cross(qv, v)
    uuv = np.cross(qv, uv)
    return v + 2.0 * (q[..., :1] * uv + uuv)


def axis_angle_to_quat(rotvec: np.ndarray) -> np.ndarray:
    rotvec = np.asarray(rotvec, dtype=float)
    angle = np.linalg.norm(rotvec, axis=-1, keepdims=True)
    axis = np.divide(rotvec, angle, out=np.zeros_like(rotvec), where=angle > 1e-12)
    half = 0.5 * angle
    return quat_normalize(np.concatenate([np.cos(half), axis * np.sin(half)], axis=-1))


def quat_to_yaw(q: np.ndarray) -> np.ndarray:
    q = quat_normalize(q)
    w, x, y, z = np.moveaxis(q, -1, 0)
    return np.arctan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def quat_to_roll_pitch(q: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    q = quat_normalize(q)
    w, x, y, z = np.moveaxis(q, -1, 0)
    roll = np.arctan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y))
    pitch_arg = np.clip(2.0 * (w * y - z * x), -1.0, 1.0)
    pitch = np.arcsin(pitch_arg)
    return roll, pitch


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: List[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fieldnames})


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonify(value), ensure_ascii=False, indent=2, allow_nan=True), encoding="utf-8")


def jsonify(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): jsonify(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonify(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(jsonify(value), ensure_ascii=False)
    if isinstance(value, np.ndarray):
        return json.dumps(value.tolist(), ensure_ascii=False)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value
