"""File readers that turn logs and reference motion files into CanonicalMotion.

The module deliberately has no MuJoCo/Isaac runtime dependency.  Simulator
adapters use its generic readers and add simulator-specific FK or limits.
"""

from __future__ import annotations

import csv
import pickle
import re
from pathlib import Path
from typing import Any, Optional

import numpy as np

from canonical_motion import CanonicalMotion
from utils import normalize_quaternions, xyzw_to_wxyz


DEFAULT_ALIASES = {
    "fps": ("fps", "frame_rate", "mocap_frame_rate", "mocap_framerate"),
    "time": ("time", "timestamps", "timestamp"),
    "root_pos": ("root_pos", "root_position", "root_translation", "root_trans"),
    "root_quat": ("root_quat", "root_rot", "root_rotation", "root_orientation"),
    "root_lin_vel": ("root_lin_vel", "root_linear_velocity", "root_vel"),
    "root_ang_vel": ("root_ang_vel", "root_angular_velocity", "root_angvel"),
    # `joint_positions` commonly means human 3-D landmarks, so it is not
    # guessed as a robot DOF array. Map it explicitly in YAML if needed.
    "dof_pos": ("dof_pos", "joint_pos", "joint_angles", "qpos"),
    "dof_vel": ("dof_vel", "joint_vel", "joint_velocities", "qvel"),
    "dof_acc": ("dof_acc", "joint_acc", "joint_accelerations"),
    "dof_names": ("dof_names", "joint_names", "joint_name"),
    "dof_limits_lower": ("dof_limits_lower", "joint_limits_lower", "joint_lower"),
    "dof_limits_upper": ("dof_limits_upper", "joint_limits_upper", "joint_upper"),
    "body_positions": ("body_positions", "body_pos", "link_positions"),
    "body_quats": ("body_quats", "body_rotations", "body_quat"),
    "body_lin_vels": ("body_lin_vels", "body_linear_velocities"),
    "body_ang_vels": ("body_ang_vels", "body_angular_velocities"),
    "end_effector_positions": ("end_effector_positions", "ee_positions"),
    "end_effector_quats": ("end_effector_quats", "ee_quats"),
    "foot_contacts": ("foot_contacts", "contacts", "foot_contact"),
    "contact_forces": ("contact_forces", "contact_force"),
    "torques": ("torques", "torque", "joint_torques", "ctrl"),
    "torque_limits_lower": ("torque_limits_lower", "torque_lower", "effort_limits_lower"),
    "torque_limits_upper": ("torque_limits_upper", "torque_upper", "effort_limits_upper"),
    "actions": ("actions", "action", "controls", "ctrl"),
    "target_dof_pos": ("target_dof_pos", "target_joint_pos", "target_qpos"),
    "target_dof_vel": ("target_dof_vel", "target_joint_vel", "target_qvel"),
    "actual_dof_pos": ("actual_dof_pos", "actual_joint_pos", "actual_qpos"),
    "actual_dof_vel": ("actual_dof_vel", "actual_joint_vel", "actual_qvel"),
    "target_root_pos": ("target_root_pos",),
    "actual_root_pos": ("actual_root_pos",),
    "target_body_positions": ("target_body_positions",),
    "actual_body_positions": ("actual_body_positions",),
    "target_end_effector_positions": ("target_end_effector_positions", "target_ee_positions"),
    "actual_end_effector_positions": ("actual_end_effector_positions", "actual_ee_positions"),
    "joint_positions_ref": ("joint_positions_ref", "joint_positions", "joints", "positions"),
    "joint_rotations_ref": ("joint_rotations_ref", "joint_rotations", "joint_quats"),
    "joint_names_ref": ("joint_names_ref", "joint_names", "joint_name", "names"),
}


