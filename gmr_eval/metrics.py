from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Tuple

import numpy as np

from .alignment import make_aligned_pair, recompute_derivatives, sync_motions
from .io import MotionData, finite_difference, quat_to_roll_pitch


def evaluate_motion_pair(reference: MotionData, prediction: MotionData, config: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, str]]:
    """Compute all available quality metrics for one motion-method pair."""
    raw_ref, raw_pred, sync_notes = sync_motions(reference, prediction, config)
    aligned_ref, aligned_pred, align_notes = make_aligned_pair(reference, prediction, config, use_scale=False)
    scaled_ref, scaled_pred, scale_notes = make_aligned_pair(reference, prediction, config, use_scale=True)
    names = list(config.get("compare_keypoints", []))
    unavailable: Dict[str, str] = {}

    raw_global, raw_kp, raw_unav = keypoint_position_error(raw_ref, raw_pred, names, root_relative=False)
    aligned_global, aligned_kp, aligned_unav = keypoint_position_error(aligned_ref, aligned_pred, names, root_relative=False)
    scale_global, scale_kp, scale_unav = keypoint_position_error(scaled_ref, scaled_pred, names, root_relative=False)
    root_relative, relative_kp, relative_unav = keypoint_position_error(scaled_ref, scaled_pred, names, root_relative=True)
    joint_angle, joint_rows, joint_unav = joint_or_bone_angle_error(scaled_ref, scaled_pred, names, config)
    foot_sliding, foot_unav = foot_sliding_metrics(raw_pred, config)
    penetration, penetration_unav = ground_penetration_metrics(raw_pred, config)
    collision, collision_rows, collision_unav = self_collision_metrics(raw_pred)
    jumps, jump_rows, jump_unav = sudden_jump_metrics(prediction, config)
    success, success_reasons = success_metrics(reference, prediction, penetration, collision, config)

    for block in [raw_unav, aligned_unav, scale_unav, relative_unav, joint_unav, foot_unav, penetration_unav, collision_unav, jump_unav]:
        unavailable.update(block)

    metrics: Dict[str, Any] = {
        "motion_name": reference.name,
        "method": prediction.method,
        "original_motion_path": reference.path,
        "pkl_path": prediction.path,
        "original_fps": reference.fps,
        "robot_fps": prediction.fps,
        "original_frames": reference.num_frames,
        "robot_frames": prediction.num_frames,
        "original_duration_s": reference.duration,
        "robot_duration_s": prediction.duration,
        "completion_fraction": _completion_fraction(reference, prediction),
        "success": int(success),
        "failure_reasons": "; ".join(success_reasons),
        "raw_global_error_mm": raw_global,
        "aligned_global_error_mm": aligned_global,
        "scale_aligned_global_error_mm": scale_global,
        "root_relative_error_mm": root_relative,
        "available_keypoint_count": int(sum(np.isfinite(v) for v in relative_kp.values())),
        "alignment_notes": " | ".join(dict.fromkeys(sync_notes + align_notes + scale_notes)),
        "warnings": "; ".join(reference.warnings + prediction.warnings),
        "unavailable_metrics": "; ".join(f"{k}: {v}" for k, v in sorted(unavailable.items())),
    }
    metrics.update(joint_angle)
    metrics.update(foot_sliding)
    metrics.update(penetration)
    metrics.update(collision)
    metrics.update(jumps)

    keypoint_rows = []
    for keypoint in names:
        keypoint_rows.append(
            {
                "motion_name": reference.name,
                "method": prediction.method,
                "keypoint": keypoint,
                "raw_global_error_mm": raw_kp.get(keypoint, np.nan),
                "aligned_global_error_mm": aligned_kp.get(keypoint, np.nan),
                "scale_aligned_global_error_mm": scale_kp.get(keypoint, np.nan),
                "root_relative_error_mm": relative_kp.get(keypoint, np.nan),
            }
        )
        metrics[f"{keypoint}_error_mm"] = relative_kp.get(keypoint, np.nan)

    for row in jump_rows:
        row.update({"motion_name": reference.name, "method": prediction.method})
    for row in collision_rows:
        row.update({"motion_name": reference.name, "method": prediction.method})
    return metrics, keypoint_rows, jump_rows, collision_rows, unavailable


