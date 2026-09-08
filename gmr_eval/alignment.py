from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np

from .io import MotionData, finite_difference, quat_multiply, quat_normalize, quat_to_yaw


def sync_motions(reference: MotionData, prediction: MotionData, config: Dict[str, Any]) -> Tuple[MotionData, MotionData, List[str]]:
    """Return copies on a shared timeline using trim or resample mode."""
    ref = reference.copy().finalize()
    pred = prediction.copy().finalize()
    target_fps = float(config.get("target_fps", config.get("default_fps", 30.0)))
    mode = str(config.get("sync_mode", "resample")).lower()
    notes: List[str] = []

    if mode == "trim":
        ref = resample_to_fps(ref, target_fps)
        pred = resample_to_fps(pred, target_fps)
        n = min(ref.num_frames, pred.num_frames)
        ref = trim_motion(ref, n)
        pred = trim_motion(pred, n)
        notes.append(f"Time sync trim: target_fps={target_fps:g}, frames={n}.")
        return ref, pred, notes

    duration = min(_positive_duration(ref), _positive_duration(pred))
    if duration <= 0.0:
        n = min(ref.num_frames, pred.num_frames)
    else:
        n = max(2, int(round(duration * target_fps)) + 1)
    ref = resample_to_frame_count(ref, n, duration if duration > 0 else None)
    pred = resample_to_frame_count(pred, n, duration if duration > 0 else None)
    ref.fps = target_fps
    pred.fps = target_fps
    notes.append(f"Time sync resample: target_fps={target_fps:g}, duration={duration:.4f}s, frames={n}.")
    return ref, pred, notes


def make_aligned_pair(reference: MotionData, prediction: MotionData, config: Dict[str, Any], *, use_scale: bool = False) -> Tuple[MotionData, MotionData, List[str]]:
    """Return synced copies with initial root/heading and optional scale alignment."""
    ref, pred, notes = sync_motions(reference, prediction, config)
    alignment = config.get("alignment", {})
    if alignment.get("initial_root", True):
        if ref.root_pos is not None and pred.root_pos is not None and ref.num_frames > 0 and pred.num_frames > 0:
            translate_motion(pred, ref.root_pos[0] - pred.root_pos[0])
            notes.append("Aligned prediction initial root position to reference.")
    if alignment.get("initial_heading", True):
        yaw_delta = estimate_initial_heading(ref) - estimate_initial_heading(pred)
        if np.isfinite(yaw_delta) and pred.root_pos is not None and pred.num_frames > 0:
            rotate_motion_yaw(pred, yaw_delta, ref.root_pos[0] if ref.root_pos is not None else pred.root_pos[0])
            notes.append(f"Aligned prediction initial heading by {np.degrees(yaw_delta):.3f} deg.")
    if use_scale and alignment.get("scale", True):
        scale = estimate_reference_to_prediction_scale(ref, pred)
        if scale is not None and np.isfinite(scale) and scale > 1e-8:
            scale_motion_positions(ref, scale, origin=ref.root_pos[0] if ref.root_pos is not None and ref.num_frames else None)
            notes.append(f"Scaled reference keypoints by {scale:.6g} to match robot size.")
        else:
            notes.append("Scale alignment skipped because height/leg-length keypoints were unavailable.")
    return ref.finalize(), pred.finalize(), notes


def resample_to_fps(motion: MotionData, target_fps: float) -> MotionData:
    if motion.num_frames <= 1 or abs(float(motion.fps) - target_fps) < 1e-8:
        motion.fps = target_fps
        return motion
    duration = motion.duration
    n = max(2, int(round(duration * target_fps)) + 1)
    return resample_to_frame_count(motion, n, duration)


