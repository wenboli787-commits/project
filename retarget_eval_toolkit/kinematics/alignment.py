from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np

from loaders.common_motion import MotionData, finite_difference


def prepare_pair(reference: MotionData, prediction: MotionData, config: Dict[str, Any], *, mode: str = "full") -> Tuple[MotionData, MotionData, List[str]]:
    """Return aligned copies of reference and prediction.

    Modes:
    - `raw`: time resampling/trimming only.
    - `aligned`: time + root translation + initial yaw.
    - `full`: aligned + scale normalization.
    """
    ref = reference.copy()
    pred = prediction.copy()
    notes: List[str] = []
    target_fps = float(config.get("evaluation", {}).get("target_fps", config.get("target_fps", 30.0)))
    ref = resample_motion_to_fps(ref, target_fps)
    pred = resample_motion_to_fps(pred, target_fps)
    n = min(ref.num_frames, pred.num_frames)
    ref = trim_motion(ref, n)
    pred = trim_motion(pred, n)
    notes.append(f"Resampled/trimmed to {target_fps:g} fps and {n} frames.")

    eval_cfg = config.get("evaluation", {})
    if mode in {"aligned", "full"} and eval_cfg.get("align_root_translation", True):
        if ref.root_pos is not None and pred.root_pos is not None and n > 0:
            translate_motion(pred, ref.root_pos[0] - pred.root_pos[0])
            notes.append("Aligned prediction initial root translation to reference.")
    if mode in {"aligned", "full"} and eval_cfg.get("align_initial_yaw", True):
        yaw = estimate_initial_yaw(ref) - estimate_initial_yaw(pred)
        if np.isfinite(yaw) and pred.root_pos is not None and n > 0:
            rotate_motion_yaw(pred, yaw, pred.root_pos[0].copy())
            notes.append(f"Aligned prediction initial yaw by {np.rad2deg(yaw):.3f} deg.")
    if mode == "full" and eval_cfg.get("normalize_scale", True):
        scale = estimate_scale(ref, pred)
        if scale is not None and np.isfinite(scale) and scale > 1e-8:
            scale_motion_positions(ref, scale)
            notes.append(f"Scaled reference positions by {scale:.6g}.")
        else:
            notes.append("Scale normalization skipped because height/leg-length keypoints were unavailable.")
    ref.ensure_keypoint_aliases()
    pred.ensure_keypoint_aliases()
    return ref, pred, notes


def resample_motion_to_fps(motion: MotionData, target_fps: float) -> MotionData:
    """Resample all numeric frame arrays to target FPS using linear interpolation."""
    if motion.num_frames <= 1 or abs(motion.fps - target_fps) < 1e-8:
        motion.fps = target_fps
        return motion
    duration = (motion.num_frames - 1) / float(motion.fps)
    old_t = np.linspace(0.0, duration, motion.num_frames)
    new_n = max(2, int(round(duration * target_fps)) + 1)
    new_t = np.linspace(0.0, duration, new_n)
    for attr in ["root_pos", "root_rot", "joint_pos", "joint_rot", "qpos", "qvel", "qacc", "dof_pos", "left_foot_pos", "right_foot_pos", "left_hand_pos", "right_hand_pos", "head_pos", "pelvis_pos"]:
        setattr(motion, attr, _interp(getattr(motion, attr), old_t, new_t))
    motion.keypoints = {k: _interp(v, old_t, new_t) for k, v in motion.keypoints.items()}
    motion.keypoint_quats = {k: _interp(v, old_t, new_t) for k, v in motion.keypoint_quats.items()}
    if motion.contacts:
        motion.contacts = {k: (_interp(np.asarray(v, dtype=float), old_t, new_t) >= 0.5) for k, v in motion.contacts.items()}
    motion.fps = target_fps
    motion.refresh_num_frames()
    motion.infer_missing_derivatives()
    return motion


def trim_motion(motion: MotionData, n: int) -> MotionData:
    """Trim every frame-varying field to length n."""
    for attr in ["root_pos", "root_rot", "joint_pos", "joint_rot", "qpos", "qvel", "qacc", "dof_pos", "left_foot_pos", "right_foot_pos", "left_hand_pos", "right_hand_pos", "head_pos", "pelvis_pos"]:
        value = getattr(motion, attr)
        if value is not None:
            setattr(motion, attr, np.asarray(value)[:n])
    motion.keypoints = {k: np.asarray(v)[:n] for k, v in motion.keypoints.items()}
    motion.keypoint_quats = {k: np.asarray(v)[:n] for k, v in motion.keypoint_quats.items()}
    if motion.contacts:
        motion.contacts = {k: np.asarray(v)[:n] for k, v in motion.contacts.items()}
    motion.refresh_num_frames()
    return motion