def keypoint_position_error(reference: MotionData, prediction: MotionData, names: List[str], *, root_relative: bool) -> Tuple[float, Dict[str, float], Dict[str, str]]:
    """Compute mean point error in millimeters, optionally after root translation removal."""
    n = min(reference.num_frames, prediction.num_frames)
    per_keypoint: Dict[str, float] = {}
    unavailable: Dict[str, str] = {}
    distances = []

    ref_root = _root(reference, n)
    pred_root = _root(prediction, n)
    if root_relative and (ref_root is None or pred_root is None):
        unavailable["root_relative_error_mm"] = "root/pelvis keypoint missing in reference or prediction"

    for name in names:
        ref = reference.get_keypoint(name)
        pred = prediction.get_keypoint(name)
        if ref is None or pred is None:
            per_keypoint[name] = np.nan
            unavailable[f"{name}_error_mm"] = "keypoint missing in reference or prediction"
            continue
        ref = np.asarray(ref[:n], dtype=float)
        pred = np.asarray(pred[:n], dtype=float)
        if root_relative and ref_root is not None and pred_root is not None:
            ref = ref - ref_root
            pred = pred - pred_root
        dist = np.linalg.norm(pred - ref, axis=1) * 1000.0
        valid = np.isfinite(dist)
        if not valid.any():
            per_keypoint[name] = np.nan
            unavailable[f"{name}_error_mm"] = "keypoint trajectory contains no finite comparable values"
            continue
        per_keypoint[name] = float(np.nanmean(dist))
        distances.append(dist)

    if not distances:
        return np.nan, per_keypoint, unavailable
    stacked = np.stack(distances, axis=1)
    return float(np.nanmean(stacked)), per_keypoint, unavailable


def joint_or_bone_angle_error(reference: MotionData, prediction: MotionData, names: List[str], config: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, str]]:
    """Compute mapped joint angle error or fallback bone orientation error."""
    unavailable: Dict[str, str] = {}
    rows: List[Dict[str, Any]] = []
    ref_dof = reference.dof_pos
    pred_dof = prediction.dof_pos
    if ref_dof is not None and pred_dof is not None:
        n = min(ref_dof.shape[0], pred_dof.shape[0])
        width = min(ref_dof.shape[1], pred_dof.shape[1])
        if n > 0 and width > 0:
            diff = np.abs(pred_dof[:n, :width] - ref_dof[:n, :width])
            mean_rad = float(np.nanmean(diff))
            joint_names = prediction.joint_names[:width] if prediction.joint_names else [f"joint_{i}" for i in range(width)]
            for idx, name in enumerate(joint_names):
                rows.append({"joint_name": name, "joint_angle_error_rad": float(np.nanmean(diff[:, idx]))})
            return {
                "joint_angle_error_rad": mean_rad,
                "joint_angle_error_deg": float(np.degrees(mean_rad)),
                "bone_orientation_error_deg": np.nan,
                "angle_error_type": "mapped_joint_angle",
            }, rows, unavailable

    segments = config.get("bone_segments") or [
        ["pelvis", "left_knee"],
        ["left_knee", "left_foot"],
        ["pelvis", "right_knee"],
        ["right_knee", "right_foot"],
        ["left_shoulder", "left_elbow"],
        ["left_elbow", "left_hand"],
        ["right_shoulder", "right_elbow"],
        ["right_elbow", "right_hand"],
        ["pelvis", "torso"],
        ["torso", "head"],
    ]
    angles = []
    for start, end in segments:
        ref_a, ref_b = reference.get_keypoint(start), reference.get_keypoint(end)
        pred_a, pred_b = prediction.get_keypoint(start), prediction.get_keypoint(end)
        if ref_a is None or ref_b is None or pred_a is None or pred_b is None:
            rows.append({"bone": f"{start}->{end}", "bone_orientation_error_deg": np.nan})
            continue
        n = min(len(ref_a), len(ref_b), len(pred_a), len(pred_b))
        angle = _vector_angle_deg(ref_b[:n] - ref_a[:n], pred_b[:n] - pred_a[:n])
        rows.append({"bone": f"{start}->{end}", "bone_orientation_error_deg": _safe_mean(angle)})
        if np.isfinite(angle).any():
            angles.append(angle)
    if not angles:
        unavailable["bone_orientation_error_deg"] = "no comparable bone segments available"
        return {
            "joint_angle_error_rad": np.nan,
            "joint_angle_error_deg": np.nan,
            "bone_orientation_error_deg": np.nan,
            "angle_error_type": "unavailable",
        }, rows, unavailable
    merged = np.concatenate(angles)
    return {
        "joint_angle_error_rad": np.nan,
        "joint_angle_error_deg": np.nan,
        "bone_orientation_error_deg": _safe_mean(merged),
        "angle_error_type": "bone_orientation_fallback",
    }, rows, unavailable


