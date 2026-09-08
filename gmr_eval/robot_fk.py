from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .io import MotionData


def enrich_robot_with_fk(motion: MotionData, robot_xml: str | Path | None, config: Dict[str, Any]) -> MotionData:
    """Use MuJoCo forward kinematics to add robot body trajectories and contacts."""
    if not robot_xml:
        motion.warnings.append("MuJoCo XML was not provided; FK, contact, and self-collision metrics are unavailable.")
        return motion
    xml_path = Path(robot_xml).expanduser()
    if not xml_path.exists():
        motion.warnings.append(f"MuJoCo XML not found: {xml_path}; FK metrics are unavailable.")
        return motion
    try:
        import mujoco  # type: ignore
    except Exception as exc:
        motion.warnings.append(f"mujoco package is not installed or failed to import: {exc}; FK metrics are unavailable.")
        return motion

    if motion.qpos is None:
        motion.finalize()
    if motion.qpos is None:
        motion.warnings.append("Robot PKL has no qpos or root_pos/root_rot/dof_pos fields; MuJoCo FK skipped.")
        return motion

    try:
        model = mujoco.MjModel.from_xml_path(str(xml_path))
        data = mujoco.MjData(model)
    except Exception as exc:
        motion.warnings.append(f"MuJoCo model load failed for {xml_path}: {exc}; FK skipped.")
        return motion

    body_names = _body_names(model, mujoco)
    site_names = _site_names(model, mujoco)
    joint_names, lower, upper = _joint_limits(model, mujoco)
    if joint_names and not motion.joint_names:
        motion.joint_names = joint_names[: motion.dof_pos.shape[1] if motion.dof_pos is not None else len(joint_names)]
    motion.raw["joint_limit_lower"] = lower
    motion.raw["joint_limit_upper"] = upper

    qpos = np.asarray(motion.qpos, dtype=float)
    body_pos = np.empty((qpos.shape[0], model.nbody, 3), dtype=float)
    body_quat = np.empty((qpos.shape[0], model.nbody, 4), dtype=float)
    keypoint_map = _robot_keypoint_map(config)
    keypoint_buffers: Dict[str, List[np.ndarray]] = {name: [] for name in keypoint_map}
    quat_buffers: Dict[str, List[np.ndarray]] = {name: [] for name in keypoint_map}
    contacts = {"left_foot": np.zeros(qpos.shape[0], dtype=bool), "right_foot": np.zeros(qpos.shape[0], dtype=bool)}
    self_collision_counter: Counter[Tuple[str, str]] = Counter()
    self_collision_frames = np.zeros(qpos.shape[0], dtype=bool)

    for frame_idx, frame_qpos in enumerate(qpos):
        q = np.asarray(model.qpos0, dtype=float).copy()
        width = min(len(q), len(frame_qpos))
        q[:width] = frame_qpos[:width]
        data.qpos[:] = q
        mujoco.mj_forward(model, data)

        body_pos[frame_idx] = np.asarray(data.xpos, dtype=float)
        for body_id in range(model.nbody):
            body_quat[frame_idx, body_id] = _mat_to_wxyz(np.asarray(data.xmat[body_id], dtype=float).reshape(3, 3))
        for keypoint, candidates in keypoint_map.items():
            pos, quat = _lookup_body_or_site(candidates, body_names, site_names, data, model, mujoco)
            keypoint_buffers[keypoint].append(pos if pos is not None else np.full(3, np.nan))
            quat_buffers[keypoint].append(quat if quat is not None else np.full(4, np.nan))

        frame_pairs, frame_foot_contact = _contacts_for_frame(data, model, mujoco, body_names, config)
        contacts["left_foot"][frame_idx] = frame_foot_contact.get("left_foot", False)
        contacts["right_foot"][frame_idx] = frame_foot_contact.get("right_foot", False)
        if frame_pairs:
            self_collision_frames[frame_idx] = True
            self_collision_counter.update(frame_pairs)

    motion.all_body_pos = body_pos
    motion.all_body_names = [name for name, _ in sorted(body_names.items(), key=lambda item: item[1])]
    motion.raw["body_quat"] = body_quat
    for keypoint, frames in keypoint_buffers.items():
        arr = np.asarray(frames, dtype=float)
        if np.isfinite(arr).any():
            motion.keypoints[keypoint] = arr
    for keypoint, frames in quat_buffers.items():
        arr = np.asarray(frames, dtype=float)
        if np.isfinite(arr).any():
            motion.keypoint_quats[keypoint] = arr
    motion.contacts.update(contacts)
    motion.raw["self_collision_count"] = int(np.sum(self_collision_frames))
    motion.raw["self_collision_frame_ratio"] = float(np.mean(self_collision_frames)) if len(self_collision_frames) else np.nan
    motion.raw["self_collision_pairs"] = [
        {"body_a": a, "body_b": b, "count": int(count)}
        for (a, b), count in self_collision_counter.most_common()
    ]
    missing = [
        keypoint
        for keypoint, frames in keypoint_buffers.items()
        if not np.isfinite(np.asarray(frames, dtype=float)).any()
    ]
    if missing:
        motion.warnings.append(f"MuJoCo FK could not resolve robot bodies/sites for: {', '.join(missing)}")
    return motion.finalize()


