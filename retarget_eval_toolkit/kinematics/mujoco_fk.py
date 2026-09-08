from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from loaders.common_motion import MotionData, quat_wxyz_to_xyzw


def enrich_with_mujoco_fk(motion: MotionData, robot_xml: str | Path, config: Dict[str, Any]) -> MotionData:
    """Fill robot keypoints and joint limits from MuJoCo, when available."""
    if not robot_xml:
        motion.warnings.append("MuJoCo XML was not provided; robot FK and XML joint limits are unavailable.")
        return motion
    try:
        import mujoco
    except Exception as exc:
        motion.warnings.append(f"MuJoCo import failed; FK skipped: {exc}")
        return motion

    robot_xml = Path(robot_xml)
    if not robot_xml.exists():
        motion.warnings.append(f"MuJoCo XML not found; FK skipped: {robot_xml}")
        return motion
    if motion.qpos is None:
        motion.infer_missing_derivatives()
    if motion.qpos is None:
        motion.warnings.append("Robot motion has no qpos/root+dof data; MuJoCo FK skipped.")
        return motion

    try:
        model = mujoco.MjModel.from_xml_path(str(robot_xml))
        data = mujoco.MjData(model)
    except Exception as exc:
        motion.warnings.append(f"MuJoCo model load failed; FK skipped: {exc}")
        return motion

    _fill_joint_limits(motion, model, mujoco)
    body_names = _body_names(model, mujoco)
    keypoint_map = _keypoint_body_map(config)
    positions: Dict[str, List[np.ndarray]] = {name: [] for name in keypoint_map}
    quats: Dict[str, List[np.ndarray]] = {name: [] for name in keypoint_map}
    self_collision_frames = 0

    for frame_qpos in np.asarray(motion.qpos, dtype=float):
        q = np.asarray(model.qpos0, dtype=float).copy()
        q[: min(len(q), len(frame_qpos))] = frame_qpos[: min(len(q), len(frame_qpos))]
        data.qpos[:] = q
        mujoco.mj_forward(model, data)
        for standard, candidates in keypoint_map.items():
            body_id = _first_body_id(candidates, body_names, model, mujoco)
            if body_id is None:
                positions[standard].append(np.full(3, np.nan))
                quats[standard].append(np.asarray([np.nan, np.nan, np.nan, np.nan]))
            else:
                positions[standard].append(np.asarray(data.xpos[body_id], dtype=float).copy())
                quats[standard].append(_mat_to_wxyz(np.asarray(data.xmat[body_id]).reshape(3, 3)))
        if _has_self_collision(data, model, mujoco):
            self_collision_frames += 1

    for standard, items in positions.items():
        arr = np.asarray(items, dtype=float)
        if np.isfinite(arr).any():
            motion.keypoints[standard] = arr
    for standard, items in quats.items():
        arr = np.asarray(items, dtype=float)
        if np.isfinite(arr).any():
            motion.keypoint_quats[standard] = arr
    motion.extra["self_collision_count"] = int(self_collision_frames)
    motion.extra["self_collision_rate"] = float(self_collision_frames / max(motion.num_frames, 1))
    motion.ensure_keypoint_aliases()
    return motion


def _fill_joint_limits(motion: MotionData, model: Any, mujoco: Any) -> None:
    lower = []
    upper = []
    names = []
    free_type = int(getattr(mujoco.mjtJoint, "mjJNT_FREE", 0))
    for joint_id in range(model.njnt):
        if int(model.jnt_type[joint_id]) == free_type:
            continue
        qadr = int(model.jnt_qposadr[joint_id])
        width = 1
        if qadr >= model.nq:
            continue
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, joint_id) or f"joint_{joint_id}"
        rng = np.asarray(model.jnt_range[joint_id], dtype=float)
        if int(model.jnt_limited[joint_id]):
            lo, hi = float(rng[0]), float(rng[1])
        else:
            lo, hi = -np.inf, np.inf
        for local in range(width):
            lower.append(lo)
            upper.append(hi)
            names.append(name if width == 1 else f"{name}_{local}")
    if lower:
        motion.joint_limits_lower = np.asarray(lower, dtype=float)
        motion.joint_limits_upper = np.asarray(upper, dtype=float)
        motion.dof_names = motion.dof_names or names
        if motion.dof_pos is not None and len(lower) != motion.dof_pos.shape[1]:
            n = min(len(lower), motion.dof_pos.shape[1])
            motion.joint_limits_lower = motion.joint_limits_lower[:n]
            motion.joint_limits_upper = motion.joint_limits_upper[:n]
            motion.dof_names = motion.dof_names[:n] if motion.dof_names else None
            motion.warnings.append("MuJoCo joint-limit count did not match dof_pos width; limits were truncated.")