def foot_sliding_metrics(prediction: MotionData, config: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Compute horizontal sliding while each foot is in contact."""
    floor = float(config.get("floor_height", 0.0))
    contact_height = float(config.get("thresholds", {}).get("foot_contact_height_m", 0.04))
    metrics: Dict[str, Any] = {}
    unavailable: Dict[str, str] = {}
    total_distance = 0.0
    total_contact_steps = 0
    total_contact_velocity = 0.0
    for side in ["left", "right"]:
        foot = prediction.get_keypoint(f"{side}_foot")
        if foot is None:
            metrics[f"{side}_foot_sliding_m"] = np.nan
            unavailable[f"{side}_foot_sliding_m"] = f"{side}_foot keypoint missing"
            continue
        foot = np.asarray(foot, dtype=float)
        contact = prediction.contacts.get(f"{side}_foot")
        if contact is None or len(contact) != len(foot) or not np.asarray(contact).any():
            contact = foot[:, 2] <= floor + contact_height
        else:
            contact = np.asarray(contact, dtype=bool)
        if len(foot) < 2:
            slide = np.asarray([], dtype=float)
            contact_step = np.asarray([], dtype=bool)
        else:
            step_xy = np.linalg.norm(np.diff(foot[:, :2], axis=0), axis=1)
            contact_step = contact[:-1] & contact[1:]
            slide = np.where(contact_step, step_xy, 0.0)
        distance = float(np.nansum(slide))
        metrics[f"{side}_foot_sliding_m"] = distance
        total_distance += distance
        if len(slide):
            total_contact_steps += int(np.sum(contact_step))
            total_contact_velocity += float(np.nansum(slide * prediction.fps))
    metrics["total_foot_sliding_m"] = total_distance if np.isfinite(total_distance) else np.nan
    metrics["mean_foot_sliding_velocity_mps"] = total_contact_velocity / total_contact_steps if total_contact_steps > 0 else 0.0
    return metrics, unavailable


def ground_penetration_metrics(prediction: MotionData, config: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Compute foot/all-body penetration below the configured floor height."""
    floor = float(config.get("floor_height", 0.0))
    unavailable: Dict[str, str] = {}
    foot_depths = []
    metrics: Dict[str, Any] = {}
    for side in ["left", "right"]:
        foot = prediction.get_keypoint(f"{side}_foot")
        if foot is None:
            metrics[f"{side}_foot_penetration_m"] = np.nan
            unavailable[f"{side}_foot_penetration_m"] = f"{side}_foot keypoint missing"
            continue
        depth = np.maximum(0.0, floor - np.asarray(foot, dtype=float)[:, 2])
        metrics[f"{side}_foot_penetration_m"] = float(np.nanmax(depth)) if depth.size else np.nan
        foot_depths.append(depth)

    if prediction.all_body_pos is not None and bool(config.get("use_all_bodies_for_penetration", True)):
        depths = np.maximum(0.0, floor - np.asarray(prediction.all_body_pos, dtype=float)[..., 2])
        source = "all_body"
    elif foot_depths:
        depths = np.stack(foot_depths, axis=1)
        source = "feet_only"
    else:
        depths = np.asarray([], dtype=float)
        source = "unavailable"
        unavailable["ground_penetration"] = "no foot/body positions available"

    if depths.size:
        per_frame = np.nanmax(depths.reshape(depths.shape[0], -1), axis=1)
        metrics["max_ground_penetration_m"] = float(np.nanmax(depths))
        metrics["mean_ground_penetration_m"] = float(np.nanmean(depths))
        metrics["penetration_frame_ratio"] = float(np.mean(per_frame > 0.0))
    else:
        metrics["max_ground_penetration_m"] = np.nan
        metrics["mean_ground_penetration_m"] = np.nan
        metrics["penetration_frame_ratio"] = np.nan
    metrics["ground_penetration_source"] = source
    return metrics, unavailable


def self_collision_metrics(prediction: MotionData) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, str]]:
    """Return self-collision counts if MuJoCo contact data was available."""
    count = prediction.raw.get("self_collision_count", np.nan)
    ratio = prediction.raw.get("self_collision_frame_ratio", np.nan)
    pairs = prediction.raw.get("self_collision_pairs", [])
    unavailable: Dict[str, str] = {}
    if count is None or not np.isfinite(float(count)):
        unavailable["self_collision_count"] = "MuJoCo contact/self-collision information unavailable"
        count = np.nan
        ratio = np.nan
    rows = []
    if isinstance(pairs, list):
        for pair in pairs:
            if isinstance(pair, dict):
                rows.append(
                    {
                        "body_a": pair.get("body_a", ""),
                        "body_b": pair.get("body_b", ""),
                        "count": pair.get("count", 0),
                    }
                )
    return {
        "self_collision_count": count,
        "self_collision_frame_ratio": ratio,
        "top_self_collision_pair": f"{rows[0].get('body_a')} vs {rows[0].get('body_b')}" if rows else "",
    }, rows, unavailable