def read_motion_file(path: Path) -> Any:
    """Read npy/npz/pkl/csv into a mapping or array; no format assumptions yet."""
    path = Path(path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Motion file was not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".npz":
        with np.load(path, allow_pickle=True) as archive:
            return {key: _unwrap_object(archive[key]) for key in archive.files}
    if suffix == ".npy":
        return _unwrap_object(np.load(path, allow_pickle=True))
    if suffix in {".pkl", ".pickle"}:
        with path.open("rb") as handle:
            return _unwrap_object(pickle.load(handle))
    if suffix == ".csv":
        return _read_csv(path)
    if suffix == ".bvh":
        return _load_bvh(path)
    raise ValueError(
        f"Unsupported motion extension '{suffix}'. Supported: .npy, .npz, .pkl, .csv, .bvh. "
        "Convert AMASS/SMPL/HumanML3D to canonical .npz first (see 操作手册_CN.md)."
    )


def load_canonical_motion(path: Path, config: Optional[dict[str, Any]] = None, *, name: Optional[str] = None, simulator: Optional[str] = None) -> CanonicalMotion:
    payload = read_motion_file(path)
    if isinstance(payload, CanonicalMotion):
        result = payload.copy(name=name or payload.name)
        result.simulator = simulator or result.simulator
        return result
    if not isinstance(payload, dict):
        array = np.asarray(payload)
        input_config = (config or {}).get("input", {})
        kind = str(input_config.get("array_type", "auto"))
        is_position_array = array.ndim == 3 and array.shape[-1] == 3
        if kind == "joint_positions_ref" or (kind == "auto" and is_position_array):
            payload = {"joint_positions_ref": array}
            names = input_config.get("joint_names_ref")
            if names:
                payload["joint_names_ref"] = names
        else:
            payload = {"dof_pos": array}
    return canonical_from_payload(payload, config=config, name=name or path.stem, simulator=simulator, source_type=path.suffix.lower().lstrip("."))


def canonical_from_payload(payload: dict[str, Any], config: Optional[dict[str, Any]] = None, *, name: str = "motion", simulator: Optional[str] = None, source_type: str = "memory") -> CanonicalMotion:
    """Map common log keys to canonical fields, retaining unknown keys in metadata."""
    config = config or {}
    expected = config.get("expected_keys", config)
    values: dict[str, Any] = {}
    used_keys: set[str] = set()
    for field, aliases in DEFAULT_ALIASES.items():
        value, key = _lookup(payload, expected.get(field), aliases)
        if key is not None:
            values[field] = _unwrap_object(value)
            used_keys.add(key)

    # Isaac / Isaac Lab compact state arrays.
    root_state, root_key = _lookup(payload, expected.get("root_state"), ("root_state",))
    if root_key is not None:
        used_keys.add(root_key)
        root_state = np.asarray(root_state, dtype=float)
        if root_state.ndim == 2 and root_state.shape[1] >= 13:
            values.setdefault("root_pos", root_state[:, :3])
            values.setdefault("root_quat", root_state[:, 3:7])
            values.setdefault("root_lin_vel", root_state[:, 7:10])
            values.setdefault("root_ang_vel", root_state[:, 10:13])

    body_names, body_names_key = _lookup(payload, expected.get("body_names"), ("body_names", "link_body_list"))
    rigid_state, rigid_key = _lookup(payload, expected.get("rigid_body_state"), ("rigid_body_state", "rigid_body_states"))
    if rigid_key is not None:
        used_keys.add(rigid_key)
        if body_names_key is not None:
            used_keys.add(body_names_key)
        _ingest_rigid_body_state(values, rigid_state, body_names)

    # GMR output stores `local_body_pos`; it is intentionally not treated as
    # world-space body positions.  MuJoCo FK can fill those when a model exists.
    if "metadata" in payload and isinstance(_unwrap_object(payload["metadata"]), dict):
        used_keys.add("metadata")
        metadata = dict(_unwrap_object(payload["metadata"]))
    else:
        metadata = {}
    metadata.update({"input_keys": sorted(str(key) for key in payload.keys()), "unused_input_keys": sorted(str(key) for key in payload.keys() if key not in used_keys)})

    quaternion_order = str(config.get("quaternion_order", "xyzw")).lower()
    if quaternion_order not in {"xyzw", "wxyz"}:
        raise ValueError("quaternion_order must be 'xyzw' or 'wxyz'.")
    for field in ("root_quat", "joint_rotations_ref"):
        if values.get(field) is not None:
            quat = np.asarray(values[field], dtype=float)
            values[field] = normalize_quaternions(xyzw_to_wxyz(quat) if quaternion_order == "xyzw" else quat)
    for field in ("body_quats", "end_effector_quats"):
        if isinstance(values.get(field), dict):
            values[field] = {
                key: normalize_quaternions(xyzw_to_wxyz(array) if quaternion_order == "xyzw" else array)
                for key, array in values[field].items()
            }

    for name_field in ("dof_names", "joint_names_ref"):
        if values.get(name_field) is not None:
            values[name_field] = _string_list(values[name_field])

    fps = _to_scalar(values.pop("fps", config.get("fps", 30.0)), default=30.0)
    if values.get("time") is not None:
        values["time"] = np.asarray(values["time"], dtype=float).reshape(-1)
        if values["time"].shape[0] > 1 and "fps" not in payload:
            elapsed = values["time"][-1] - values["time"][0]
            if elapsed > 0:
                fps = (values["time"].shape[0] - 1) / elapsed

    # Isaac's contact_forces is normally [T, B, 3] beside body_names. Convert
    # it to the same name->array shape as offline files before validation.
    if values.get("contact_forces") is not None and not isinstance(values["contact_forces"], dict):
        force_array = np.asarray(values["contact_forces"])
        if body_names is not None and force_array.ndim >= 2:
            names = _string_list(body_names)
            if force_array.shape[1] == len(names):
                values["contact_forces"] = {body: force_array[:, index] for index, body in enumerate(names)}
            else:
                raise ValueError("contact_forces body dimension does not match body_names.")
        else:
            raise ValueError("Bare contact_forces needs matching body_names; otherwise save a {body: force} dictionary.")
    for key in ("body_positions", "body_quats", "body_lin_vels", "body_ang_vels", "end_effector_positions", "end_effector_quats", "target_body_positions", "actual_body_positions", "target_end_effector_positions", "actual_end_effector_positions", "foot_contacts", "contact_forces"):
        if values.get(key) is not None:
            values[key] = _array_dict(values[key])
    values["metadata"] = metadata
    return CanonicalMotion(name=name, source_type=source_type, simulator=simulator, fps=fps, **values)


def _lookup(payload: dict[str, Any], requested: Any, aliases: tuple[str, ...]) -> tuple[Any, Optional[str]]:
    candidates: list[str] = []
    if isinstance(requested, str) and requested:
        candidates.append(requested)
    candidates.extend(alias for alias in aliases if alias not in candidates)
    for key in candidates:
        if key in payload:
            return payload[key], key
    return None, None


def _unwrap_object(value: Any) -> Any:
    if isinstance(value, np.ndarray) and value.dtype == object and value.shape == ():
        return value.item()
    return value


def _string_list(value: Any) -> list[str]:
    array = np.asarray(value, dtype=object).reshape(-1)
    result = []
    for item in array:
        if isinstance(item, bytes):
            result.append(item.decode("utf-8"))
        else:
            result.append(str(item))
    return result


def _array_dict(value: Any) -> dict[str, np.ndarray]:
    value = _unwrap_object(value)
    if isinstance(value, dict):
        return {str(key): np.asarray(_unwrap_object(item)) for key, item in value.items()}
    raise ValueError("Named body/contact data must be stored as a dict, not a bare array. Add body_names or use rigid_body_state.")


def _to_scalar(value: Any, default: float) -> float:
    try:
        return float(np.asarray(value).reshape(-1)[0])
    except (TypeError, ValueError, IndexError):
        return default


def _ingest_rigid_body_state(values: dict[str, Any], raw_state: Any, raw_names: Any) -> None:
    state = np.asarray(raw_state, dtype=float)
    if state.ndim != 3 or state.shape[-1] < 7:
        raise ValueError("rigid_body_state must have shape [T, B, >=7] (pos, quat, optional velocities).")
    names = _string_list(raw_names) if raw_names is not None else [f"body_{index}" for index in range(state.shape[1])]
    if len(names) != state.shape[1]:
        raise ValueError(f"body_names has {len(names)} names but rigid_body_state has {state.shape[1]} bodies.")
    values.setdefault("body_positions", {name: state[:, index, :3] for index, name in enumerate(names)})
    values.setdefault("body_quats", {name: state[:, index, 3:7] for index, name in enumerate(names)})
    if state.shape[-1] >= 13:
        values.setdefault("body_lin_vels", {name: state[:, index, 7:10] for index, name in enumerate(names)})
        values.setdefault("body_ang_vels", {name: state[:, index, 10:13] for index, name in enumerate(names)})


def _read_csv(path: Path) -> dict[str, Any]:
    """Read wide logs, including root_pos_x and dof_pos_0 style columns."""
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - documented dependency
        raise ImportError("CSV input requires pandas. Install it with pip install pandas.") from exc
    frame = pd.read_csv(path)
    payload: dict[str, Any] = {}
    columns = list(frame.columns)
    for base, dimension in (("root_pos", 3), ("root_quat", 4), ("root_lin_vel", 3), ("root_ang_vel", 3)):
        array = _columns_to_array(frame, columns, base, dimension)
        if array is not None:
            payload[base] = array
    for base in ("dof_pos", "dof_vel", "torques", "actions", "target_dof_pos", "target_dof_vel", "actual_dof_pos", "actual_dof_vel"):
        array = _columns_to_array(frame, columns, base, None)
        if array is not None:
            payload[base] = array
    if "time" in frame:
        payload["time"] = frame["time"].to_numpy()
    if "fps" in frame and len(frame):
        payload["fps"] = float(frame["fps"].iloc[0])
    if not payload:
        numeric = frame.select_dtypes(include=["number"])
        if numeric.empty:
            raise ValueError("CSV contains no recognized columns and no numeric fallback columns.")
        payload["dof_pos"] = numeric.to_numpy()
    return payload


def _columns_to_array(frame: Any, columns: list[str], base: str, width: Optional[int]) -> Optional[np.ndarray]:
    matches = []
    for column in columns:
        match = re.fullmatch(rf"{re.escape(base)}[_\.](x|y|z|w|\d+)", str(column), flags=re.IGNORECASE)
        if match:
            token = match.group(1).lower()
            order = {"x": 0, "y": 1, "z": 2, "w": 3}.get(token, int(token) if token.isdigit() else 999)
            matches.append((order, column))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0])
    if width is not None and len(matches) != width:
        raise ValueError(f"CSV needs {width} {base}_* columns, found {len(matches)}.")
    return frame[[column for _, column in matches]].to_numpy(dtype=float)


