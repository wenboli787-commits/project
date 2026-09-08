from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .quaternion import normalize_quat_wxyz


@dataclass(frozen=True)
class RobotMotionReference:
    path: Path
    fps: float
    root_pos: np.ndarray
    root_quat_wxyz: np.ndarray
    dof_pos: np.ndarray
    qpos: np.ndarray
    dof_vel: np.ndarray
    metadata: dict[str, Any]

    @property
    def frame_count(self) -> int:
        return int(self.qpos.shape[0])

    @property
    def dof_count(self) -> int:
        return int(self.dof_pos.shape[1])

    @property
    def qpos_dim(self) -> int:
        return int(self.qpos.shape[1])

    def frame(self, index: int) -> np.ndarray:
        return self.qpos[int(index)]

    def slice(self, start_frame: int = 0, max_frames: int | None = None) -> "RobotMotionReference":
        start_frame = max(0, int(start_frame))
        stop_frame = self.frame_count if max_frames is None else start_frame + int(max_frames)
        stop_frame = min(self.frame_count, stop_frame)
        if start_frame >= stop_frame:
            raise ValueError(
                f"Invalid motion slice: start_frame={start_frame}, max_frames={max_frames}, "
                f"frame_count={self.frame_count}"
            )
        root_pos = self.root_pos[start_frame:stop_frame].copy()
        root_quat = self.root_quat_wxyz[start_frame:stop_frame].copy()
        dof_pos = self.dof_pos[start_frame:stop_frame].copy()
        return build_motion_reference(
            path=self.path,
            fps=self.fps,
            root_pos=root_pos,
            root_quat_wxyz=root_quat,
            dof_pos=dof_pos,
            metadata=dict(self.metadata),
        )


def _finite_difference(values: np.ndarray, fps: float) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    if values.shape[0] <= 1:
        return np.zeros_like(values)
    dt = 1.0 / float(fps)
    edge_order = 2 if values.shape[0] > 2 else 1
    return np.gradient(values, dt, axis=0, edge_order=edge_order)


def build_motion_reference(
    path: Path,
    fps: float,
    root_pos: np.ndarray,
    root_quat_wxyz: np.ndarray,
    dof_pos: np.ndarray,
    metadata: dict[str, Any] | None = None,
) -> RobotMotionReference:
    root_pos = np.asarray(root_pos, dtype=np.float64)
    root_quat_wxyz = normalize_quat_wxyz(np.asarray(root_quat_wxyz, dtype=np.float64))
    dof_pos = np.asarray(dof_pos, dtype=np.float64)

    if root_pos.ndim != 2 or root_pos.shape[1] != 3:
        raise ValueError(f"root_pos must have shape (T, 3), got {root_pos.shape}")
    if root_quat_wxyz.ndim != 2 or root_quat_wxyz.shape[1] != 4:
        raise ValueError(f"root_quat_wxyz must have shape (T, 4), got {root_quat_wxyz.shape}")
    if dof_pos.ndim != 2:
        raise ValueError(f"dof_pos must have shape (T, D), got {dof_pos.shape}")
    if not (root_pos.shape[0] == root_quat_wxyz.shape[0] == dof_pos.shape[0]):
        raise ValueError(
            "root_pos, root_quat_wxyz and dof_pos must have the same frame count: "
            f"{root_pos.shape[0]}, {root_quat_wxyz.shape[0]}, {dof_pos.shape[0]}"
        )
    if root_pos.shape[0] < 2:
        raise ValueError("Motion reference must contain at least 2 frames.")
    if fps <= 0:
        raise ValueError(f"fps must be positive, got {fps}")

    qpos = np.concatenate([root_pos, root_quat_wxyz, dof_pos], axis=1)
    dof_vel = _finite_difference(dof_pos, fps)
    return RobotMotionReference(
        path=Path(path),
        fps=float(fps),
        root_pos=root_pos,
        root_quat_wxyz=root_quat_wxyz,
        dof_pos=dof_pos,
        qpos=qpos,
        dof_vel=dof_vel,
        metadata=metadata or {},
    )


def load_robot_motion_reference(
    motion_path: str | Path,
    quat_format: str = "xyzw",
    start_frame: int = 0,
    max_frames: int | None = None,
) -> RobotMotionReference:
    """Load a GMR pkl motion reference.

    GMR saves root_rot as xyzw. MuJoCo qpos expects wxyz.
    """

    path = Path(motion_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Motion file not found: {path}")
    with path.open("rb") as f:
        motion_data = pickle.load(f)

    required = ["fps", "root_pos", "root_rot", "dof_pos"]
    missing = [key for key in required if key not in motion_data]
    if missing:
        raise KeyError(f"Motion file is missing keys: {missing}")

    root_rot = np.asarray(motion_data["root_rot"], dtype=np.float64)
    if quat_format == "xyzw":
        root_quat_wxyz = root_rot[:, [3, 0, 1, 2]]
    elif quat_format == "wxyz":
        root_quat_wxyz = root_rot
    else:
        raise ValueError("quat_format must be 'xyzw' or 'wxyz'")

    reference = build_motion_reference(
        path=path,
        fps=float(motion_data["fps"]),
        root_pos=np.asarray(motion_data["root_pos"], dtype=np.float64),
        root_quat_wxyz=root_quat_wxyz,
        dof_pos=np.asarray(motion_data["dof_pos"], dtype=np.float64),
        metadata=dict(motion_data.get("metadata") or {}),
    )
    return reference.slice(start_frame=start_frame, max_frames=max_frames)