def _robot_keypoint_map(config: Dict[str, Any]) -> Dict[str, List[str]]:
    robot = config.get("robot_bodies", {})
    return {
        "pelvis": _as_list(robot.get("pelvis", robot.get("root", ["pelvis"]))),
        "root": _as_list(robot.get("root", ["pelvis"])),
        "torso": _as_list(robot.get("torso", ["torso_link", "waist_yaw_link"])),
        "head": _as_list(robot.get("head", ["head_mocap", "head_link", "head"])),
        "left_hand": _as_list(robot.get("left_hand", ["left_rubber_hand", "left_wrist_yaw_link", "left_hand_palm_link"])),
        "right_hand": _as_list(robot.get("right_hand", ["right_rubber_hand", "right_wrist_yaw_link", "right_hand_palm_link"])),
        "left_knee": _as_list(robot.get("left_knee", ["left_knee_link"])),
        "right_knee": _as_list(robot.get("right_knee", ["right_knee_link"])),
        "left_foot": _as_list(robot.get("left_foot", ["left_foot", "left_toe_link", "left_ankle_roll_link"])),
        "right_foot": _as_list(robot.get("right_foot", ["right_foot", "right_toe_link", "right_ankle_roll_link"])),
        "left_elbow": _as_list(robot.get("left_elbow", ["left_elbow_link"])),
        "right_elbow": _as_list(robot.get("right_elbow", ["right_elbow_link"])),
        "left_shoulder": _as_list(robot.get("left_shoulder", ["left_shoulder_pitch_link"])),
        "right_shoulder": _as_list(robot.get("right_shoulder", ["right_shoulder_pitch_link"])),
    }


def _contacts_for_frame(data: Any, model: Any, mujoco: Any, body_names: Dict[str, int], config: Dict[str, Any]) -> Tuple[List[Tuple[str, str]], Dict[str, bool]]:
    id_to_body = {idx: name for name, idx in body_names.items()}
    floor_names = {str(name).lower() for name in config.get("floor_geom_names", ["floor", "ground", "plane"])}
    left_foot_bodies = {name.lower() for name in _as_list(config.get("robot_bodies", {}).get("left_foot", ["left_toe_link", "left_ankle_roll_link"]))}
    right_foot_bodies = {name.lower() for name in _as_list(config.get("robot_bodies", {}).get("right_foot", ["right_toe_link", "right_ankle_roll_link"]))}
    frame_pairs: List[Tuple[str, str]] = []
    foot_contact = {"left_foot": False, "right_foot": False}

    for contact_idx in range(int(data.ncon)):
        contact = data.contact[contact_idx]
        geom1, geom2 = int(contact.geom1), int(contact.geom2)
        if geom1 < 0 or geom2 < 0:
            continue
        body1 = int(model.geom_bodyid[geom1])
        body2 = int(model.geom_bodyid[geom2])
        name1 = id_to_body.get(body1, f"body_{body1}")
        name2 = id_to_body.get(body2, f"body_{body2}")
        geom_name1 = (mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, geom1) or "").lower()
        geom_name2 = (mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, geom2) or "").lower()

        names_lower = {name1.lower(), name2.lower()}
        geoms_lower = {geom_name1, geom_name2}
        if geoms_lower & floor_names or "world" in names_lower:
            if names_lower & left_foot_bodies:
                foot_contact["left_foot"] = True
            if names_lower & right_foot_bodies:
                foot_contact["right_foot"] = True
            continue

        if body1 == 0 or body2 == 0 or body1 == body2:
            continue
        if _are_adjacent_bodies(model, body1, body2):
            continue
        pair = tuple(sorted([name1, name2]))
        frame_pairs.append(pair)
    return frame_pairs, foot_contact