def _load_bvh(path: Path) -> dict[str, Any]:
    """Minimal BVH reader: global joint positions and frame rate, no external package."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    try:
        motion_line = next(index for index, line in enumerate(lines) if line.strip().upper() == "MOTION")
    except StopIteration as exc:
        raise ValueError(f"{path}: BVH does not contain a MOTION section.") from exc
    nodes: list[dict[str, Any]] = []
    stack: list[Optional[int]] = []
    current: Optional[int] = None
    channel_count = 0
    index = 0
    while index < motion_line:
        tokens = lines[index].strip().split()
        if not tokens:
            index += 1
            continue
        kind = tokens[0].upper()
        if kind in {"ROOT", "JOINT"} and len(tokens) >= 2:
            parent = next((entry for entry in reversed(stack) if entry is not None), None)
            current = len(nodes)
            nodes.append({"name": tokens[1], "parent": parent, "offset": np.zeros(3), "channels": [], "start": channel_count})
        elif kind == "END":
            current = None
        elif kind == "{":
            stack.append(current)
        elif kind == "}":
            if stack:
                stack.pop()
            current = next((entry for entry in reversed(stack) if entry is not None), None)
        elif kind == "OFFSET" and current is not None and len(tokens) >= 4:
            nodes[current]["offset"] = np.asarray(tokens[1:4], dtype=float)
        elif kind == "CHANNELS" and current is not None and len(tokens) >= 2:
            count = int(tokens[1])
            nodes[current]["channels"] = tokens[2:2 + count]
            nodes[current]["start"] = channel_count
            channel_count += count
        index += 1
    frame_count = int(lines[motion_line + 1].split(":", 1)[1].strip())
    frame_time = float(lines[motion_line + 2].split(":", 1)[1].strip())
    raw = [[float(value) for value in line.split()] for line in lines[motion_line + 3:] if line.strip()]
    values = np.asarray(raw[:frame_count], dtype=float)
    if values.shape != (frame_count, channel_count):
        raise ValueError(f"{path}: expected [{frame_count}, {channel_count}] BVH values, got {values.shape}.")
    global_pos = np.zeros((frame_count, len(nodes), 3), dtype=float)
    for frame_index, frame_values in enumerate(values):
        rotations: list[np.ndarray] = []
        for node in nodes:
            local_pos = node["offset"].copy()
            local_rot = np.eye(3)
            for offset, channel in enumerate(node["channels"]):
                value = frame_values[node["start"] + offset]
                if channel.lower().endswith("position"):
                    local_pos["XYZ".index(channel[0].upper())] += value
                elif channel.lower().endswith("rotation"):
                    local_rot = local_rot @ _axis_rotation(channel[0].upper(), np.deg2rad(value))
            parent = node["parent"]
            if parent is None:
                global_pos[frame_index, len(rotations)] = local_pos
                rotations.append(local_rot)
            else:
                global_pos[frame_index, len(rotations)] = global_pos[frame_index, parent] + rotations[parent] @ local_pos
                rotations.append(rotations[parent] @ local_rot)
    return {"fps": 1.0 / frame_time, "joint_positions_ref": global_pos, "joint_names_ref": [node["name"] for node in nodes]}


def _axis_rotation(axis: str, angle: float) -> np.ndarray:
    cos, sin = np.cos(angle), np.sin(angle)
    if axis == "X":
        return np.array([[1, 0, 0], [0, cos, -sin], [0, sin, cos]])
    if axis == "Y":
        return np.array([[cos, 0, sin], [0, 1, 0], [-sin, 0, cos]])
    return np.array([[cos, -sin, 0], [sin, cos, 0], [0, 0, 1]])
