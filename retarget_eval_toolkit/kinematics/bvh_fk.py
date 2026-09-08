from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


def load_bvh_as_arrays(path: str | Path) -> Tuple[np.ndarray, np.ndarray, List[str], float]:
    """Parse BVH hierarchy/motion and return global positions/quaternions.

    Returned quaternions use wxyz.
    """
    lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
    motion_idx = next((i for i, line in enumerate(lines) if line.strip().upper() == "MOTION"), None)
    if motion_idx is None:
        raise ValueError(f"BVH has no MOTION section: {path}")
    joints, root_index = _parse_hierarchy(lines[:motion_idx])
    frames, frame_time, data_start = _parse_motion_header(lines, motion_idx)
    rows = _read_motion_rows(lines[data_start:], frames, sum(len(j["channels"]) for j in joints), path)
    positions, quats = _forward_kinematics(joints, rows)
    if root_index != 0:
        order = [root_index] + [i for i in range(len(joints)) if i != root_index]
        positions = positions[:, order, :]
        quats = quats[:, order, :]
        joints = [joints[i] for i in order]
    return positions, quats, [j["name"] for j in joints], 1.0 / frame_time if frame_time > 0 else 30.0


def _parse_hierarchy(lines: List[str]) -> Tuple[List[Dict[str, Any]], int]:
    joints: List[Dict[str, Any]] = []
    stack: List[int] = []
    pending: Optional[int] = None
    in_end_site = False
    root_index = 0
    cursor = 0

    def add_joint(name: str, parent: Optional[int]) -> int:
        nonlocal root_index
        unique = _unique(name, [j["name"] for j in joints])
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


def _parse_motion_header(lines: List[str], motion_idx: int) -> Tuple[int, float, int]:
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
        raise ValueError("BVH MOTION header is incomplete.")
    return frames, frame_time, data_start


def _read_motion_rows(lines: List[str], frames: int, width: int, path: str | Path) -> np.ndarray:
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


def _forward_kinematics(joints: List[Dict[str, Any]], motion: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    t_count = motion.shape[0]
    j_count = len(joints)
    positions = np.zeros((t_count, j_count, 3), dtype=float)
    quats = np.zeros((t_count, j_count, 4), dtype=float)
    quats[..., 0] = 1.0
    for t in range(t_count):
        for j, joint in enumerate(joints):
            local_pos = np.asarray(joint["offset"], dtype=float).copy()
            local_quat = np.asarray([1.0, 0.0, 0.0, 0.0], dtype=float)
            start = int(joint["channel_start"])
            values = motion[t, start : start + len(joint["channels"])]
            for channel, value in zip(joint["channels"], values):
                channel_lower = channel.lower()
                axis = channel_lower[0]
                if channel_lower.endswith("position"):
                    local_pos["xyz".index(axis)] += value
                elif channel_lower.endswith("rotation"):
                    local_quat = quat_multiply(local_quat, axis_angle_quat(axis, np.deg2rad(value)))
            parent = joint["parent"]
            if parent is None:
                positions[t, j] = local_pos
                quats[t, j] = quat_normalize(local_quat)
            else:
                positions[t, j] = positions[t, parent] + quat_rotate(quats[t, parent], local_pos)
                quats[t, j] = quat_multiply(quats[t, parent], local_quat)
    return positions, quats


def axis_angle_quat(axis: str, angle: float) -> np.ndarray:
    """Return an axis-angle quaternion in wxyz."""
    q = np.asarray([np.cos(angle / 2.0), 0.0, 0.0, 0.0], dtype=float)
    q[1 + "xyz".index(axis)] = np.sin(angle / 2.0)
    return q


def quat_multiply(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Multiply two wxyz quaternions."""
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return quat_normalize(np.asarray([
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    ], dtype=float))


def quat_rotate(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Rotate a vector by a wxyz quaternion."""
    q = quat_normalize(q)
    qv = q[1:]
    uv = np.cross(qv, v)
    uuv = np.cross(qv, uv)
    return v + 2.0 * (q[0] * uv + uuv)


def quat_normalize(q: np.ndarray) -> np.ndarray:
    """Normalize a quaternion, falling back to identity."""
    norm = float(np.linalg.norm(q))
    if norm < 1e-12:
        return np.asarray([1.0, 0.0, 0.0, 0.0], dtype=float)
    return q / norm


def _unique(name: str, existing: List[str]) -> str:
    if name not in existing:
        return name
    i = 1
    while f"{name}_{i}" in existing:
        i += 1
    return f"{name}_{i}"