def resample_to_frame_count(motion: MotionData, frame_count: int, duration: float | None = None) -> MotionData:
    """Resample all frame-varying arrays to a fixed frame count."""
    if motion.num_frames == frame_count:
        return motion
    if motion.num_frames <= 1 or frame_count <= 1:
        return trim_motion(motion, min(motion.num_frames, frame_count))
    if duration is None:
        duration = motion.duration
    old_t = np.linspace(0.0, motion.duration, motion.num_frames)
    new_t = np.linspace(0.0, min(duration, motion.duration), frame_count)
    for attr in ["root_pos", "root_rot", "qpos", "dof_pos", "all_body_pos"]:
        value = getattr(motion, attr)
        if value is not None:
            new_value = _interp_array(value, old_t, new_t)
            if attr == "root_rot":
                new_value = quat_normalize(new_value)
            setattr(motion, attr, new_value)
    motion.keypoints = {key: _interp_array(value, old_t, new_t) for key, value in motion.keypoints.items()}
    motion.keypoint_quats = {key: quat_normalize(_interp_array(value, old_t, new_t)) for key, value in motion.keypoint_quats.items()}
    motion.contacts = {key: (_interp_array(value.astype(float), old_t, new_t) >= 0.5) for key, value in motion.contacts.items()}
    return motion.finalize()


def trim_motion(motion: MotionData, frame_count: int) -> MotionData:
    for attr in ["root_pos", "root_rot", "qpos", "dof_pos", "all_body_pos"]:
        value = getattr(motion, attr)
        if value is not None:
            setattr(motion, attr, np.asarray(value)[:frame_count])
    motion.keypoints = {key: np.asarray(value)[:frame_count] for key, value in motion.keypoints.items()}
    motion.keypoint_quats = {key: np.asarray(value)[:frame_count] for key, value in motion.keypoint_quats.items()}
    motion.contacts = {key: np.asarray(value)[:frame_count] for key, value in motion.contacts.items()}
    return motion.finalize()


def translate_motion(motion: MotionData, offset: np.ndarray) -> None:
    offset = np.asarray(offset, dtype=float)
    for attr in ["root_pos", "all_body_pos"]:
        value = getattr(motion, attr)
        if value is not None:
            setattr(motion, attr, np.asarray(value, dtype=float) + offset)
    motion.keypoints = {key: np.asarray(value, dtype=float) + offset for key, value in motion.keypoints.items()}
    if motion.qpos is not None and motion.qpos.shape[1] >= 3:
        motion.qpos[:, :3] += offset


def rotate_motion_yaw(motion: MotionData, yaw: float, origin: np.ndarray | None = None) -> None:
    origin = np.zeros(3, dtype=float) if origin is None else np.asarray(origin, dtype=float)
    for attr in ["root_pos", "all_body_pos"]:
        value = getattr(motion, attr)
        if value is not None:
            setattr(motion, attr, rotate_positions_yaw(np.asarray(value, dtype=float), yaw, origin))
    motion.keypoints = {key: rotate_positions_yaw(np.asarray(value, dtype=float), yaw, origin) for key, value in motion.keypoints.items()}
    yaw_quat = np.asarray([np.cos(yaw / 2.0), 0.0, 0.0, np.sin(yaw / 2.0)], dtype=float)
    if motion.root_rot is not None:
        motion.root_rot = quat_multiply(np.broadcast_to(yaw_quat, motion.root_rot.shape), motion.root_rot)
    motion.keypoint_quats = {
        key: quat_multiply(np.broadcast_to(yaw_quat, value.shape), value)
        for key, value in motion.keypoint_quats.items()
        if value.shape[-1] == 4
    }
    if motion.qpos is not None and motion.qpos.shape[1] >= 3:
        motion.qpos[:, :3] = rotate_positions_yaw(motion.qpos[:, :3], yaw, origin)
        if motion.qpos.shape[1] >= 7 and motion.root_rot is not None:
            motion.qpos[:, 3:7] = motion.root_rot


def scale_motion_positions(motion: MotionData, scale: float, origin: np.ndarray | None = None) -> None:
    origin = np.zeros(3, dtype=float) if origin is None else np.asarray(origin, dtype=float)
    for attr in ["root_pos", "all_body_pos"]:
        value = getattr(motion, attr)
        if value is not None:
            setattr(motion, attr, (np.asarray(value, dtype=float) - origin) * scale + origin)
    motion.keypoints = {
        key: (np.asarray(value, dtype=float) - origin) * scale + origin
        for key, value in motion.keypoints.items()
    }
    if motion.qpos is not None and motion.qpos.shape[1] >= 3:
        motion.qpos[:, :3] = (motion.qpos[:, :3] - origin) * scale + origin


