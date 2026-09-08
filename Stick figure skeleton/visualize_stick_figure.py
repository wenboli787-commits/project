#!/usr/bin/env python3
"""Visualize BVH, NPV, NPY, NPZ, and AMASS/SMPL pose files as a 3D stick figure.

The tool is intentionally lightweight and works without MuJoCo.  BVH files are
converted to global joint positions through forward kinematics.  NPV/NPY/NPZ files
are expected to contain joint positions, or a raw BVH channel matrix together
with BVH hierarchy metadata or a template BVH file.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np


NUMPY_EXTENSIONS = {".npv", ".npy", ".npz"}

ARRAY_KEYS = (
    "positions",
    "joint_positions",
    "global_positions",
    "global_joint_positions",
    "keypoints3d",
    "keypoints_3d",
    "keypoints",
    "joints",
    "body_pos",
    "global_body_pos",
    "local_body_pos",
    "poses",
    "pose",
    "motion",
    "data",
    "arr_0",
)

PARENT_KEYS = (
    "parents",
    "parent",
    "skeleton_parents",
    "joint_parents",
    "kinematic_tree",
)

JOINT_NAME_KEYS = (
    "joint_names",
    "joints_names",
    "names",
    "body_names",
    "link_body_list",
)

PRESET_PARENTS: dict[str, list[int]] = {
    # LAFAN1 order:
    # Hips, LUpLeg, LLeg, LFoot, LToe, RUpLeg, RLeg, RFoot, RToe,
    # Spine, Spine1, Spine2, Neck, Head, LShoulder, LArm, LForeArm,
    # LHand, RShoulder, RArm, RForeArm, RHand
    "lafan22": [
        -1,
        0,
        1,
        2,
        3,
        0,
        5,
        6,
        7,
        0,
        9,
        10,
        11,
        12,
        11,
        14,
        15,
        16,
        11,
        18,
        19,
        20,
    ],
    # Common SMPL/SMPL-X 24-joint body order.
    "smpl24": [
        -1,
        0,
        0,
        0,
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        9,
        9,
        12,
        13,
        14,
        16,
        17,
        18,
        19,
        20,
        21,
    ],
    # COCO 17 keypoints: nose, eyes, ears, shoulders, elbows, wrists,
    # hips, knees, ankles.
    "coco17": [
        -1,
        0,
        0,
        1,
        2,
        0,
        5,
        5,
        6,
        7,
        8,
        5,
        6,
        11,
        12,
        13,
        14,
    ],
}

SMPL24_JOINT_NAMES = [
    "pelvis",
    "left_hip",
    "right_hip",
    "spine1",
    "left_knee",
    "right_knee",
    "spine2",
    "left_ankle",
    "right_ankle",
    "spine3",
    "left_foot",
    "right_foot",
    "neck",
    "left_collar",
    "right_collar",
    "head",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hand",
    "right_hand",
]

# Lightweight approximate SMPL rest-pose offsets in meters.  This preview path
# is for quick stick-figure inspection of AMASS/SMPL parameter NPZ files; it is
# not a replacement for the full SMPL body model.
SMPL24_REST_OFFSETS = np.asarray(
    [
        [0.0, 0.0, 0.0],
        [0.09, 0.0, -0.09],
        [-0.09, 0.0, -0.09],
        [0.0, 0.0, 0.10],
        [0.0, 0.0, -0.42],
        [0.0, 0.0, -0.42],
        [0.0, 0.0, 0.12],
        [0.0, 0.0, -0.43],
        [0.0, 0.0, -0.43],
        [0.0, 0.0, 0.12],
        [0.0, 0.12, -0.05],
        [0.0, 0.12, -0.05],
        [0.0, 0.0, 0.16],
        [0.07, 0.0, 0.05],
        [-0.07, 0.0, 0.05],
        [0.0, 0.0, 0.14],
        [0.16, 0.0, 0.0],
        [-0.16, 0.0, 0.0],
        [0.27, 0.0, 0.0],
        [-0.27, 0.0, 0.0],
        [0.25, 0.0, 0.0],
        [-0.25, 0.0, 0.0],
        [0.08, 0.0, 0.0],
        [-0.08, 0.0, 0.0],
    ],
    dtype=np.float64,
)


@dataclass
class BvhJoint:
    name: str
    parent: int
    offset: np.ndarray
    channels: list[str]
    channel_start: int


@dataclass
class BvhSkeleton:
    joints: list[BvhJoint]

    @property
    def names(self) -> list[str]:
        return [joint.name for joint in self.joints]

    @property
    def parents(self) -> list[int]:
        return [joint.parent for joint in self.joints]

    @property
    def channel_count(self) -> int:
        return sum(len(joint.channels) for joint in self.joints)


@dataclass
class MotionSequence:
    positions: np.ndarray
    parents: list[int]
    joint_names: list[str]
    fps: float
    source_kind: str
    source_path: Path


def axis_rotation(axis: str, degrees: float) -> np.ndarray:
    angle = np.deg2rad(degrees)
    c = float(np.cos(angle))
    s = float(np.sin(angle))
    axis = axis.upper()
    if axis == "X":
        return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])
    if axis == "Y":
        return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])
    if axis == "Z":
        return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
    raise ValueError(f"Unsupported rotation axis: {axis}")


def axis_angle_to_matrix(rotation_vector: np.ndarray) -> np.ndarray:
    vector = np.asarray(rotation_vector, dtype=np.float64)
    angle = float(np.linalg.norm(vector))
    if angle < 1e-12:
        return np.eye(3, dtype=np.float64)

    axis = vector / angle
    x, y, z = axis
    c = float(np.cos(angle))
    s = float(np.sin(angle))
    one_c = 1.0 - c
    return np.asarray(
        [
            [c + x * x * one_c, x * y * one_c - z * s, x * z * one_c + y * s],
            [y * x * one_c + z * s, c + y * y * one_c, y * z * one_c - x * s],
            [z * x * one_c - y * s, z * y * one_c + x * s, c + z * z * one_c],
        ],
        dtype=np.float64,
    )


def parse_bvh_hierarchy(lines: Iterable[str]) -> BvhSkeleton:
    joints: list[BvhJoint] = []
    stack: list[int] = []
    pending_joint: int | None = None
    channel_cursor = 0
    end_site_counts: dict[str, int] = {}

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.upper() == "HIERARCHY":
            continue

        if line.startswith("ROOT ") or line.startswith("JOINT "):
            name = line.split(maxsplit=1)[1].strip()
            parent = stack[-1] if stack else -1
            joints.append(
                BvhJoint(
                    name=name,
                    parent=parent,
                    offset=np.zeros(3, dtype=np.float64),
                    channels=[],
                    channel_start=channel_cursor,
                )
            )
            pending_joint = len(joints) - 1
            continue

        if line.upper().startswith("END SITE"):
            if not stack:
                raise ValueError("Found BVH End Site without a parent joint.")
            parent = stack[-1]
            base_name = f"{joints[parent].name}_end"
            count = end_site_counts.get(base_name, 0)
            end_site_counts[base_name] = count + 1
            name = base_name if count == 0 else f"{base_name}_{count + 1}"
            joints.append(
                BvhJoint(
                    name=name,
                    parent=parent,
                    offset=np.zeros(3, dtype=np.float64),
                    channels=[],
                    channel_start=channel_cursor,
                )
            )
            pending_joint = len(joints) - 1
            continue

        if line == "{":
            if pending_joint is not None:
                stack.append(pending_joint)
                pending_joint = None
            continue

        if line == "}":
            if stack:
                stack.pop()
            continue

        if line.upper().startswith("OFFSET"):
            if not stack:
                raise ValueError(f"Found BVH OFFSET outside a joint block: {line}")
            parts = line.split()
            if len(parts) != 4:
                raise ValueError(f"Invalid BVH OFFSET line: {line}")
            joints[stack[-1]].offset = np.asarray(parts[1:4], dtype=np.float64)
            continue

        if line.upper().startswith("CHANNELS"):
            if not stack:
                raise ValueError(f"Found BVH CHANNELS outside a joint block: {line}")
            parts = line.split()
            if len(parts) < 3:
                raise ValueError(f"Invalid BVH CHANNELS line: {line}")
            channel_count = int(parts[1])
            channels = parts[2 : 2 + channel_count]
            if len(channels) != channel_count:
                raise ValueError(f"Invalid BVH CHANNELS count: {line}")
            joint = joints[stack[-1]]
            joint.channels = channels
            joint.channel_start = channel_cursor
            channel_cursor += channel_count
            continue

    if not joints:
        raise ValueError("No BVH joints were found in the hierarchy.")
    return BvhSkeleton(joints=joints)


def read_bvh(path: Path) -> tuple[BvhSkeleton, np.ndarray, float]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    motion_index = None
    for index, line in enumerate(lines):
        if line.strip().upper() == "MOTION":
            motion_index = index
            break
    if motion_index is None:
        raise ValueError(f"{path} is not a BVH file: missing MOTION section.")

    skeleton = parse_bvh_hierarchy(lines[:motion_index])
    motion_lines = lines[motion_index + 1 :]
    frames_line_index = None
    frame_time_line_index = None
    frame_count = None
    frame_time = None

    for index, line in enumerate(motion_lines):
        frames_match = re.match(r"\s*Frames\s*:\s*(\d+)\s*$", line)
        if frames_match:
            frames_line_index = index
            frame_count = int(frames_match.group(1))
            continue
        time_match = re.match(r"\s*Frame\s+Time\s*:\s*([0-9eE+\-.]+)\s*$", line)
        if time_match:
            frame_time_line_index = index
            frame_time = float(time_match.group(1))
            break

    if frames_line_index is None or frame_time_line_index is None:
        raise ValueError(f"{path} is missing BVH Frames or Frame Time metadata.")
    if frame_count is None or frame_time is None:
        raise ValueError(f"{path} has invalid BVH motion metadata.")

    data_text = " ".join(motion_lines[frame_time_line_index + 1 :])
    values = np.fromstring(data_text, sep=" ", dtype=np.float64)
    expected = frame_count * skeleton.channel_count
    if values.size != expected:
        raise ValueError(
            f"{path} motion size mismatch: got {values.size} values, expected "
            f"{expected} ({frame_count} frames x {skeleton.channel_count} channels)."
        )

    return skeleton, values.reshape(frame_count, skeleton.channel_count), frame_time


def bvh_to_positions(
    skeleton: BvhSkeleton,
    motion: np.ndarray,
    unit_scale: float,
    position_mode: str,
) -> np.ndarray:
    motion = np.asarray(motion, dtype=np.float64)
    if motion.ndim != 2:
        raise ValueError(f"BVH motion must be a 2D array, got shape {motion.shape}.")
    if motion.shape[1] != skeleton.channel_count:
        raise ValueError(
            f"BVH motion has {motion.shape[1]} channels, but the skeleton expects "
            f"{skeleton.channel_count} channels."
        )

    frame_count = motion.shape[0]
    joint_count = len(skeleton.joints)
    positions = np.zeros((frame_count, joint_count, 3), dtype=np.float64)

    for frame in range(frame_count):
        global_rotations = [np.eye(3, dtype=np.float64) for _ in skeleton.joints]
        for joint_index, joint in enumerate(skeleton.joints):
            local_position = joint.offset.astype(np.float64) * unit_scale
            local_rotation = np.eye(3, dtype=np.float64)

            for channel_offset, channel in enumerate(joint.channels):
                value = motion[frame, joint.channel_start + channel_offset]
                lower_channel = channel.lower()
                axis = channel[0].upper()
                if lower_channel.endswith("position"):
                    if position_mode == "add":
                        local_position["XYZ".index(axis)] += value * unit_scale
                    else:
                        local_position["XYZ".index(axis)] = value * unit_scale
                elif lower_channel.endswith("rotation"):
                    local_rotation = local_rotation @ axis_rotation(axis, value)

            parent = joint.parent
            if parent < 0:
                positions[frame, joint_index] = local_position
                global_rotations[joint_index] = local_rotation
            else:
                positions[frame, joint_index] = (
                    positions[frame, parent] + global_rotations[parent] @ local_position
                )
                global_rotations[joint_index] = global_rotations[parent] @ local_rotation

    return positions


def load_numpy_payload(path: Path) -> Any:
    data = np.load(path, allow_pickle=True)
    if isinstance(data, np.lib.npyio.NpzFile):
        with data:
            return {key: data[key] for key in data.files}
    if isinstance(data, np.ndarray) and data.shape == ():
        try:
            return data.item()
        except ValueError:
            return data
    return data


def scalar_to_string(value: Any) -> str:
    array = np.asarray(value)
    if array.shape == ():
        item = array.item()
        if isinstance(item, bytes):
            return item.decode("utf-8", errors="replace")
        return str(item)
    if array.dtype.kind in {"U", "S", "O"}:
        return "\n".join(str(item.decode("utf-8", "replace") if isinstance(item, bytes) else item) for item in array.ravel())
    return str(value)


def is_numeric_array(value: Any) -> bool:
    try:
        array = np.asarray(value)
    except Exception:
        return False
    return np.issubdtype(array.dtype, np.number)


def is_motion_like_array(value: Any) -> bool:
    if not is_numeric_array(value):
        return False
    array = np.asarray(value)
    return array.ndim >= 2 and array.size > 0


def select_array(payload: Any, key: str | None) -> tuple[np.ndarray, str]:
    if isinstance(payload, np.ndarray):
        return np.asarray(payload), "array"

    if not isinstance(payload, dict):
        raise ValueError(
            f"Expected an ndarray or dict-like payload, got {type(payload).__name__}."
        )

    if key:
        if key not in payload:
            raise KeyError(f"Key '{key}' was not found. Available keys: {sorted(payload)}")
        return np.asarray(payload[key]), key

    for candidate in ARRAY_KEYS:
        if candidate in payload and is_motion_like_array(payload[candidate]):
            return np.asarray(payload[candidate]), candidate

    numeric_keys = [name for name, value in payload.items() if is_motion_like_array(value)]
    if len(numeric_keys) == 1:
        return np.asarray(payload[numeric_keys[0]]), numeric_keys[0]

    raise ValueError(
        "Could not choose an array automatically. "
        f"Available numeric motion-like keys: {numeric_keys}. Use --key KEY."
    )


def normalize_positions(array: np.ndarray, layout: str) -> np.ndarray:
    array = np.asarray(array)
    if not np.issubdtype(array.dtype, np.number):
        raise ValueError(f"The selected array must be numeric, got dtype {array.dtype}.")
    array = np.asarray(array, dtype=np.float64)
    array = np.squeeze(array)

    if layout == "tjc":
        if array.ndim != 3 or array.shape[2] < 3:
            raise ValueError("--array-layout tjc expects shape [frames, joints, coords].")
        return array[:, :, :3]
    if layout == "jtc":
        if array.ndim != 3 or array.shape[2] < 3:
            raise ValueError("--array-layout jtc expects shape [joints, frames, coords].")
        return np.transpose(array[:, :, :3], (1, 0, 2))
    if layout == "tcj":
        if array.ndim != 3 or array.shape[1] < 3:
            raise ValueError("--array-layout tcj expects shape [frames, coords, joints].")
        return np.transpose(array[:, :3, :], (0, 2, 1))
    if layout == "flat":
        if array.ndim != 2 or array.shape[1] % 3 != 0:
            raise ValueError("--array-layout flat expects shape [frames, joints * 3].")
        return array.reshape(array.shape[0], array.shape[1] // 3, 3)
    if layout == "static-jc":
        if array.ndim != 2 or array.shape[1] < 3:
            raise ValueError("--array-layout static-jc expects shape [joints, coords].")
        return array[np.newaxis, :, :3]
    if layout != "auto":
        raise ValueError(f"Unsupported array layout: {layout}")

    if array.ndim == 3:
        if array.shape[-1] >= 3:
            # Most files use [T, J, 3].  If the first dimension is a common
            # joint count and the second is much larger, treat it as [J, T, 3].
            if array.shape[0] in {17, 22, 24, 25, 33} and array.shape[1] > array.shape[0]:
                return np.transpose(array[:, :, :3], (1, 0, 2))
            return array[:, :, :3]
        if array.shape[1] >= 3:
            return np.transpose(array[:, :3, :], (0, 2, 1))

    if array.ndim == 2:
        if array.shape[1] % 3 == 0 and array.shape[1] > 3:
            return array.reshape(array.shape[0], array.shape[1] // 3, 3)
        if array.shape[1] >= 3:
            return array[np.newaxis, :, :3]

    raise ValueError(
        "Could not interpret the selected array as joint positions. Supported "
        "layouts are [T,J,3], [J,T,3], [T,3,J], [T,J*3], or [J,3]. "
        "Use --array-layout to disambiguate."
    )


def list_payload_keys(path: Path, payload: Any) -> None:
    print(f"File: {path}")
    if isinstance(payload, np.ndarray):
        print(f"array: shape={payload.shape}, dtype={payload.dtype}")
        return
    if not isinstance(payload, dict):
        print(f"payload type: {type(payload).__name__}")
        return
    for key, value in payload.items():
        array = np.asarray(value)
        print(f"{key}: shape={array.shape}, dtype={array.dtype}")


def extract_fps(payload: Any, default_fps: float) -> float:
    if not isinstance(payload, dict):
        return default_fps
    if "fps" in payload:
        fps = float(np.asarray(payload["fps"]).squeeze())
        if fps > 0:
            return fps
    if "mocap_framerate" in payload:
        fps = float(np.asarray(payload["mocap_framerate"]).squeeze())
        if fps > 0:
            return fps
    if "frame_time" in payload:
        frame_time = float(np.asarray(payload["frame_time"]).squeeze())
        if frame_time > 0:
            return 1.0 / frame_time
    return default_fps


def is_amass_smpl_payload(payload: Any) -> bool:
    if not isinstance(payload, dict) or "poses" not in payload:
        return False
    poses = np.asarray(payload["poses"])
    return poses.ndim == 2 and poses.shape[1] >= 72


def smpl_axis_angle_to_positions(
    poses: np.ndarray,
    trans: np.ndarray | None,
    unit_scale: float,
) -> np.ndarray:
    poses = np.asarray(poses, dtype=np.float64)
    if poses.ndim != 2 or poses.shape[1] < 72:
        raise ValueError(
            "AMASS/SMPL poses must have shape [frames, >=72] axis-angle values."
        )

    frame_count = poses.shape[0]
    joint_count = len(SMPL24_JOINT_NAMES)
    parents = PRESET_PARENTS["smpl24"]
    body_pose = poses[:, : joint_count * 3].reshape(frame_count, joint_count, 3)
    positions = np.zeros((frame_count, joint_count, 3), dtype=np.float64)

    if trans is None:
        translations = np.zeros((frame_count, 3), dtype=np.float64)
    else:
        translations = np.asarray(trans, dtype=np.float64)
        if translations.ndim != 2 or translations.shape[1] < 3:
            raise ValueError("AMASS/SMPL trans must have shape [frames, 3].")
        if translations.shape[0] != frame_count:
            raise ValueError(
                f"trans has {translations.shape[0]} frames but poses has {frame_count}."
            )
        translations = translations[:, :3] * unit_scale

    offsets = SMPL24_REST_OFFSETS * unit_scale
    for frame in range(frame_count):
        global_rotations = [np.eye(3, dtype=np.float64) for _ in range(joint_count)]
        for joint_index in range(joint_count):
            # AMASS stores a global root orientation in poses[:, :3].  For this
            # lightweight stick-figure preview we keep the body upright and use
            # root translation only; full root orientation needs the real SMPL
            # model coordinate frame to be exact.
            if joint_index == 0:
                local_rotation = np.eye(3, dtype=np.float64)
            else:
                local_rotation = axis_angle_to_matrix(body_pose[frame, joint_index])
            parent = parents[joint_index]
            if parent < 0:
                positions[frame, joint_index] = translations[frame]
                global_rotations[joint_index] = local_rotation
            else:
                positions[frame, joint_index] = (
                    positions[frame, parent] + global_rotations[parent] @ offsets[joint_index]
                )
                global_rotations[joint_index] = global_rotations[parent] @ local_rotation

    return positions


def load_amass_smpl_sequence(
    payload: dict[str, Any],
    path: Path,
    args: argparse.Namespace,
) -> MotionSequence:
    positions = smpl_axis_angle_to_positions(
        poses=np.asarray(payload["poses"]),
        trans=np.asarray(payload["trans"]) if "trans" in payload else None,
        unit_scale=args.unit_scale,
    )
    return MotionSequence(
        positions=positions,
        parents=PRESET_PARENTS["smpl24"],
        joint_names=SMPL24_JOINT_NAMES,
        fps=extract_fps(payload, args.fps_default),
        source_kind="amass-smpl-approx",
        source_path=path,
    )


def extract_joint_names(payload: Any, joint_count: int) -> list[str]:
    if isinstance(payload, dict):
        for key in JOINT_NAME_KEYS:
            if key not in payload:
                continue
            names = []
            for item in np.asarray(payload[key]).ravel():
                if isinstance(item, bytes):
                    names.append(item.decode("utf-8", errors="replace"))
                else:
                    names.append(str(item))
            if len(names) == joint_count:
                return names
    return [f"joint_{index}" for index in range(joint_count)]


def parse_parents_text(text: str) -> list[int]:
    values = [part.strip() for part in text.split(",") if part.strip()]
    if not values:
        raise ValueError("--parents was provided but no values were parsed.")
    return [int(value) for value in values]


def parents_from_edges(edge_array: np.ndarray, joint_count: int) -> list[int] | None:
    array = np.asarray(edge_array).astype(int)
    if array.ndim != 2:
        return None
    if array.shape[0] == 2:
        edges = array.T
    elif array.shape[1] == 2:
        edges = array
    else:
        return None
    parents = [-1] * joint_count
    for parent, child in edges:
        if 0 <= child < joint_count and 0 <= parent < joint_count:
            parents[int(child)] = int(parent)
    return parents


def extract_parents(
    payload: Any,
    joint_count: int,
    parents_text: str | None,
    skeleton_preset: str,
) -> list[int]:
    if parents_text:
        parents = parse_parents_text(parents_text)
        if len(parents) != joint_count:
            raise ValueError(
                f"--parents has {len(parents)} values, but the motion has "
                f"{joint_count} joints."
            )
        return parents

    if isinstance(payload, dict):
        for key in PARENT_KEYS:
            if key not in payload:
                continue
            array = np.asarray(payload[key]).squeeze()
            if array.ndim == 1 and array.size == joint_count:
                return array.astype(int).tolist()
            parents = parents_from_edges(array, joint_count)
            if parents is not None:
                return parents

    if skeleton_preset == "chain":
        return [-1] + list(range(joint_count - 1))
    if skeleton_preset != "auto":
        parents = PRESET_PARENTS[skeleton_preset]
        if len(parents) != joint_count:
            raise ValueError(
                f"Skeleton preset '{skeleton_preset}' has {len(parents)} joints, "
                f"but the motion has {joint_count} joints."
            )
        return parents

    for preset in ("lafan22", "smpl24", "coco17"):
        parents = PRESET_PARENTS[preset]
        if len(parents) == joint_count:
            return parents

    print(
        f"Warning: no skeleton parents found for {joint_count} joints; "
        "falling back to a simple index chain. Use --parents or --skeleton.",
        file=sys.stderr,
    )
    return [-1] + list(range(joint_count - 1))


def load_bvh_sequence(path: Path, args: argparse.Namespace) -> MotionSequence:
    skeleton, motion, frame_time = read_bvh(path)
    positions = bvh_to_positions(
        skeleton=skeleton,
        motion=motion,
        unit_scale=args.unit_scale,
        position_mode=args.bvh_position_mode,
    )
    fps = 1.0 / frame_time if frame_time > 0 else args.fps_default
    return MotionSequence(
        positions=positions,
        parents=skeleton.parents,
        joint_names=skeleton.names,
        fps=fps,
        source_kind="bvh",
        source_path=path,
    )


def try_load_bvh_channel_sequence(
    payload: Any,
    selected_array: np.ndarray,
    path: Path,
    args: argparse.Namespace,
) -> MotionSequence | None:
    skeleton = None
    source_kind = None
    if isinstance(payload, dict) and "hierarchy" in payload:
        hierarchy = scalar_to_string(payload["hierarchy"])
        skeleton = parse_bvh_hierarchy(hierarchy.splitlines())
        source_kind = "bvh-metadata"
    elif args.template_bvh:
        skeleton, _, _ = read_bvh(Path(args.template_bvh))
        source_kind = "template-bvh"

    if skeleton is None:
        return None

    array = np.asarray(selected_array)
    if array.ndim != 2 or array.shape[1] != skeleton.channel_count:
        return None

    positions = bvh_to_positions(
        skeleton=skeleton,
        motion=array,
        unit_scale=args.unit_scale,
        position_mode=args.bvh_position_mode,
    )
    return MotionSequence(
        positions=positions,
        parents=skeleton.parents,
        joint_names=skeleton.names,
        fps=extract_fps(payload, args.fps_default),
        source_kind=source_kind or "bvh-channels",
        source_path=path,
    )


def load_array_sequence(path: Path, args: argparse.Namespace) -> MotionSequence:
    suffix = path.suffix.lower()
    payload = load_numpy_payload(path)

    if args.list_keys:
        list_payload_keys(path, payload)
        raise SystemExit(0)

    if args.key is None and is_amass_smpl_payload(payload):
        return load_amass_smpl_sequence(payload, path, args)

    selected_array, selected_key = select_array(payload, args.key)
    bvh_sequence = try_load_bvh_channel_sequence(payload, selected_array, path, args)
    if bvh_sequence is not None:
        return bvh_sequence

    positions = normalize_positions(selected_array, args.array_layout)
    positions *= args.unit_scale
    parents = extract_parents(payload, positions.shape[1], args.parents, args.skeleton)
    joint_names = extract_joint_names(payload, positions.shape[1])
    fps = extract_fps(payload, args.fps_default)

    print(f"Selected array key: {selected_key}", file=sys.stderr)
    return MotionSequence(
        positions=positions,
        parents=parents,
        joint_names=joint_names,
        fps=fps,
        source_kind="joint-positions",
        source_path=path,
    )


def load_motion_sequence(path: Path, args: argparse.Namespace) -> MotionSequence:
    if not path.exists():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    if suffix == ".bvh":
        return load_bvh_sequence(path, args)
    if suffix in NUMPY_EXTENSIONS:
        return load_array_sequence(path, args)
    raise ValueError(
        f"Unsupported file extension: {suffix}. Use .bvh, .npv, .npy, or .npz."
    )


def parents_to_edges(parents: list[int], joint_count: int) -> list[tuple[int, int]]:
    edges = []
    for child, parent in enumerate(parents):
        if 0 <= parent < joint_count and child != parent:
            edges.append((parent, child))
    return edges


def remap_up_axis(positions: np.ndarray, up_axis: str) -> tuple[np.ndarray, tuple[str, str, str]]:
    if up_axis == "z":
        return positions, ("X", "Y", "Z")
    if up_axis == "y":
        return positions[:, :, [0, 2, 1]], ("X", "Z", "Y")
    if up_axis == "x":
        return positions[:, :, [1, 2, 0]], ("Y", "Z", "X")
    raise ValueError(f"Unsupported --up-axis: {up_axis}")


def finite_radius(points: np.ndarray) -> float:
    finite = points[np.isfinite(points)]
    if finite.size == 0:
        return 1.0
    span = float(np.nanmax(finite) - np.nanmin(finite))
    if span <= 1e-9:
        return 1.0
    return max(span * 0.55, 1e-3)


def set_axes_equal_limits(ax: Any, center: np.ndarray, radius: float) -> None:
    ax.set_xlim(center[0] - radius, center[0] + radius)
    ax.set_ylim(center[1] - radius, center[1] + radius)
    ax.set_zlim(center[2] - radius, center[2] + radius)


def color_to_rgb(value: str, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    text = str(value).strip()
    if text.startswith("#") and len(text) == 7:
        try:
            return int(text[1:3], 16), int(text[3:5], 16), int(text[5:7], 16)
        except ValueError:
            return fallback
    return fallback


def render_motion_pillow(
    sequence: MotionSequence,
    args: argparse.Namespace,
    output_path: Path,
) -> None:
    from PIL import Image, ImageDraw

    suffix = output_path.suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        raise RuntimeError(
            "matplotlib is required for this output format. Pillow fallback supports "
            "png, jpg, webp, and gif."
        )

    positions = sliced_positions(sequence, args)
    positions, _ = remap_up_axis(positions, args.up_axis)
    edges = parents_to_edges(sequence.parents, positions.shape[1])
    if not edges:
        raise ValueError("No drawable skeleton edges were found.")

    display_positions = positions - positions[:, :1, :] if args.follow_root else positions
    projected = np.empty((display_positions.shape[0], display_positions.shape[1], 2))
    projected[:, :, 0] = display_positions[:, :, 0] + 0.25 * display_positions[:, :, 1]
    projected[:, :, 1] = display_positions[:, :, 2] + 0.12 * display_positions[:, :, 1]

    finite = projected[np.isfinite(projected)]
    if finite.size == 0:
        raise ValueError("No finite points were found for rendering.")
    min_xy = np.nanmin(projected.reshape(-1, 2), axis=0)
    max_xy = np.nanmax(projected.reshape(-1, 2), axis=0)
    center = (min_xy + max_xy) * 0.5
    span = np.maximum(max_xy - min_xy, 1e-6)

    size = max(320, int(args.figure_size * args.dpi))
    margin = max(32, int(size * 0.08))
    scale = (size - 2 * margin) / float(np.max(span) * max(args.padding, 1e-6))
    bone_color = color_to_rgb(args.bone_color, (31, 119, 180))
    joint_color = color_to_rgb(args.joint_color, (214, 39, 40))
    text_color = (40, 40, 40)
    title = args.title or f"{sequence.source_path.name} ({sequence.source_kind})"
    fps = args.fps if args.fps is not None else max(sequence.fps / max(args.stride, 1), 1.0)
    duration_ms = max(20, int(round(1000.0 / fps)))

    def to_pixel(points: np.ndarray) -> np.ndarray:
        xy = (points - center) * scale
        xy[:, 0] += size * 0.5
        xy[:, 1] = size * 0.5 - xy[:, 1]
        return xy

    frames = []
    for frame_index, frame_points in enumerate(projected):
        image = Image.new("RGB", (size, size), "white")
        draw = ImageDraw.Draw(image)
        clean_points = np.nan_to_num(frame_points, nan=0.0, posinf=0.0, neginf=0.0)
        pixels = to_pixel(clean_points)

        for parent, child in edges:
            p0 = tuple(np.round(pixels[parent]).astype(int))
            p1 = tuple(np.round(pixels[child]).astype(int))
            draw.line([p0, p1], fill=bone_color, width=max(1, int(args.bone_width)))

        radius = max(2, int(np.sqrt(max(args.joint_size, 1.0)) * 0.7))
        for x, y in pixels:
            cx = int(round(float(x)))
            cy = int(round(float(y)))
            draw.ellipse(
                [cx - radius, cy - radius, cx + radius, cy + radius],
                fill=joint_color,
                outline=(120, 20, 20),
            )

        draw.text((12, 10), title, fill=text_color)
        draw.text((12, 28), f"frame {frame_index + 1}/{projected.shape[0]}", fill=text_color)
        frames.append(image)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if suffix == ".gif":
        frames[0].save(
            output_path,
            save_all=True,
            append_images=frames[1:],
            duration=duration_ms,
            loop=0,
            optimize=True,
        )
    else:
        frames[0].save(output_path)
    print(f"Saved: {output_path}")


def sliced_positions(sequence: MotionSequence, args: argparse.Namespace) -> np.ndarray:
    positions = sequence.positions
    start = max(args.start, 0)
    end = args.end if args.end is not None else positions.shape[0]
    end = min(end, positions.shape[0])
    if start >= end:
        raise ValueError(f"Invalid frame slice: start={start}, end={end}.")
    stride = max(args.stride, 1)
    sliced = positions[start:end:stride]
    if args.max_frames is not None:
        sliced = sliced[: args.max_frames]
    if sliced.size == 0:
        raise ValueError("No frames remain after applying start/end/stride/max-frames.")
    return sliced


def render_motion(sequence: MotionSequence, args: argparse.Namespace) -> None:
    output_path = Path(args.output) if args.output else None
    headless = sys.platform.startswith("linux") and not os.environ.get("DISPLAY")
    if output_path is None and (args.no_show or headless):
        raise RuntimeError(
            "No display is available. Provide --output, for example "
            "--output outputs/preview.gif or --output outputs/first_frame.png."
        )

    try:
        if output_path is not None or args.no_show or headless:
            import matplotlib

            matplotlib.use("Agg")

        import matplotlib.pyplot as plt
        from matplotlib.animation import FFMpegWriter, FuncAnimation, PillowWriter
    except ImportError as exc:
        if output_path is not None:
            print(
                "Warning: matplotlib is not available; using Pillow fallback renderer.",
                file=sys.stderr,
            )
            render_motion_pillow(sequence, args, output_path)
            return
        raise RuntimeError(
            "matplotlib is required for rendering. Install dependencies with "
            "'pip install -r requirements.txt' in the Stick figure skeleton directory."
        ) from exc

    positions = sliced_positions(sequence, args)
    positions, labels = remap_up_axis(positions, args.up_axis)
    edges = parents_to_edges(sequence.parents, positions.shape[1])
    if not edges:
        raise ValueError("No drawable skeleton edges were found.")

    fps = args.fps if args.fps is not None else max(sequence.fps / max(args.stride, 1), 1.0)
    figure = plt.figure(figsize=(args.figure_size, args.figure_size), dpi=args.dpi)
    ax = figure.add_subplot(111, projection="3d")
    ax.view_init(elev=args.elev, azim=args.azim)
    ax.set_xlabel(labels[0])
    ax.set_ylabel(labels[1])
    ax.set_zlabel(labels[2])
    ax.grid(True, alpha=0.25)
    title = args.title or f"{sequence.source_path.name} ({sequence.source_kind})"

    centered_for_radius = positions
    if args.follow_root:
        centered_for_radius = positions - positions[:, :1, :]
    radius = finite_radius(centered_for_radius) * args.padding
    global_center = np.nanmean(positions.reshape(-1, 3), axis=0)
    set_axes_equal_limits(ax, global_center, radius)

    lines = [
        ax.plot([], [], [], color=args.bone_color, linewidth=args.bone_width)[0]
        for _ in edges
    ]
    points = ax.scatter([], [], [], s=args.joint_size, c=args.joint_color, depthshade=True)

    def update(frame_index: int) -> list[Any]:
        frame = positions[frame_index]
        clean_frame = np.nan_to_num(frame, nan=0.0, posinf=0.0, neginf=0.0)
        for line, (parent, child) in zip(lines, edges):
            segment = clean_frame[[parent, child]]
            line.set_data(segment[:, 0], segment[:, 1])
            line.set_3d_properties(segment[:, 2])
        points._offsets3d = (
            clean_frame[:, 0],
            clean_frame[:, 1],
            clean_frame[:, 2],
        )
        if args.follow_root:
            center = clean_frame[0]
            set_axes_equal_limits(ax, center, radius)
        ax.set_title(f"{title} | frame {frame_index + 1}/{positions.shape[0]}")
        return [*lines, points]

    update(0)
    figure.tight_layout()

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        suffix = output_path.suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".svg", ".pdf"}:
            figure.savefig(output_path, bbox_inches="tight")
        elif suffix == ".gif":
            animation = FuncAnimation(
                figure,
                update,
                frames=positions.shape[0],
                interval=1000.0 / fps,
                blit=False,
            )
            animation.save(output_path, writer=PillowWriter(fps=fps))
        elif suffix in {".mp4", ".m4v"}:
            animation = FuncAnimation(
                figure,
                update,
                frames=positions.shape[0],
                interval=1000.0 / fps,
                blit=False,
            )
            animation.save(output_path, writer=FFMpegWriter(fps=fps))
        else:
            raise ValueError(
                f"Unsupported output extension '{suffix}'. Use png, gif, or mp4."
            )
        print(f"Saved: {output_path}")

    if not args.no_show and output_path is None:
        plt.show()
    plt.close(figure)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Visualize .bvh, .npv, .npy, and .npz motion as a 3D stick figure."
    )
    parser.add_argument("input", help="Path to a .bvh, .npv, .npy, or .npz motion file.")
    parser.add_argument("-o", "--output", help="Save to .png, .gif, or .mp4.")
    parser.add_argument("--key", help="Array key to read from .npv/.npz or dict-like .npy.")
    parser.add_argument(
        "--list-keys",
        action="store_true",
        help="List arrays inside .npv/.npz or dict-like .npy and exit.",
    )
    parser.add_argument(
        "--template-bvh",
        help="BVH template used when .npv/.npy/.npz contains raw BVH channel data.",
    )
    parser.add_argument(
        "--array-layout",
        choices=("auto", "tjc", "jtc", "tcj", "flat", "static-jc"),
        default="auto",
        help=(
            "Layout for position arrays: tjc=[T,J,3], jtc=[J,T,3], "
            "tcj=[T,3,J], flat=[T,J*3], static-jc=[J,3]."
        ),
    )
    parser.add_argument(
        "--parents",
        help="Comma-separated parent index list, for example '-1,0,1,2'.",
    )
    parser.add_argument(
        "--skeleton",
        choices=("auto", "chain", "lafan22", "smpl24", "coco17"),
        default="auto",
        help="Skeleton preset for .npv/.npy/.npz position arrays without parents.",
    )
    parser.add_argument(
        "--unit-scale",
        type=float,
        default=1.0,
        help="Scale applied to all positions. Use 0.01 for centimeter BVH data.",
    )
    parser.add_argument(
        "--bvh-position-mode",
        choices=("replace", "add"),
        default="replace",
        help=(
            "How BVH position channels combine with OFFSET. 'replace' is common "
            "for BVH root/world translations; 'add' uses OFFSET + channel value."
        ),
    )
    parser.add_argument(
        "--up-axis",
        choices=("x", "y", "z"),
        default="z",
        help="Input coordinate axis that should be displayed vertically.",
    )
    parser.add_argument("--start", type=int, default=0, help="First frame index.")
    parser.add_argument("--end", type=int, help="Exclusive end frame index.")
    parser.add_argument("--stride", type=int, default=1, help="Frame stride.")
    parser.add_argument("--max-frames", type=int, help="Maximum frames to draw.")
    parser.add_argument("--fps", type=float, help="Output/display FPS override.")
    parser.add_argument(
        "--fps-default",
        type=float,
        default=30.0,
        help="FPS used when the file does not contain timing metadata.",
    )
    parser.add_argument("--no-show", action="store_true", help="Do not open a GUI window.")
    parser.add_argument("--follow-root", dest="follow_root", action="store_true", default=True)
    parser.add_argument("--no-follow-root", dest="follow_root", action="store_false")
    parser.add_argument("--padding", type=float, default=1.25, help="Plot padding multiplier.")
    parser.add_argument("--elev", type=float, default=18.0, help="3D camera elevation.")
    parser.add_argument("--azim", type=float, default=-70.0, help="3D camera azimuth.")
    parser.add_argument("--figure-size", type=float, default=7.0, help="Figure size in inches.")
    parser.add_argument("--dpi", type=int, default=120, help="Figure DPI.")
    parser.add_argument("--bone-width", type=float, default=2.5)
    parser.add_argument("--joint-size", type=float, default=18.0)
    parser.add_argument("--bone-color", default="#1f77b4")
    parser.add_argument("--joint-color", default="#d62728")
    parser.add_argument("--title", help="Custom plot title.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        path = Path(args.input).expanduser()
        sequence = load_motion_sequence(path, args)
        print(
            "Loaded "
            f"{sequence.source_kind}: frames={sequence.positions.shape[0]}, "
            f"joints={sequence.positions.shape[1]}, fps={sequence.fps:.3f}",
            file=sys.stderr,
        )
        render_motion(sequence, args)
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
