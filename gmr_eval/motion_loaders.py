from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .io import (
    MotionData,
    as_array,
    axis_angle_to_quat,
    first_existing,
    quat_multiply,
    quat_rotate,
    quat_xyzw_to_wxyz,
    read_names,
)


ORIGINAL_EXTENSIONS = {".npz", ".npy", ".bvh"}
ROBOT_EXTENSIONS = {".pkl", ".pickle"}


def load_original_motion(path: str | Path, config: Dict[str, Any]) -> MotionData:
    """Load an original human motion and expose comparable keypoints."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".npz":
        return load_npz_motion(path, config)
    if suffix == ".npy":
        return load_npy_motion(path, config)
    if suffix == ".bvh":
        return load_bvh_motion(path, config)
    raise ValueError(f"Unsupported original motion extension for {path}. Expected one of {sorted(ORIGINAL_EXTENSIONS)}.")


def load_robot_pkl(path: str | Path, config: Dict[str, Any], method: str = "") -> MotionData:
    """Load trusted robot retargeting PKL files with flexible key detection."""
    path = Path(path)
    with path.open("rb") as f:
        obj = pickle.load(f)
    if not isinstance(obj, dict):
        raise ValueError(f"PKL must contain a dict, got {type(obj).__name__}: {path}")

    raw = {str(k): _unwrap(v) for k, v in obj.items()}
    fps = _read_fps(raw, config)
    root_pos = as_array(first_existing(raw, ["root_pos", "base_pos", "pelvis_pos", "global_translation", "trans"]), dtype=float)
    root_rot = as_array(first_existing(raw, ["root_rot", "root_quat", "base_quat", "global_rotation"]), dtype=float)
    qpos = as_array(first_existing(raw, ["qpos", "qpos_traj", "robot_qpos", "motion_qpos", "q"]), dtype=float)
    dof_pos = as_array(first_existing(raw, ["dof_pos", "joint_pos", "joint_angles", "robot_dof_pos", "dof"]), dtype=float)
    joint_names = read_names(first_existing(raw, ["dof_names", "joint_names", "joint_name", "actuated_joint_names"]))
    if not joint_names:
        joint_names = [str(name) for name in config.get("joint_names", [])]

    if qpos is not None and qpos.ndim == 2:
        if root_pos is None and qpos.shape[1] >= 3:
            root_pos = qpos[:, :3]
        if root_rot is None and qpos.shape[1] >= 7:
            root_rot = qpos[:, 3:7]
        if dof_pos is None:
            dof_pos = qpos[:, 7:] if qpos.shape[1] > 7 else qpos

    if root_rot is not None and root_rot.shape[-1] == 4:
        order = str(config.get("pkl_quaternion_order", "xyzw")).lower()
        if order == "xyzw":
            root_rot = quat_xyzw_to_wxyz(root_rot)
    if qpos is None and root_pos is not None and root_rot is not None and dof_pos is not None:
        qpos = np.concatenate([root_pos, root_rot, dof_pos], axis=1)

    keypoints, body_pos, body_names = _extract_named_positions(raw)
    contacts = _extract_contacts(raw)
    status_keys = {
        key: raw[key]
        for key in ["done", "terminated", "terminate", "fall", "fell", "success"]
        if key in raw
    }
    motion = MotionData(
        name=path.stem,
        path=str(path),
        fps=fps,
        method=method,
        root_pos=root_pos,
        root_rot=root_rot,
        qpos=qpos,
        dof_pos=dof_pos,
        joint_names=joint_names,
        keypoints=keypoints,
        all_body_pos=body_pos,
        all_body_names=body_names,
        contacts=contacts,
        raw=status_keys,
        raw_keys=sorted(raw.keys()),
    ).finalize()

    if not _has_robot_trajectory(motion):
        keys = ", ".join(motion.raw_keys)
        raise ValueError(
            "Could not identify robot trajectory fields in PKL. "
            "Expected qpos/root_pos+dof_pos/body_pos-like keys. "
            f"Actual keys: [{keys}]"
        )
    return motion


def load_npz_motion(path: Path, config: Dict[str, Any]) -> MotionData:
    """Load NPZ files from AMASS/SMPL/SMPL-X or precomputed keypoint formats."""
    data = np.load(path, allow_pickle=True)
    raw = {key: _unwrap(data[key]) for key in data.files}
    fps = _read_fps(raw, config)
    keypoints, body_pos, body_names = _extract_named_positions(raw)
    root_pos = as_array(first_existing(raw, ["root_pos", "pelvis_pos", "trans", "translation", "global_translation"]), dtype=float)
    root_rot = _extract_root_quat(raw, config)
    warnings: List[str] = []

    if not keypoints and root_pos is not None:
        keypoints = _canonical_human_keypoints(root_pos, root_rot, config)
        body_names = list(keypoints.keys())
        body_pos = np.stack([keypoints[name] for name in body_names], axis=1)
        if "poses" in raw:
            warnings.append(
                "Original NPZ has SMPL/AMASS pose parameters but no explicit 3D joints; "
                "used configurable canonical human keypoint offsets. Install/export SMPL keypoints for more exact body error."
            )
        else:
            warnings.append("Original NPZ had root trajectory but no explicit 3D joints; used canonical human keypoint offsets.")

    reference_qpos = as_array(first_existing(raw, ["reference_qpos", "mapped_joint_angle", "mapped_joint_angles", "robot_joint_angles"]), dtype=float)
    motion = MotionData(
        name=path.stem,
        path=str(path),
        fps=fps,
        method="reference",
        root_pos=root_pos,
        root_rot=root_rot,
        dof_pos=reference_qpos,
        keypoints=keypoints,
        all_body_pos=body_pos,
        all_body_names=body_names,
        raw_keys=sorted(raw.keys()),
        warnings=warnings,
    ).finalize()

    if not motion.keypoints:
        keys = ", ".join(motion.raw_keys)
        raise ValueError(f"Could not identify human keypoint/root trajectory in NPZ {path}. Actual keys: [{keys}]")
    return motion


def load_npy_motion(path: Path, config: Dict[str, Any]) -> MotionData:
    """Load NPY keypoint arrays such as HumanML3D-style T x J x 3 files."""
    arr = np.load(path, allow_pickle=True)
    fps = float(config.get("default_fps", 30.0))
    keypoints: Dict[str, np.ndarray] = {}
    body_pos: Optional[np.ndarray] = None
    body_names: List[str] = []
    root_pos: Optional[np.ndarray] = None
    warnings: List[str] = []

    if isinstance(arr, np.ndarray) and arr.dtype == object and arr.shape == ():
        obj = arr.item()
        if isinstance(obj, dict):
            return _load_dict_like_motion(path, obj, config, method="reference")

    arr = np.asarray(arr, dtype=float)
    if arr.ndim == 3 and arr.shape[-1] >= 3:
        body_pos = arr[..., :3]
        body_names = list(config.get("human_keypoint_names", []))[: arr.shape[1]]
        if not body_names:
            body_names = [f"joint_{i}" for i in range(arr.shape[1])]
        keypoints = {name: body_pos[:, i, :] for i, name in enumerate(body_names)}
        root_pos = body_pos[:, 0, :]
    elif arr.ndim == 2 and arr.shape[1] >= 3 and arr.shape[1] % 3 == 0:
        body_pos = arr.reshape(arr.shape[0], arr.shape[1] // 3, 3)
        body_names = list(config.get("human_keypoint_names", []))[: body_pos.shape[1]]
        if not body_names:
            body_names = [f"joint_{i}" for i in range(body_pos.shape[1])]
        keypoints = {name: body_pos[:, i, :] for i, name in enumerate(body_names)}
        root_pos = body_pos[:, 0, :]
    elif arr.ndim == 2 and arr.shape[1] == 3:
        root_pos = arr
        keypoints = _canonical_human_keypoints(root_pos, None, config)
        body_names = list(keypoints.keys())
        body_pos = np.stack([keypoints[name] for name in body_names], axis=1)
        warnings.append("NPY only contained root positions; used canonical human keypoint offsets.")
    else:
        raise ValueError(f"Unsupported NPY shape for {path}: {arr.shape}. Expected T x J x 3, T x (J*3), or T x 3.")

    return MotionData(
        name=path.stem,
        path=str(path),
        fps=fps,
        method="reference",
        root_pos=root_pos,
        keypoints=keypoints,
        all_body_pos=body_pos,
        all_body_names=body_names,
        warnings=warnings,
    ).finalize()


def load_bvh_motion(path: Path, config: Dict[str, Any]) -> MotionData:
    """Load BVH via a lightweight hierarchy parser and forward kinematics."""
    positions, quats, names, fps = _load_bvh_as_arrays(path)
    scale = float(config.get("bvh_unit_scale", 0.01))
    positions = positions * scale
    keypoints = {name: positions[:, i, :] for i, name in enumerate(names)}
    return MotionData(
        name=path.stem,
        path=str(path),
        fps=fps,
        method="reference",
        root_pos=positions[:, 0, :],
        root_rot=quats[:, 0, :],
        keypoints=keypoints,
        keypoint_quats={name: quats[:, i, :] for i, name in enumerate(names)},
        all_body_pos=positions,
        all_body_names=names,
    ).finalize()


def _load_dict_like_motion(path: Path, raw_obj: Dict[str, Any], config: Dict[str, Any], method: str) -> MotionData:
    raw = {str(k): _unwrap(v) for k, v in raw_obj.items()}
    fps = _read_fps(raw, config)
    keypoints, body_pos, body_names = _extract_named_positions(raw)
    root_pos = as_array(first_existing(raw, ["root_pos", "pelvis_pos", "trans", "translation"]), dtype=float)
    root_rot = _extract_root_quat(raw, config)
    return MotionData(
        name=path.stem,
        path=str(path),
        fps=fps,
        method=method,
        root_pos=root_pos,
        root_rot=root_rot,
        keypoints=keypoints,
        all_body_pos=body_pos,
        all_body_names=body_names,
        raw_keys=sorted(raw.keys()),
    ).finalize()


def _read_fps(raw: Dict[str, Any], config: Dict[str, Any]) -> float:
    fps_value = first_existing(raw, ["fps", "frame_rate", "mocap_framerate", "motion_fps", "framerate"])
    if fps_value is not None:
        arr = np.asarray(fps_value).reshape(-1)
        if arr.size and float(arr[0]) > 0:
            return float(arr[0])
    dt_value = first_existing(raw, ["dt", "frame_time", "timestep"])
    if dt_value is not None:
        arr = np.asarray(dt_value).reshape(-1)
        if arr.size and float(arr[0]) > 0:
            return 1.0 / float(arr[0])
    return float(config.get("default_fps", 30.0))


def _extract_root_quat(raw: Dict[str, Any], config: Dict[str, Any]) -> Optional[np.ndarray]:
    root_rot = as_array(first_existing(raw, ["root_rot", "root_quat", "global_orient_quat", "base_quat"]), dtype=float)
    if root_rot is not None and root_rot.shape[-1] == 4:
        order = str(config.get("human_quaternion_order", "wxyz")).lower()
        if order == "xyzw":
            root_rot = quat_xyzw_to_wxyz(root_rot)
        return root_rot
    poses = as_array(first_existing(raw, ["poses", "pose", "body_pose"]), dtype=float)
    if poses is not None and poses.ndim == 2 and poses.shape[1] >= 3:
        return axis_angle_to_quat(poses[:, :3])
    return None


def _extract_named_positions(raw: Dict[str, Any]) -> Tuple[Dict[str, np.ndarray], Optional[np.ndarray], List[str]]:
    for key in [
        "keypoints",
        "keypoint_pos",
        "joint_pos",
        "joint_positions",
        "joints",
        "joints3d",
        "body_pos",
        "body_positions",
        "global_positions",
        "positions",
        "local_body_pos",
    ]:
        if key not in raw or raw[key] is None:
            continue
        value = raw[key]
        if isinstance(value, dict):
            names = list(map(str, value.keys()))
            arrays = [as_array(value[name], dtype=float) for name in names]
            if arrays and all(arr is not None and arr.ndim == 2 and arr.shape[-1] >= 3 for arr in arrays):
                body_pos = np.stack([arr[:, :3] for arr in arrays if arr is not None], axis=1)
                return {name: body_pos[:, i, :] for i, name in enumerate(names)}, body_pos, names
        arr = as_array(value, dtype=float)
        if arr is not None and arr.ndim == 3 and arr.shape[-1] >= 3:
            body_pos = arr[..., :3]
            names = read_names(first_existing(raw, ["keypoint_names", "joint_names", "body_names", "link_body_list", "names"]))
            if not names:
                names = [f"body_{i}" for i in range(body_pos.shape[1])]
            names = names[: body_pos.shape[1]]
            return {name: body_pos[:, i, :] for i, name in enumerate(names)}, body_pos, names
    return {}, None, []


def _extract_contacts(raw: Dict[str, Any]) -> Dict[str, np.ndarray]:
    contacts: Dict[str, np.ndarray] = {}
    contact_obj = first_existing(raw, ["contacts", "contact", "foot_contacts", "contact_states"])
    if isinstance(contact_obj, dict):
        for key, value in contact_obj.items():
            arr = as_array(value, dtype=float)
            if arr is not None and arr.ndim >= 1:
                contacts[str(key)] = arr.astype(bool)
    elif contact_obj is not None:
        arr = as_array(contact_obj, dtype=float)
        if arr is not None and arr.ndim == 2 and arr.shape[1] >= 2:
            contacts["left_foot"] = arr[:, 0].astype(bool)
            contacts["right_foot"] = arr[:, 1].astype(bool)
    return contacts


def _canonical_human_keypoints(root_pos: np.ndarray, root_rot: Optional[np.ndarray], config: Dict[str, Any]) -> Dict[str, np.ndarray]:
    offsets = config.get("human_canonical_offsets_m", {})
    if not offsets:
        offsets = {
            "pelvis": [0.0, 0.0, 0.0],
            "torso": [0.0, 0.0, 0.45],
            "head": [0.0, 0.0, 0.85],
            "left_shoulder": [0.0, 0.18, 0.55],
            "right_shoulder": [0.0, -0.18, 0.55],
            "left_elbow": [0.0, 0.42, 0.35],
            "right_elbow": [0.0, -0.42, 0.35],
            "left_hand": [0.0, 0.62, 0.18],
            "right_hand": [0.0, -0.62, 0.18],
            "left_knee": [0.0, 0.10, -0.45],
            "right_knee": [0.0, -0.10, -0.45],
            "left_foot": [0.08, 0.10, -0.90],
            "right_foot": [0.08, -0.10, -0.90],
        }
    root = np.asarray(root_pos, dtype=float)
    if root_rot is None:
        root_rot = np.zeros((len(root), 4), dtype=float)
        root_rot[:, 0] = 1.0
    out: Dict[str, np.ndarray] = {}
    for name, offset in offsets.items():
        off = np.asarray(offset, dtype=float)
        rotated = quat_rotate(root_rot, np.broadcast_to(off, root.shape))
        out[str(name)] = root + rotated
    return out


def _has_robot_trajectory(motion: MotionData) -> bool:
    return any(
        value is not None
        for value in [motion.qpos, motion.dof_pos, motion.root_pos, motion.all_body_pos]
    ) or bool(motion.keypoints)


def _unwrap(value: Any) -> Any:
    if isinstance(value, np.ndarray) and value.dtype == object and value.shape == ():
        return value.item()
    return value


def _load_bvh_as_arrays(path: Path) -> Tuple[np.ndarray, np.ndarray, List[str], float]:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    motion_idx = next((i for i, line in enumerate(lines) if line.strip().upper() == "MOTION"), None)
    if motion_idx is None:
        raise ValueError(f"BVH has no MOTION section: {path}")
    joints, root_index = _parse_bvh_hierarchy(lines[:motion_idx])
    frames, frame_time, data_start = _parse_bvh_motion_header(lines, motion_idx)
    width = sum(len(j["channels"]) for j in joints)
    rows = _read_bvh_rows(lines[data_start:], frames, width, path)
    positions, quats = _bvh_forward_kinematics(joints, rows)
    if root_index != 0:
        order = [root_index] + [i for i in range(len(joints)) if i != root_index]
        positions = positions[:, order, :]
        quats = quats[:, order, :]
        joints = [joints[i] for i in order]
    fps = 1.0 / frame_time if frame_time > 0 else 30.0
    return positions, quats, [j["name"] for j in joints], fps


def _parse_bvh_hierarchy(lines: List[str]) -> Tuple[List[Dict[str, Any]], int]:
    joints: List[Dict[str, Any]] = []
    stack: List[int] = []
    pending: Optional[int] = None
    in_end_site = False
    root_index = 0
    cursor = 0

    def add_joint(name: str, parent: Optional[int]) -> int:
        nonlocal root_index
        existing = {j["name"] for j in joints}
        unique = name
        suffix = 1
        while unique in existing:
            unique = f"{name}_{suffix}"
            suffix += 1
        idx = len(joints)
        joints.append({"name": unique, "parent": parent, "offset": np.zeros(3), "channels": [], "channel_start": 0})
        if parent is None:
            root_index = idx
        return idx

    for raw in lines:
        line = raw.strip()
        upper = line.upper()
        if not line or upper == "HIERARCHY":
            continue
        if upper.startswith("END SITE"):
            in_end_site = True
            pending = None
            continue
        if upper.startswith("ROOT ") or upper.startswith("JOINT "):
            in_end_site = False
            pending = add_joint(line.split(maxsplit=1)[1], stack[-1] if stack else None)
            continue
        if line.startswith("{"):
            if pending is not None:
                stack.append(pending)
                pending = None
            continue
        if line.startswith("}"):
            if in_end_site:
                in_end_site = False
            elif stack:
                stack.pop()
            continue
        if in_end_site or not stack:
            continue
        if upper.startswith("OFFSET"):
            joints[stack[-1]]["offset"] = np.asarray([float(v) for v in line.split()[1:4]], dtype=float)
        elif upper.startswith("CHANNELS"):
            parts = line.split()
            count = int(parts[1])
            channels = parts[2 : 2 + count]
            joints[stack[-1]]["channels"] = channels
            joints[stack[-1]]["channel_start"] = cursor
            cursor += count
    return joints, root_index


def _parse_bvh_motion_header(lines: List[str], motion_idx: int) -> Tuple[int, float, int]:
    frames = None
    frame_time = None
    data_start = None
    for i in range(motion_idx + 1, len(lines)):
        stripped = lines[i].strip()
        lower = stripped.lower()
        if lower.startswith("frames:"):
            frames = int(stripped.split(":", 1)[1].strip())
        elif lower.startswith("frame time:"):
            frame_time = float(stripped.split(":", 1)[1].strip())
            data_start = i + 1
            break
    if frames is None or frame_time is None or data_start is None:
        raise ValueError(f"BVH MOTION header is incomplete.")
    return frames, frame_time, data_start


def _read_bvh_rows(lines: List[str], frames: int, width: int, path: Path) -> np.ndarray:
    rows = []
    for line in lines:
        if not line.strip():
            continue
        values = [float(v) for v in line.split()]
        if len(values) < width:
            raise ValueError(f"BVH row has {len(values)} values but expected {width}: {path}")
        rows.append(values[:width])
        if len(rows) == frames:
            break
    if len(rows) != frames:
        raise ValueError(f"BVH expected {frames} frames but found {len(rows)} rows: {path}")
    return np.asarray(rows, dtype=float)


def _bvh_forward_kinematics(joints: List[Dict[str, Any]], motion: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    frame_count = motion.shape[0]
    joint_count = len(joints)
    positions = np.zeros((frame_count, joint_count, 3), dtype=float)
    quats = np.zeros((frame_count, joint_count, 4), dtype=float)
    quats[..., 0] = 1.0
    for frame in range(frame_count):
        for idx, joint in enumerate(joints):
            local_pos = np.asarray(joint["offset"], dtype=float).copy()
            local_quat = np.asarray([1.0, 0.0, 0.0, 0.0], dtype=float)
            start = int(joint["channel_start"])
            values = motion[frame, start : start + len(joint["channels"])]
            for channel, value in zip(joint["channels"], values):
                channel_lower = channel.lower()
                axis = channel_lower[0]
                if channel_lower.endswith("position"):
                    local_pos["xyz".index(axis)] += value
                elif channel_lower.endswith("rotation"):
                    local_quat = quat_multiply(local_quat, _axis_angle_quat(axis, np.deg2rad(value)))
            parent = joint["parent"]
            if parent is None:
                positions[frame, idx] = local_pos
                quats[frame, idx] = local_quat
            else:
                positions[frame, idx] = positions[frame, parent] + quat_rotate(quats[frame, parent], local_pos)
                quats[frame, idx] = quat_multiply(quats[frame, parent], local_quat)
    return positions, quats


def _axis_angle_quat(axis: str, angle: float) -> np.ndarray:
    q = np.asarray([np.cos(angle / 2.0), 0.0, 0.0, 0.0], dtype=float)
    q[1 + "xyz".index(axis)] = np.sin(angle / 2.0)
    return q
