from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .common_motion import (
    as_array,
    first_existing,
    make_motion,
    quat_xyzw_to_wxyz,
    read_names,
    unwrap_np_value,
)


def load_pkl(path: str | Path, config: Optional[Dict[str, Any]] = None, *, method: Optional[str] = None) -> Any:
    """Load trusted retargeting PKL files.

    Python pickle can execute code while loading. This loader is intended for
    locally generated, trusted retargeting results only.
    """
    config = config or {}
    path = Path(path)
    with open(path, "rb") as f:
        obj = pickle.load(f)
    if not isinstance(obj, dict):
        raise ValueError(f"Only dict-like PKL files are supported: {path}")
    raw = {str(k): unwrap_np_value(v) for k, v in obj.items()}

    fps = float(np.asarray(first_existing(raw, ["fps", "frame_rate", "motion_fps"]) or config.get("target_fps", 30.0)).reshape(-1)[0])
    qpos = as_array(first_existing(raw, ["qpos", "qpos_traj", "q", "robot_qpos"]), dtype=float)
    qvel = as_array(first_existing(raw, ["qvel", "qvel_traj", "robot_qvel"]), dtype=float)
    qacc = as_array(first_existing(raw, ["qacc", "qacc_traj", "robot_qacc"]), dtype=float)
    root_pos = as_array(first_existing(raw, ["root_pos", "base_pos", "global_translation", "pelvis_pos"]), dtype=float)
    root_rot_raw = first_existing(raw, ["root_quat", "root_rot", "base_quat", "global_rotation"])
    root_rot = as_array(root_rot_raw, dtype=float)
    dof_pos = as_array(first_existing(raw, ["dof_pos", "joint_angles", "joint_pos"]), dtype=float)
    root_rot_from_qpos = False

    if qpos is not None and qpos.ndim == 2:
        root_pos = root_pos if root_pos is not None else qpos[:, :3]
        if root_rot is None or root_rot.shape[-1] != 4:
            root_rot = qpos[:, 3:7]
            root_rot_from_qpos = True
        dof_pos = dof_pos if dof_pos is not None else qpos[:, 7:]

    if root_rot is not None and root_rot.shape[-1] == 4:
        order = "wxyz" if root_rot_from_qpos else str(config.get("pkl_quaternion_order", "xyzw")).lower()
        if "root_quat" in raw and "root_rot" not in raw:
            order = str(config.get("root_quat_order", "wxyz")).lower()
        if order == "xyzw":
            root_rot = quat_xyzw_to_wxyz(root_rot)

    joint_pos, joint_names = _extract_named_positions(raw)
    motion = make_motion(
        path,
        fps,
        method=method,
        root_pos=root_pos,
        root_rot=root_rot,
        joint_pos=joint_pos,
        joint_names=joint_names,
        qpos=qpos,
        qvel=qvel,
        qacc=qacc,
        dof_pos=dof_pos,
        extra={
            "raw_keys": sorted(raw.keys()),
            "metadata": raw.get("metadata", {}),
            "torque": first_existing(raw, ["torque", "torques", "qfrc", "actuator_force", "ctrl", "action", "actions"]),
        },
    )
    motion.dof_names = read_names(first_existing(raw, ["dof_names", "joint_names", "joint_name"]))
    return motion


def _extract_named_positions(raw: Dict[str, Any]) -> Tuple[Optional[np.ndarray], Optional[List[str]]]:
    for key in ["body_pos", "body_positions", "keypoints", "joint_positions", "global_translation"]:
        if key not in raw:
            continue
        value = raw[key]
        if isinstance(value, dict):
            names = list(map(str, value.keys()))
            arrays = [np.asarray(value[name], dtype=float) for name in names]
            if arrays and all(a.ndim == 2 and a.shape[-1] == 3 for a in arrays):
                return np.stack(arrays, axis=1), names
        arr = as_array(value, dtype=float)
        if arr is not None and arr.ndim == 3 and arr.shape[-1] >= 3:
            names = read_names(first_existing(raw, ["body_names", "link_body_list", "joint_names", "keypoint_names"]))
            if names is None:
                names = [f"body_{i}" for i in range(arr.shape[1])]
            return arr[..., :3], names[: arr.shape[1]]
    return None, None