def translate_motion(motion: MotionData, offset: np.ndarray) -> None:
    """Translate every position trajectory by an offset."""
    for attr in ["root_pos", "joint_pos", "left_foot_pos", "right_foot_pos", "left_hand_pos", "right_hand_pos", "head_pos", "pelvis_pos"]:
        value = getattr(motion, attr)
        if value is not None:
            setattr(motion, attr, np.asarray(value) + offset)
    motion.keypoints = {k: np.asarray(v) + offset for k, v in motion.keypoints.items()}
    if motion.qpos is not None and motion.qpos.shape[1] >= 3:
        motion.qpos[:, :3] += offset


def rotate_motion_yaw(motion: MotionData, yaw: float, origin: np.ndarray) -> None:
    """Rotate position trajectories around world Z by yaw."""
    for attr in ["root_pos", "joint_pos", "left_foot_pos", "right_foot_pos", "left_hand_pos", "right_hand_pos", "head_pos", "pelvis_pos"]:
        value = getattr(motion, attr)
        if value is not None:
            setattr(motion, attr, _rotate_positions(np.asarray(value), yaw, origin))
    motion.keypoints = {k: _rotate_positions(np.asarray(v), yaw, origin) for k, v in motion.keypoints.items()}
    if motion.qpos is not None and motion.qpos.shape[1] >= 3:
        motion.qpos[:, :3] = _rotate_positions(motion.qpos[:, :3], yaw, origin)
    motion.root_pos = motion.root_pos if motion.root_pos is not None else motion.keypoints.get("root")
    if motion.root_pos is not None:
        motion.qvel = finite_difference(motion.qpos, motion.fps) if motion.qpos is not None else motion.qvel


def estimate_initial_yaw(motion: MotionData) -> float:
    """Estimate initial yaw from root quaternion or first root displacement."""
    if motion.root_rot is not None and len(motion.root_rot) > 0:
        q = np.asarray(motion.root_rot[0], dtype=float)
        w, x, y, z = q / max(np.linalg.norm(q), 1e-12)
        return float(np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))
    if motion.root_pos is not None and len(motion.root_pos) > 1:
        delta = motion.root_pos[min(5, len(motion.root_pos) - 1), :2] - motion.root_pos[0, :2]
        if np.linalg.norm(delta) > 1e-8:
            return float(np.arctan2(delta[1], delta[0]))
    return 0.0


def estimate_scale(reference: MotionData, prediction: MotionData) -> float | None:
    """Estimate scale factor from height or leg length as prediction/reference."""
    ref_h = _height(reference)
    pred_h = _height(prediction)
    if ref_h is not None and pred_h is not None and ref_h > 1e-8:
        return pred_h / ref_h
    ref_l = _leg_length(reference)
    pred_l = _leg_length(prediction)
    if ref_l is not None and pred_l is not None and ref_l > 1e-8:
        return pred_l / ref_l
    return None


def scale_motion_positions(motion: MotionData, scale: float) -> None:
    """Scale all positions in a motion."""
    for attr in ["root_pos", "joint_pos", "left_foot_pos", "right_foot_pos", "left_hand_pos", "right_hand_pos", "head_pos", "pelvis_pos"]:
        value = getattr(motion, attr)
        if value is not None:
            setattr(motion, attr, np.asarray(value) * scale)
    motion.keypoints = {k: np.asarray(v) * scale for k, v in motion.keypoints.items()}
    if motion.qpos is not None and motion.qpos.shape[1] >= 3:
        motion.qpos[:, :3] *= scale


def _height(motion: MotionData) -> float | None:
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
    return float(np.nanmedian(head[:, 2] - foot_z))


def _leg_length(motion: MotionData) -> float | None:
    root = motion.get_keypoint("pelvis")
    left = motion.get_keypoint("left_foot")
    right = motion.get_keypoint("right_foot")
    if root is None or (left is None and right is None):
        return None
    lengths = []
    if left is not None:
        lengths.append(np.linalg.norm(root - left, axis=1))
    if right is not None:
        lengths.append(np.linalg.norm(root - right, axis=1))
    return float(np.nanmedian(np.concatenate(lengths)))


def _interp(value: Any, old_t: np.ndarray, new_t: np.ndarray) -> Any:
    if value is None:
        return None
    arr = np.asarray(value)
    if arr.shape[0] != len(old_t):
        return value
    flat = arr.reshape(arr.shape[0], -1).astype(float)
    out = np.empty((len(new_t), flat.shape[1]), dtype=float)
    for i in range(flat.shape[1]):
        out[:, i] = np.interp(new_t, old_t, flat[:, i])
    return out.reshape((len(new_t),) + arr.shape[1:])


def _rotate_positions(value: np.ndarray, yaw: float, origin: np.ndarray | None = None) -> np.ndarray:
    origin = np.zeros(3) if origin is None else np.asarray(origin)
    c, s = np.cos(yaw), np.sin(yaw)
    rot = np.asarray([[c, -s], [s, c]], dtype=float)
    out = value.copy()
    flat = out.reshape(-1, out.shape[-1])
    flat[:, :2] = (flat[:, :2] - origin[:2]) @ rot.T + origin[:2]
    return flat.reshape(out.shape)