def sudden_jump_metrics(prediction: MotionData, config: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, str]]:
    """Compute joint velocity, acceleration, jerk, and sudden jump counts."""
    dof = prediction.dof_pos if prediction.dof_pos is not None else (prediction.qpos[:, 7:] if prediction.qpos is not None and prediction.qpos.shape[1] > 7 else prediction.qpos)
    unavailable: Dict[str, str] = {}
    if dof is None or dof.shape[0] < 2:
        unavailable["sudden_jump_count"] = "dof_pos/qpos unavailable or too short"
        return {
            "mean_joint_velocity": np.nan,
            "max_joint_velocity": np.nan,
            "mean_joint_acceleration": np.nan,
            "max_joint_acceleration": np.nan,
            "mean_joint_jerk": np.nan,
            "max_joint_jerk": np.nan,
            "sudden_jump_count": np.nan,
            "top_jump_joints": "",
        }, [], unavailable
    dof = np.asarray(dof, dtype=float)
    fps = max(float(prediction.fps), 1e-9)
    velocity = np.diff(dof, axis=0) * fps
    acceleration = np.diff(velocity, axis=0) * fps if velocity.shape[0] >= 2 else np.zeros((0, dof.shape[1]))
    jerk = np.diff(acceleration, axis=0) * fps if acceleration.shape[0] >= 2 else np.zeros((0, dof.shape[1]))
    abs_velocity = np.abs(velocity)
    std_factor = float(config.get("thresholds", {}).get("sudden_jump_std_factor", 3.0))
    abs_threshold = float(config.get("thresholds", {}).get("sudden_jump_abs_velocity", np.inf))
    adaptive = np.nanmean(abs_velocity, axis=0) + std_factor * np.nanstd(abs_velocity, axis=0)
    thresholds = np.minimum(adaptive, abs_threshold)
    jump_mask = abs_velocity > thresholds.reshape(1, -1)
    per_joint_counts = np.sum(jump_mask, axis=0)
    joint_names = prediction.joint_names[: dof.shape[1]] if prediction.joint_names else [f"joint_{i}" for i in range(dof.shape[1])]
    rows = []
    for idx in np.argsort(per_joint_counts)[::-1][:10]:
        rows.append(
            {
                "joint_name": joint_names[idx] if idx < len(joint_names) else f"joint_{idx}",
                "sudden_jump_count": int(per_joint_counts[idx]),
                "mean_abs_velocity": float(np.nanmean(abs_velocity[:, idx])),
                "max_abs_velocity": float(np.nanmax(abs_velocity[:, idx])),
                "threshold_used": float(thresholds[idx]),
            }
        )
    return {
        "mean_joint_velocity": float(np.nanmean(np.abs(velocity))),
        "max_joint_velocity": float(np.nanmax(np.abs(velocity))),
        "mean_joint_acceleration": float(np.nanmean(np.abs(acceleration))) if acceleration.size else 0.0,
        "max_joint_acceleration": float(np.nanmax(np.abs(acceleration))) if acceleration.size else 0.0,
        "mean_joint_jerk": float(np.nanmean(np.abs(jerk))) if jerk.size else 0.0,
        "max_joint_jerk": float(np.nanmax(np.abs(jerk))) if jerk.size else 0.0,
        "sudden_jump_count": int(np.sum(np.any(jump_mask, axis=1))),
        "top_jump_joints": "; ".join(f"{row['joint_name']}({row['sudden_jump_count']})" for row in rows[:10]),
    }, rows, unavailable


