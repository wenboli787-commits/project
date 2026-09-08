from __future__ import annotations

import math

import numpy as np


def normalize_quat_wxyz(quat: np.ndarray) -> np.ndarray:
    quat = np.asarray(quat, dtype=np.float64)
    norm = np.linalg.norm(quat, axis=-1, keepdims=True)
    if np.any(norm <= 0):
        raise ValueError("Quaternion norm must be positive.")
    return quat / norm


def quat_conjugate_wxyz(quat: np.ndarray) -> np.ndarray:
    quat = np.asarray(quat, dtype=np.float64)
    out = quat.copy()
    out[..., 1:] *= -1.0
    return out


def quat_multiply_wxyz(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    aw, ax, ay, az = np.moveaxis(a, -1, 0)
    bw, bx, by, bz = np.moveaxis(b, -1, 0)
    return np.stack(
        [
            aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
        ],
        axis=-1,
    )


def quat_angle_error_wxyz(current: np.ndarray, target: np.ndarray) -> float:
    current = normalize_quat_wxyz(current)
    target = normalize_quat_wxyz(target)
    dot = float(abs(np.dot(current, target)))
    dot = max(-1.0, min(1.0, dot))
    return 2.0 * math.acos(dot)


def quat_error_vector_wxyz(current: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Return a compact target-to-current orientation error vector."""

    current = normalize_quat_wxyz(current)
    target = normalize_quat_wxyz(target)
    delta = quat_multiply_wxyz(quat_conjugate_wxyz(target), current)
    if delta[0] < 0.0:
        delta = -delta
    return delta[1:] * 2.0