def _are_adjacent_bodies(model: Any, body_a: int, body_b: int) -> bool:
    return int(model.body_parentid[body_a]) == body_b or int(model.body_parentid[body_b]) == body_a


def _body_names(model: Any, mujoco: Any) -> Dict[str, int]:
    names = {}
    for body_id in range(model.nbody):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, body_id)
        if name:
            names[name] = body_id
    return names


def _site_names(model: Any, mujoco: Any) -> Dict[str, int]:
    names = {}
    for site_id in range(model.nsite):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_SITE, site_id)
        if name:
            names[name] = site_id
    return names


def _joint_limits(model: Any, mujoco: Any) -> Tuple[List[str], np.ndarray, np.ndarray]:
    names: List[str] = []
    lower: List[float] = []
    upper: List[float] = []
    free_type = int(getattr(mujoco.mjtJoint, "mjJNT_FREE", 0))
    for joint_id in range(model.njnt):
        if int(model.jnt_type[joint_id]) == free_type:
            continue
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, joint_id) or f"joint_{joint_id}"
        rng = np.asarray(model.jnt_range[joint_id], dtype=float)
        if int(model.jnt_limited[joint_id]):
            lo, hi = float(rng[0]), float(rng[1])
        else:
            lo, hi = -np.inf, np.inf
        names.append(name)
        lower.append(lo)
        upper.append(hi)
    return names, np.asarray(lower, dtype=float), np.asarray(upper, dtype=float)


def _lookup_body_or_site(
    candidates: List[str],
    body_names: Dict[str, int],
    site_names: Dict[str, int],
    data: Any,
    model: Any,
    mujoco: Any,
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    for name in candidates:
        if name in site_names:
            site_id = site_names[name]
            mat = np.asarray(data.site_xmat[site_id], dtype=float).reshape(3, 3)
            return np.asarray(data.site_xpos[site_id], dtype=float).copy(), _mat_to_wxyz(mat)
        if name in body_names:
            body_id = body_names[name]
            mat = np.asarray(data.xmat[body_id], dtype=float).reshape(3, 3)
            return np.asarray(data.xpos[body_id], dtype=float).copy(), _mat_to_wxyz(mat)
        try:
            site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, name)
            if site_id >= 0:
                mat = np.asarray(data.site_xmat[site_id], dtype=float).reshape(3, 3)
                return np.asarray(data.site_xpos[site_id], dtype=float).copy(), _mat_to_wxyz(mat)
        except Exception:
            pass
        try:
            body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
            if body_id >= 0:
                mat = np.asarray(data.xmat[body_id], dtype=float).reshape(3, 3)
                return np.asarray(data.xpos[body_id], dtype=float).copy(), _mat_to_wxyz(mat)
        except Exception:
            pass
    return None, None


def _mat_to_wxyz(matrix: np.ndarray) -> np.ndarray:
    m = np.asarray(matrix, dtype=float)
    tr = float(np.trace(m))
    if tr > 0.0:
        s = np.sqrt(tr + 1.0) * 2.0
        return np.asarray([0.25 * s, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s])
    idx = int(np.argmax(np.diag(m)))
    if idx == 0:
        s = np.sqrt(max(1.0 + m[0, 0] - m[1, 1] - m[2, 2], 1e-12)) * 2.0
        return np.asarray([(m[2, 1] - m[1, 2]) / s, 0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s])
    if idx == 1:
        s = np.sqrt(max(1.0 + m[1, 1] - m[0, 0] - m[2, 2], 1e-12)) * 2.0
        return np.asarray([(m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s])
    s = np.sqrt(max(1.0 + m[2, 2] - m[0, 0] - m[1, 1], 1e-12)) * 2.0
    return np.asarray([(m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s])


def _as_list(value: Any) -> List[str]:
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return [str(value)]