def _body_names(model: Any, mujoco: Any) -> Dict[str, int]:
    names = {}
    for body_id in range(model.nbody):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, body_id)
        if name:
            names[name] = body_id
    return names


def _keypoint_body_map(config: Dict[str, Any]) -> Dict[str, List[str]]:
    robot = config.get("robot", {})
    return {
        "pelvis": _as_list(robot.get("pelvis_body", robot.get("root_body", "pelvis"))),
        "root": _as_list(robot.get("root_body", "pelvis")),
        "torso": _as_list(robot.get("torso_body", "torso_link")),
        "head": _as_list(robot.get("head_body", ["head_link", "head"])),
        "left_hand": _as_list(robot.get("left_hand_body", ["left_rubber_hand", "left_wrist_yaw_link", "left_hand"])),
        "right_hand": _as_list(robot.get("right_hand_body", ["right_rubber_hand", "right_wrist_yaw_link", "right_hand"])),
        "left_foot": _as_list(robot.get("left_foot_body", ["left_toe_link", "left_ankle_roll_link", "left_foot"])),
        "right_foot": _as_list(robot.get("right_foot_body", ["right_toe_link", "right_ankle_roll_link", "right_foot"])),
        "left_knee": _as_list(robot.get("left_knee_body", ["left_knee_link", "left_knee"])),
        "right_knee": _as_list(robot.get("right_knee_body", ["right_knee_link", "right_knee"])),
        "left_elbow": _as_list(robot.get("left_elbow_body", ["left_elbow_link", "left_elbow"])),
        "right_elbow": _as_list(robot.get("right_elbow_body", ["right_elbow_link", "right_elbow"])),
    }


def _as_list(value: Any) -> List[str]:
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [str(value)]


def _first_body_id(candidates: List[str], names: Dict[str, int], model: Any, mujoco: Any) -> Optional[int]:
    for name in candidates:
        if name in names:
            return names[name]
        try:
            body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
        except Exception:
            body_id = -1
        if body_id >= 0:
            return int(body_id)
    return None


def _mat_to_wxyz(matrix: np.ndarray) -> np.ndarray:
    try:
        from scipy.spatial.transform import Rotation as R

        return np.asarray(R.from_matrix(matrix).as_quat()[[3, 0, 1, 2]], dtype=float)
    except Exception:
        tr = float(np.trace(matrix))
        if tr > 0:
            s = np.sqrt(tr + 1.0) * 2.0
            return np.asarray([0.25 * s, (matrix[2, 1] - matrix[1, 2]) / s, (matrix[0, 2] - matrix[2, 0]) / s, (matrix[1, 0] - matrix[0, 1]) / s])
        return np.asarray([1.0, 0.0, 0.0, 0.0])


def _has_self_collision(data: Any, model: Any, mujoco: Any) -> bool:
    for i in range(int(data.ncon)):
        contact = data.contact[i]
        geom1 = int(contact.geom1)
        geom2 = int(contact.geom2)
        if geom1 < 0 or geom2 < 0:
            continue
        body1 = int(model.geom_bodyid[geom1])
        body2 = int(model.geom_bodyid[geom2])
        if body1 != 0 and body2 != 0 and body1 != body2:
            return True
    return False