def success_metrics(reference: MotionData, prediction: MotionData, penetration: Dict[str, Any], collision: Dict[str, Any], config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Classify one retargeted motion as successful or failed."""
    thresholds = config.get("success_thresholds", {})
    reasons: List[str] = []
    completion = _completion_fraction(reference, prediction)
    if np.isfinite(completion) and completion < float(thresholds.get("min_completion_fraction", 0.9)):
        reasons.append(f"early_stop completion_fraction={completion:.3f}")

    root = prediction.root_pos
    if root is not None and len(root):
        min_root = float(np.nanmin(root[:, 2]))
        if min_root < float(thresholds.get("min_root_height_m", 0.45)):
            reasons.append(f"low_root_height={min_root:.3f}m")

    if prediction.root_rot is not None and len(prediction.root_rot):
        roll, pitch = quat_to_roll_pitch(prediction.root_rot)
        max_tilt = float(np.degrees(np.nanmax(np.maximum(np.abs(roll), np.abs(pitch)))))
        if max_tilt > float(thresholds.get("max_abs_roll_pitch_deg", 60.0)):
            reasons.append(f"large_roll_pitch={max_tilt:.1f}deg")

    max_pen = penetration.get("max_ground_penetration_m", np.nan)
    if np.isfinite(_as_float(max_pen)) and _as_float(max_pen) > float(thresholds.get("max_ground_penetration_m", 0.08)):
        reasons.append(f"ground_penetration={_as_float(max_pen):.3f}m")

    col_count = collision.get("self_collision_count", np.nan)
    if np.isfinite(_as_float(col_count)) and _as_float(col_count) > float(thresholds.get("max_self_collision_count", 20)):
        reasons.append(f"self_collision_count={int(_as_float(col_count))}")

    for key in ["fall", "fell", "terminate", "terminated", "done"]:
        value = prediction.raw.get(key)
        if value is not None and _any_true(value):
            reasons.append(f"status_{key}=true")
    if prediction.raw.get("success") is not None and not _all_true(prediction.raw.get("success")):
        reasons.append("status_success=false")
    return len(reasons) == 0, reasons


def add_overall_scores(rows: List[Dict[str, Any]], config: Dict[str, Any]) -> None:
    """Add normalized weighted overall_score to every per-motion row."""
    weights = config.get("overall_score_weights", {})
    metric_specs = {
        "success": ("success", False),
        "root_relative_error": ("root_relative_error_mm", True),
        "global_error": ("aligned_global_error_mm", True),
        "foot_sliding": ("total_foot_sliding_m", True),
        "ground_penetration": ("max_ground_penetration_m", True),
        "sudden_jumps": ("sudden_jump_count", True),
        "self_collision": ("self_collision_count", True),
    }
    normalized: Dict[str, List[float]] = {}
    for weight_name, (column, inverse) in metric_specs.items():
        values = np.asarray([_as_float(row.get(column, np.nan)) for row in rows], dtype=float)
        finite = np.isfinite(values)
        out = np.full(len(rows), np.nan, dtype=float)
        if finite.any():
            lo, hi = float(np.nanmin(values[finite])), float(np.nanmax(values[finite]))
            if abs(hi - lo) < 1e-12:
                out[finite] = 1.0
            else:
                scaled = (values[finite] - lo) / (hi - lo)
                out[finite] = 1.0 - scaled if inverse else scaled
        normalized[weight_name] = out.tolist()
        for row, value in zip(rows, out):
            row[f"normalized_{weight_name}"] = value

    for idx, row in enumerate(rows):
        numerator = 0.0
        denominator = 0.0
        for weight_name, weight in weights.items():
            value = normalized.get(weight_name, [np.nan] * len(rows))[idx]
            if np.isfinite(value):
                numerator += float(weight) * float(value)
                denominator += float(weight)
        row["overall_score"] = numerator / denominator if denominator > 0 else np.nan


def aggregate_summary(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate per-motion rows into one row per method."""
    methods = sorted({str(row.get("method", "")) for row in rows if row.get("method")})
    numeric_columns = [
        "success",
        "overall_score",
        "raw_global_error_mm",
        "aligned_global_error_mm",
        "scale_aligned_global_error_mm",
        "root_relative_error_mm",
        "bone_orientation_error_deg",
        "joint_angle_error_deg",
        "total_foot_sliding_m",
        "mean_foot_sliding_velocity_mps",
        "max_ground_penetration_m",
        "mean_ground_penetration_m",
        "self_collision_count",
        "sudden_jump_count",
        "mean_joint_velocity",
        "mean_joint_acceleration",
        "mean_joint_jerk",
    ]
    summary = []
    for method in methods:
        subset = [row for row in rows if row.get("method") == method]
        out = {"method": method, "motion_count": len(subset), "success_rate": _safe_mean([row.get("success", np.nan) for row in subset])}
        for column in numeric_columns:
            values = [_as_float(row.get(column, np.nan)) for row in subset]
            out[f"mean_{column}"] = _safe_mean(values)
        summary.append(out)
    summary.sort(key=lambda row: (-_as_float(row.get("mean_overall_score", np.nan)), row["method"]))
    return summary


def _root(motion: MotionData, n: int) -> np.ndarray | None:
    root = motion.get_keypoint("root")
    if root is None:
        root = motion.get_keypoint("pelvis")
    return None if root is None else np.asarray(root[:n], dtype=float)


def _vector_angle_deg(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    an = np.linalg.norm(a, axis=1)
    bn = np.linalg.norm(b, axis=1)
    dot = np.sum(a * b, axis=1)
    denom = an * bn
    cos = np.divide(dot, denom, out=np.full_like(dot, np.nan, dtype=float), where=denom > 1e-12)
    return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))


def _completion_fraction(reference: MotionData, prediction: MotionData) -> float:
    if reference.duration <= 1e-12:
        return np.nan
    return float(prediction.duration / reference.duration)


def _safe_mean(values: Any) -> float:
    arr = np.asarray(values, dtype=float)
    return float(np.nanmean(arr)) if arr.size and np.isfinite(arr).any() else np.nan


def _as_float(value: Any) -> float:
    try:
        return float(np.asarray(value).reshape(-1)[0])
    except Exception:
        return np.nan


def _any_true(value: Any) -> bool:
    try:
        arr = np.asarray(value)
        return bool(np.any(arr.astype(bool)))
    except Exception:
        return bool(value)


def _all_true(value: Any) -> bool:
    try:
        arr = np.asarray(value)
        return bool(np.all(arr.astype(bool)))
    except Exception:
        return bool(value)
