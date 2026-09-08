from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

from loaders.common_motion import MotionData


def nan() -> float:
    """Return a JSON/CSV friendly NaN."""
    return float("nan")


def safe_mean(value: Any) -> float:
    """Mean that returns NaN when no finite values exist."""
    arr = np.asarray(value, dtype=float)
    finite = arr[np.isfinite(arr)]
    return float(np.mean(finite)) if finite.size else nan()


def safe_std(value: Any) -> float:
    """Std that returns NaN when no finite values exist."""
    arr = np.asarray(value, dtype=float)
    finite = arr[np.isfinite(arr)]
    return float(np.std(finite)) if finite.size else nan()


def safe_max(value: Any) -> float:
    """Max that returns NaN when no finite values exist."""
    arr = np.asarray(value, dtype=float)
    finite = arr[np.isfinite(arr)]
    return float(np.max(finite)) if finite.size else nan()


def safe_min(value: Any) -> float:
    """Min that returns NaN when no finite values exist."""
    arr = np.asarray(value, dtype=float)
    finite = arr[np.isfinite(arr)]
    return float(np.min(finite)) if finite.size else nan()


def finite_ratio(mask: Any) -> float:
    """Return mean of a boolean-like mask."""
    arr = np.asarray(mask)
    return float(np.mean(arr)) if arr.size else nan()


def keypoint_stack(motion: MotionData, names: List[str]) -> Tuple[np.ndarray, List[str]]:
    """Stack available keypoints as [T,K,3], filling missing with NaN."""
    motion.ensure_keypoint_aliases()
    n = motion.num_frames
    arrays = []
    for name in names:
        arr = motion.get_keypoint(name)
        if arr is None:
            arrays.append(np.full((n, 3), np.nan))
        else:
            arrays.append(np.asarray(arr[:n], dtype=float))
    return np.stack(arrays, axis=1) if arrays else np.empty((n, 0, 3)), names


def quat_angle_deg(a: Optional[np.ndarray], b: Optional[np.ndarray], n: Optional[int] = None) -> Optional[np.ndarray]:
    """Compute angular distance between wxyz quaternion trajectories."""
    if a is None or b is None:
        return None
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    count = min(len(a), len(b)) if n is None else min(n, len(a), len(b))
    if count <= 0:
        return None
    a = _normalize_quat(a[:count])
    b = _normalize_quat(b[:count])
    dots = np.abs(np.sum(a * b, axis=1))
    dots = np.clip(dots, -1.0, 1.0)
    return np.rad2deg(2.0 * np.arccos(dots))


def body_tilt_deg(quat: Optional[np.ndarray]) -> Optional[np.ndarray]:
    """Compute tilt angle between local Z and world Z from wxyz quaternions."""
    if quat is None:
        return None
    q = _normalize_quat(np.asarray(quat, dtype=float))
    w, x, y, z = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
    z_axis = np.stack([2 * (x * z + w * y), 2 * (y * z - w * x), 1 - 2 * (x * x + y * y)], axis=1)
    denom = np.linalg.norm(z_axis, axis=1)
    cos_tilt = np.divide(z_axis[:, 2], denom, out=np.full_like(denom, np.nan), where=denom > 1e-12)
    return np.rad2deg(np.arccos(np.clip(cos_tilt, -1.0, 1.0)))


def trajectory_length(pos: Optional[np.ndarray]) -> float:
    """Return path length of a 3D position trajectory."""
    if pos is None or len(pos) < 2:
        return nan()
    return float(np.nansum(np.linalg.norm(np.diff(pos, axis=0), axis=1)))


def dtw_distance(a: Optional[np.ndarray], b: Optional[np.ndarray], max_frames: int = 500) -> float:
    """Compute a simple DTW distance for root trajectories."""
    if a is None or b is None:
        return nan()
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if len(a) == 0 or len(b) == 0:
        return nan()
    if len(a) > max_frames:
        idx = np.linspace(0, len(a) - 1, max_frames).round().astype(int)
        a = a[idx]
    if len(b) > max_frames:
        idx = np.linspace(0, len(b) - 1, max_frames).round().astype(int)
        b = b[idx]
    cost = np.full((len(a) + 1, len(b) + 1), np.inf)
    cost[0, 0] = 0.0
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            d = np.linalg.norm(a[i - 1] - b[j - 1])
            cost[i, j] = d + min(cost[i - 1, j], cost[i, j - 1], cost[i - 1, j - 1])
    return float(cost[-1, -1] / (len(a) + len(b)))


def unavailable_set(keys: Iterable[str], reason: str) -> Dict[str, str]:
    """Create an unavailable mapping."""
    return {key: reason for key in keys}


def _normalize_quat(q: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(q, axis=1, keepdims=True)
    return np.divide(q, norm, out=np.tile(np.asarray([[1.0, 0.0, 0.0, 0.0]]), (len(q), 1)), where=norm > 1e-12)


def numeric(value: Any) -> Optional[float]:
    """Convert a value to finite float or None."""
    try:
        x = float(value)
    except Exception:
        return None
    return x if np.isfinite(x) else None

