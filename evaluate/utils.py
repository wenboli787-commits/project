"""Shared utilities for I/O, alignment, interpolation and safe serialization."""

from __future__ import annotations

import copy
import json
import warnings
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np
import yaml

from canonical_motion import CanonicalMotion


UNAVAILABLE = "unavailable"


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Mapping YAML was not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Mapping YAML must be a mapping, got {type(data).__name__}.")
    return data


def recursive_get(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current


def as_python(value: Any) -> Any:
    """Convert NumPy values recursively so JSON and CSV never see NumPy scalars."""
    if isinstance(value, np.ndarray):
        return [as_python(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): as_python(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [as_python(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not np.isfinite(value):
        return UNAVAILABLE
    return value


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(as_python(data), handle, indent=2, ensure_ascii=False)


def finite_difference(values: np.ndarray, fps: float) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if values.shape[0] < 2:
        return np.zeros_like(values)
    return np.gradient(values, 1.0 / fps, axis=0, edge_order=1)


def normalize_quaternions(quaternions: np.ndarray) -> np.ndarray:
    quaternions = np.asarray(quaternions, dtype=float)
    norms = np.linalg.norm(quaternions, axis=-1, keepdims=True)
    return quaternions / np.maximum(norms, 1e-12)


def xyzw_to_wxyz(quaternions: np.ndarray) -> np.ndarray:
    values = np.asarray(quaternions, dtype=float)
    return values[..., [3, 0, 1, 2]]


def wxyz_to_xyzw(quaternions: np.ndarray) -> np.ndarray:
    values = np.asarray(quaternions, dtype=float)
    return values[..., [1, 2, 3, 0]]


def quat_multiply(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    """Hamilton product for broadcastable wxyz quaternions."""
    l = np.asarray(left, dtype=float)
    r = np.asarray(right, dtype=float)
    lw, lx, ly, lz = np.moveaxis(l, -1, 0)
    rw, rx, ry, rz = np.moveaxis(r, -1, 0)
    return np.stack(
        (lw * rw - lx * rx - ly * ry - lz * rz,
         lw * rx + lx * rw + ly * rz - lz * ry,
         lw * ry - lx * rz + ly * rw + lz * rx,
         lw * rz + lx * ry - ly * rx + lz * rw),
        axis=-1,
    )


def quat_conjugate(quaternion: np.ndarray) -> np.ndarray:
    result = np.asarray(quaternion, dtype=float).copy()
    result[..., 1:] *= -1
    return result


def quat_rotate(quaternion: np.ndarray, vectors: np.ndarray) -> np.ndarray:
    quat = normalize_quaternions(np.asarray(quaternion, dtype=float))
    vec = np.asarray(vectors, dtype=float)
    vector_quat = np.concatenate((np.zeros(vec.shape[:-1] + (1,)), vec), axis=-1)
    return quat_multiply(quat_multiply(quat, vector_quat), quat_conjugate(quat))[..., 1:]


def yaw_from_wxyz(quaternion: np.ndarray) -> np.ndarray:
    q = normalize_quaternions(quaternion)
    w, x, y, z = np.moveaxis(q, -1, 0)
    return np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def yaw_quaternion(angle: float) -> np.ndarray:
    return np.array([np.cos(angle / 2), 0.0, 0.0, np.sin(angle / 2)], dtype=float)


def resample_array(values: np.ndarray, source_fps: float, target_fps: float, *, boolean: bool = False) -> np.ndarray:
    """Resample an arbitrary [T, ...] trajectory without SciPy dependency."""
    values = np.asarray(values)
    if values.shape[0] < 2 or abs(source_fps - target_fps) < 1e-9:
        return values.copy()
    duration = (values.shape[0] - 1) / source_fps
    count = max(2, int(round(duration * target_fps)) + 1)
    old_time = np.linspace(0.0, duration, values.shape[0])
    new_time = np.linspace(0.0, duration, count)
    if boolean:
        indices = np.clip(np.round(new_time * source_fps).astype(int), 0, values.shape[0] - 1)
        return values[indices]
    flat = values.reshape(values.shape[0], -1)
    result = np.empty((count, flat.shape[1]), dtype=float)
    for column in range(flat.shape[1]):
        result[:, column] = np.interp(new_time, old_time, flat[:, column])
    return result.reshape((count,) + values.shape[1:])


def resample_motion(motion: CanonicalMotion, target_fps: float) -> CanonicalMotion:
    result = motion.copy(name=motion.name)
    source_fps = motion.fps
    for key, value in list(result.__dict__.items()):
        if isinstance(value, np.ndarray) and value.ndim >= 1 and value.shape[0] == motion.num_frames:
            if key == "time":
                continue
            setattr(result, key, resample_array(value, source_fps, target_fps))
        elif isinstance(value, dict) and key not in {"metadata"}:
            is_bool = key == "foot_contacts"
            mapped = {}
            for subkey, subvalue in value.items():
                if isinstance(subvalue, np.ndarray) and subvalue.ndim >= 1 and subvalue.shape[0] == motion.num_frames:
                    mapped[subkey] = resample_array(subvalue, source_fps, target_fps, boolean=is_bool)
                else:
                    mapped[subkey] = subvalue
            setattr(result, key, mapped)
    result.fps = float(target_fps)
    result.time = np.arange(result.num_frames, dtype=float) / result.fps
    result.metadata["resampled_from_fps"] = source_fps
    return result


def trim_motion(motion: CanonicalMotion, frames: int) -> CanonicalMotion:
    result = motion.copy(name=motion.name)
    for key, value in list(result.__dict__.items()):
        if isinstance(value, np.ndarray) and value.ndim >= 1 and value.shape[0] == motion.num_frames:
            setattr(result, key, value[:frames].copy())
        elif isinstance(value, dict) and key != "metadata":
            setattr(result, key, {
                subkey: (subvalue[:frames].copy() if isinstance(subvalue, np.ndarray) and subvalue.ndim >= 1 and subvalue.shape[0] == motion.num_frames else subvalue)
                for subkey, subvalue in value.items()
            })
    result.metadata["trimmed_to_frames"] = frames
    return result


def align_time(reference: CanonicalMotion, candidate: CanonicalMotion, resample: bool = False) -> tuple[CanonicalMotion, CanonicalMotion, dict[str, Any]]:
    """Put a pair at one FPS and one length; document every automatic intervention."""
    ref, cand = reference.copy(), candidate.copy()
    note: dict[str, Any] = {"reference_fps": ref.fps, "candidate_fps": cand.fps, "resampled": False, "trimmed": False}
    if resample and abs(ref.fps - cand.fps) > 1e-6:
        cand = resample_motion(cand, ref.fps)
        note["resampled"] = True
    elif abs(ref.fps - cand.fps) > 1e-6:
        warnings.warn(
            f"{candidate.name}: fps ({candidate.fps}) differs from reference ({reference.fps}); "
            "frames are clipped by index. Use --resample for time-based interpolation.", stacklevel=2,
        )
        note["fps_mismatch_without_resampling"] = True
    common = min(ref.num_frames, cand.num_frames)
    if not common:
        raise ValueError("A reference or candidate motion has zero frames.")
    if ref.num_frames != common or cand.num_frames != common:
        ref, cand = trim_motion(ref, common), trim_motion(cand, common)
        note["trimmed"] = True
    note["evaluated_frames"] = common
    return ref, cand, note


def estimate_height(motion: CanonicalMotion) -> Optional[float]:
    # Prefer a robust per-frame head-to-foot distance. A global bounding box
    # would confuse forward locomotion displacement with the body's height.
    head = motion.position("head")
    feet = [motion.position(name) for name in ("left_foot", "right_foot", "left_ankle", "right_ankle")]
    feet = [foot for foot in feet if foot is not None]
    if head is not None and feet:
        foot_z = np.min(np.stack([foot[:, 2] for foot in feet], axis=1), axis=1)
        height = float(np.nanmedian(head[:, 2] - foot_z))
        if np.isfinite(height) and height > 1e-6:
            return height
    points = [point for point in [head, *feet] if point is not None]
    if not points:
        return None
    stacked = np.concatenate([point.reshape(-1, 3) for point in points], axis=0)
    height = float(np.nanmax(stacked[:, 2]) - np.nanmin(stacked[:, 2]))
    return height if np.isfinite(height) and height > 1e-6 else None


def _transform_positions(motion: CanonicalMotion, origin: np.ndarray, scale: float, yaw: float, destination: np.ndarray) -> None:
    rotation = yaw_quaternion(yaw)
    def transform(values: np.ndarray) -> np.ndarray:
        return quat_rotate(rotation, (values - origin) * scale) + destination
    for key in ("root_pos",):
        value = getattr(motion, key)
        if value is not None:
            setattr(motion, key, transform(value))
    for key in ("body_positions", "end_effector_positions"):
        values = getattr(motion, key)
        if values:
            setattr(motion, key, {name: transform(value) for name, value in values.items()})
    if motion.joint_positions_ref is not None:
        motion.joint_positions_ref = transform(motion.joint_positions_ref)
    if motion.root_quat is not None:
        motion.root_quat = normalize_quaternions(quat_multiply(rotation, motion.root_quat))
    for key in ("body_quats", "end_effector_quats"):
        values = getattr(motion, key)
        if values:
            setattr(motion, key, {name: normalize_quaternions(quat_multiply(rotation, value)) for name, value in values.items()})


def normalize_reference(reference: CanonicalMotion, candidate: CanonicalMotion, config: dict[str, Any]) -> tuple[CanonicalMotion, dict[str, Any]]:
    """Scale and rigidly align reference to candidate when requested by YAML."""
    ref = reference.copy(name=reference.name)
    norm = config.get("normalization", {})
    note: dict[str, Any] = {"scale": 1.0, "root_aligned": False, "heading_aligned": False}
    mode = str(norm.get("scale_by", "none"))
    if norm.get("enable_scale_normalization", False) and mode != "none":
        ref_height, candidate_height = estimate_height(ref), estimate_height(candidate)
        if ref_height and candidate_height:
            note["scale"] = candidate_height / ref_height
        else:
            note["scale_warning"] = "unavailable: no usable height landmarks"
    origin = ref.root_pos[0] if ref.root_pos is not None else np.zeros(3)
    destination = candidate.root_pos[0] if norm.get("align_root_at_first_frame", True) and candidate.root_pos is not None else origin
    note["root_aligned"] = bool(norm.get("align_root_at_first_frame", True) and candidate.root_pos is not None)
    yaw = 0.0
    if norm.get("align_heading_at_first_frame", True) and ref.root_quat is not None and candidate.root_quat is not None:
        yaw = float(yaw_from_wxyz(candidate.root_quat[0]) - yaw_from_wxyz(ref.root_quat[0]))
        note["heading_aligned"] = True
    _transform_positions(ref, origin, float(note["scale"]), yaw, destination)
    return ref, note


def flatten_summary(summary: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten nested metric output for a practical method-by-metric CSV."""
    result: dict[str, Any] = {}
    for key, value in summary.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            result.update(flatten_summary(value, path))
        elif isinstance(value, (list, tuple, np.ndarray)):
            result[path] = json.dumps(as_python(value), ensure_ascii=False)
        else:
            result[path] = as_python(value)
    return result