def estimate_initial_heading(motion: MotionData) -> float:
    if motion.root_rot is not None and motion.root_rot.shape[0] > 0:
        return float(quat_to_yaw(motion.root_rot[0]))
    if motion.root_pos is not None and motion.root_pos.shape[0] > 1:
        delta = motion.root_pos[min(5, motion.root_pos.shape[0] - 1), :2] - motion.root_pos[0, :2]
        if np.linalg.norm(delta) > 1e-8:
            return float(np.arctan2(delta[1], delta[0]))
    return 0.0


def estimate_reference_to_prediction_scale(reference: MotionData, prediction: MotionData) -> float | None:
    ref_height = _body_height(reference)
    pred_height = _body_height(prediction)
    if ref_height is not None and pred_height is not None and ref_height > 1e-8:
        return pred_height / ref_height
    ref_leg = _leg_length(reference)
    pred_leg = _leg_length(prediction)
    if ref_leg is not None and pred_leg is not None and ref_leg > 1e-8:
        return pred_leg / ref_leg
    return None


def rotate_positions_yaw(value: np.ndarray, yaw: float, origin: np.ndarray) -> np.ndarray:
    c, s = float(np.cos(yaw)), float(np.sin(yaw))
    rot = np.asarray([[c, -s], [s, c]], dtype=float)
    out = np.asarray(value, dtype=float).copy()
    flat = out.reshape(-1, out.shape[-1])
    flat[:, :2] = (flat[:, :2] - origin[:2]) @ rot.T + origin[:2]
    return flat.reshape(out.shape)


def recompute_derivatives(motion: MotionData) -> Dict[str, np.ndarray | None]:
    dof = motion.dof_pos if motion.dof_pos is not None else (motion.qpos[:, 7:] if motion.qpos is not None and motion.qpos.shape[1] > 7 else motion.qpos)
    velocity = finite_difference(dof, motion.fps)
    acceleration = finite_difference(velocity, motion.fps) if velocity is not None else None
    jerk = finite_difference(acceleration, motion.fps) if acceleration is not None else None
    return {"position": dof, "velocity": velocity, "acceleration": acceleration, "jerk": jerk}


def _interp_array(value: Any, old_t: np.ndarray, new_t: np.ndarray) -> np.ndarray:
    arr = np.asarray(value)
    if arr.shape[0] != len(old_t):
        return arr
    flat = arr.reshape(arr.shape[0], -1).astype(float)
    out = np.empty((len(new_t), flat.shape[1]), dtype=float)
    for idx in range(flat.shape[1]):
        out[:, idx] = np.interp(new_t, old_t, flat[:, idx])
    return out.reshape((len(new_t),) + arr.shape[1:])


def _positive_duration(motion: MotionData) -> float:
    return motion.duration if motion.duration > 0.0 else max(motion.num_frames - 1, 0) / max(motion.fps, 1e-9)


def _body_height(motion: MotionData) -> float | None:
    head = motion.get_keypoint("head")
    left = motion.get_keypoint("left_foot")
    right = motion.get_keypoint("right_foot")
    if head is None or (left is None and right is None):
        return None
    feet = []
    if left is not None:
        feet.append(left[:, 2])
    if right is not None:
        feet.append(right[:, 2])
    foot_z = np.nanmin(np.stack(feet, axis=1), axis=1)
    values = head[:, 2] - foot_z
    return float(np.nanmedian(values)) if np.isfinite(values).any() else None


def _leg_length(motion: MotionData) -> float | None:
    pelvis = motion.get_keypoint("pelvis")
    left = motion.get_keypoint("left_foot")
    right = motion.get_keypoint("right_foot")
    if pelvis is None or (left is None and right is None):
        return None
    lengths = []
    if left is not None:
        lengths.append(np.linalg.norm(pelvis - left, axis=1))
    if right is not None:
        lengths.append(np.linalg.norm(pelvis - right, axis=1))
    values = np.concatenate(lengths)
    return float(np.nanmedian(values)) if np.isfinite(values).any() else None
