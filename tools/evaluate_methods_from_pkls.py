#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
import pickle
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


DEFAULT_METHODS = {
    "Direct Mapping": r"D:\GMR_WORK\GMR\outputs\final product\pkl direct",
    "Basic IK": r"D:\GMR_WORK\GMR\outputs\final product\pkl Basic IK",
    "GMR": r"D:\GMR_WORK\GMR\outputs\final product\pkl",
}

JOINT_NAMES_29 = [
    "left_hip_pitch_joint",
    "left_hip_roll_joint",
    "left_hip_yaw_joint",
    "left_knee_joint",
    "left_ankle_pitch_joint",
    "left_ankle_roll_joint",
    "right_hip_pitch_joint",
    "right_hip_roll_joint",
    "right_hip_yaw_joint",
    "right_knee_joint",
    "right_ankle_pitch_joint",
    "right_ankle_roll_joint",
    "waist_yaw_joint",
    "waist_roll_joint",
    "waist_pitch_joint",
    "left_shoulder_pitch_joint",
    "left_shoulder_roll_joint",
    "left_shoulder_yaw_joint",
    "left_elbow_joint",
    "left_wrist_roll_joint",
    "left_wrist_pitch_joint",
    "left_wrist_yaw_joint",
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_joint",
    "right_wrist_roll_joint",
    "right_wrist_pitch_joint",
    "right_wrist_yaw_joint",
]


def main() -> None:
    args = build_parser().parse_args()
    method_dirs = {
        "Direct Mapping": Path(args.direct_dir).expanduser() if args.direct_dir else Path(DEFAULT_METHODS["Direct Mapping"]),
        "Basic IK": Path(args.basic_ik_dir).expanduser() if args.basic_ik_dir else Path(DEFAULT_METHODS["Basic IK"]),
        "GMR": Path(args.gmr_dir).expanduser() if args.gmr_dir else Path(DEFAULT_METHODS["GMR"]),
    }
    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    files_by_method = discover_method_files(method_dirs, args.name_regex)
    motions = sorted(set().union(*(set(items) for items in files_by_method.values()))) if files_by_method else []
    missing_rows = missing_method_rows(motions, files_by_method)

    per_motion_rows: List[Dict[str, Any]] = []
    loaded: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for method, by_motion in files_by_method.items():
        loaded[method] = {}
        for motion, path in by_motion.items():
            data = load_pkl(path)
            loaded[method][motion] = data
            per_motion_rows.append(
                compute_absolute_metrics(
                    motion=motion,
                    method=method,
                    path=path,
                    data=data,
                    floor_height=args.floor_height,
                    foot_contact_height=args.foot_contact_height,
                    root_height_threshold=args.root_height_threshold,
                    penetration_threshold=args.penetration_threshold,
                    self_collision_threshold=args.self_collision_threshold,
                    use_status_flags=args.use_status_flags,
                )
            )

    pairwise_rows = compute_reference_errors(loaded, args.reference_method)
    inject_reference_errors(per_motion_rows, pairwise_rows)
    summary_rows = summarize_methods(per_motion_rows)

    write_csv(output_dir / "per_motion_pkl_metrics.csv", per_motion_rows)
    write_csv(output_dir / "summary_pkl_metrics.csv", summary_rows)
    write_csv(output_dir / "pairwise_reference_errors.csv", pairwise_rows)
    write_csv(output_dir / "missing_pkl_files.csv", missing_rows, ["motion", "method", "detail"])
    write_report(output_dir / "report_pkl_metrics.md", summary_rows, per_motion_rows, pairwise_rows, missing_rows, args.reference_method)

    print_result(summary_rows, pairwise_rows, missing_rows, output_dir, args.reference_method)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate retargeting methods directly from generated PKL files.")
    parser.add_argument("--direct_dir", default=DEFAULT_METHODS["Direct Mapping"])
    parser.add_argument("--basic_ik_dir", default=DEFAULT_METHODS["Basic IK"])
    parser.add_argument("--gmr_dir", default=DEFAULT_METHODS["GMR"])
    parser.add_argument("--output_dir", default=r"D:\GMR_WORK\GMR\outputs\pkl_method_evaluation")
    parser.add_argument("--name_regex", default=r"^([0-9]+_[0-9]+)")
    parser.add_argument("--reference_method", default="GMR", help="Reference method for global/relative body error from PKL only.")
    parser.add_argument("--floor_height", type=float, default=0.0)
    parser.add_argument("--foot_contact_height", type=float, default=0.04)
    parser.add_argument("--root_height_threshold", type=float, default=0.45)
    parser.add_argument("--penetration_threshold", type=float, default=0.08)
    parser.add_argument("--self_collision_threshold", type=int, default=20)
    parser.add_argument(
        "--use_status_flags",
        action="store_true",
        help="Use PKL fall/terminated flags in success. Default is off because some regenerated GMR PKLs mark these fields unexpectedly.",
    )
    return parser


def discover_method_files(method_dirs: Dict[str, Path], pattern: str) -> Dict[str, Dict[str, Path]]:
    out: Dict[str, Dict[str, Path]] = {}
    for method, directory in method_dirs.items():
        if not directory.exists():
            out[method] = {}
            continue
        files = sorted(directory.glob("*.pkl"))
        out[method] = {motion_id(path, pattern): path for path in files}
    return out


def missing_method_rows(motions: List[str], files_by_method: Dict[str, Dict[str, Path]]) -> List[Dict[str, str]]:
    rows = []
    for motion in motions:
        for method, items in files_by_method.items():
            if motion not in items:
                rows.append({"motion": motion, "method": method, "detail": "missing pkl for this method"})
    for method, items in files_by_method.items():
        if not items:
            rows.append({"motion": "", "method": method, "detail": "method directory has no pkl files"})
    return rows


def load_pkl(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        data = pickle.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected dict PKL: {path}")
    return data


def compute_absolute_metrics(
    motion: str,
    method: str,
    path: Path,
    data: Dict[str, Any],
    floor_height: float,
    foot_contact_height: float,
    root_height_threshold: float,
    penetration_threshold: float,
    self_collision_threshold: int,
    use_status_flags: bool,
) -> Dict[str, Any]:
    fps = scalar(data.get("fps"), fallback_from_dt(data.get("dt"), 30.0))
    qpos = array_or_none(data.get("qpos"))
    root_pos = array_or_none(data.get("root_pos"))
    root_rot = first_array(data, ["root_rot", "root_quat"])
    dof_pos = array_or_none(data.get("dof_pos"))
    if dof_pos is None and qpos is not None and qpos.ndim == 2 and qpos.shape[1] > 7:
        dof_pos = qpos[:, 7:]
    body_pos = first_array(data, ["body_pos", "local_body_pos"])
    body_names = list(data.get("body_names") or data.get("link_body_list") or [])
    foot_pos = array_or_none(data.get("foot_pos"))
    contacts = array_or_none(data.get("contacts"))
    self_collision = data.get("self_collision")
    fall = data.get("fall")
    terminated = data.get("terminated")
    frames = first_frame_count([body_pos, foot_pos, dof_pos, root_pos, qpos])

    smooth = joint_jump_metrics(dof_pos, fps, data)
    foot = foot_quality_metrics(foot_pos, contacts, fps, floor_height, foot_contact_height)
    penetration = penetration_metrics(foot_pos, body_pos, body_names, floor_height)
    self_collision_available = bool_available(self_collision)
    collision_count = bool_count(self_collision) if self_collision_available else np.nan
    fall_count = bool_count(fall)
    terminated_count = bool_count(terminated)
    root_min = safe_min(root_pos[:, 2]) if root_pos is not None and root_pos.ndim == 2 and root_pos.shape[1] >= 3 else np.nan
    success, failure_reasons = success_from_metrics(
        root_min=root_min,
        max_penetration=penetration["max_ground_penetration_m"],
        self_collision_count=collision_count,
        fall_count=fall_count,
        terminated_count=terminated_count,
        root_height_threshold=root_height_threshold,
        penetration_threshold=penetration_threshold,
        self_collision_threshold=self_collision_threshold,
        use_status_flags=use_status_flags,
    )

    return {
        "motion": motion,
        "method": method,
        "pkl_path": str(path),
        "frames": frames,
        "fps": fps,
        "duration_s": duration(frames, fps),
        "qpos_shape": shape_text(qpos),
        "body_pos_shape": shape_text(body_pos),
        "foot_pos_shape": shape_text(foot_pos),
        "contacts_shape": shape_text(contacts),
        "success": int(success),
        "failure_reasons": "; ".join(failure_reasons),
        "root_min_height_m": root_min,
        "fall_count": fall_count,
        "terminated_count": terminated_count,
        "self_collision_count": collision_count,
        "self_collision_available": int(self_collision_available),
        "status_flags_used_for_success": bool(use_status_flags),
        **smooth,
        **foot,
        **penetration,
    }


def compute_reference_errors(loaded: Dict[str, Dict[str, Dict[str, Any]]], reference_method: str) -> List[Dict[str, Any]]:
    if reference_method not in loaded:
        return []
    rows = []
    ref_items = loaded[reference_method]
    for motion, ref_data in sorted(ref_items.items()):
        ref_fps = fps_of(ref_data)
        ref_body = first_array(ref_data, ["body_pos", "local_body_pos"])
        ref_root = array_or_none(ref_data.get("root_pos"))
        ref_dof = array_or_none(ref_data.get("dof_pos"))
        if ref_dof is None and array_or_none(ref_data.get("qpos")) is not None:
            ref_dof = array_or_none(ref_data.get("qpos"))[:, 7:]
        for method, items in sorted(loaded.items()):
            if motion not in items:
                continue
            data = items[motion]
            fps = fps_of(data)
            body = first_array(data, ["body_pos", "local_body_pos"])
            root = array_or_none(data.get("root_pos"))
            dof = array_or_none(data.get("dof_pos"))
            if dof is None and array_or_none(data.get("qpos")) is not None:
                dof = array_or_none(data.get("qpos"))[:, 7:]
            ref_timeline = ref_body if ref_body is not None else ref_root
            timeline = body if body is not None else root
            common_duration = min(duration_of(ref_timeline, ref_fps), duration_of(timeline, fps))
            n = max(2, int(round(common_duration * 30.0)) + 1) if common_duration > 0 else min(first_frame_count([ref_body, ref_root]), first_frame_count([body, root]))
            ref_body_r = resample(ref_body, ref_fps, n, common_duration)
            body_r = resample(body, fps, n, common_duration)
            ref_root_r = resample(ref_root, ref_fps, n, common_duration)
            root_r = resample(root, fps, n, common_duration)
            ref_dof_r = resample(ref_dof, ref_fps, n, common_duration)
            dof_r = resample(dof, fps, n, common_duration)
            rows.append(
                {
                    "motion": motion,
                    "method": method,
                    "reference_method": reference_method,
                    "global_body_position_error_to_reference_mm": 1000.0 * mean_vector_distance(body_r, ref_body_r),
                    "relative_root_error_to_reference_mm": 1000.0 * mean_relative_root_distance(body_r, root_r, ref_body_r, ref_root_r),
                    "root_position_error_to_reference_mm": 1000.0 * mean_vector_distance(root_r, ref_root_r),
                    "joint_angle_difference_to_reference_rad": mean_abs_diff(dof_r, ref_dof_r),
                    "synced_frames": n,
                }
            )
    return rows


def inject_reference_errors(per_motion: List[Dict[str, Any]], pairwise: List[Dict[str, Any]]) -> None:
    index = {(row["motion"], row["method"]): row for row in pairwise}
    for row in per_motion:
        extra = index.get((row["motion"], row["method"]), {})
        for key in [
            "reference_method",
            "global_body_position_error_to_reference_mm",
            "relative_root_error_to_reference_mm",
            "root_position_error_to_reference_mm",
            "joint_angle_difference_to_reference_rad",
        ]:
            row[key] = extra.get(key, np.nan)


def summarize_methods(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    methods = sorted({row["method"] for row in rows})
    mean_cols = [
        "success",
        "global_body_position_error_to_reference_mm",
        "relative_root_error_to_reference_mm",
        "root_position_error_to_reference_mm",
        "joint_angle_difference_to_reference_rad",
        "total_foot_sliding_m",
        "mean_foot_sliding_velocity_mps",
        "max_ground_penetration_m",
        "mean_ground_penetration_m",
        "penetration_frame_ratio",
        "mean_abs_joint_velocity",
        "mean_abs_joint_acceleration",
        "mean_abs_joint_jerk",
        "sudden_jump_count",
        "self_collision_count",
    ]
    sum_cols = ["fall_count", "terminated_count"]
    summary = []
    for method in methods:
        subset = [row for row in rows if row["method"] == method]
        out: Dict[str, Any] = {"method": method, "motion_count": len(subset)}
        for col in mean_cols:
            out[f"mean_{col}"] = safe_mean([row.get(col, np.nan) for row in subset])
        for col in sum_cols:
            out[f"sum_{col}"] = int(np.nansum([row.get(col, 0) for row in subset]))
        summary.append(out)
    return summary


def joint_jump_metrics(dof: Optional[np.ndarray], fps: float, data: Dict[str, Any]) -> Dict[str, Any]:
    if dof is None or dof.ndim != 2 or len(dof) < 2:
        return {
            "mean_abs_joint_velocity": np.nan,
            "max_abs_joint_velocity": np.nan,
            "mean_abs_joint_acceleration": np.nan,
            "max_abs_joint_acceleration": np.nan,
            "mean_abs_joint_jerk": np.nan,
            "max_abs_joint_jerk": np.nan,
            "sudden_jump_count": np.nan,
            "top_jump_joints": "",
        }
    vel = np.diff(dof, axis=0) * fps
    acc = np.diff(vel, axis=0) * fps if len(vel) > 1 else np.zeros((0, dof.shape[1]))
    jerk = np.diff(acc, axis=0) * fps if len(acc) > 1 else np.zeros((0, dof.shape[1]))
    abs_vel = np.abs(vel)
    threshold = np.nanmean(abs_vel, axis=0) + 3.0 * np.nanstd(abs_vel, axis=0)
    jump_mask = abs_vel > threshold.reshape(1, -1)
    per_joint = np.sum(jump_mask, axis=0)
    names = names_for_dof(data, dof.shape[1])
    order = np.argsort(per_joint)[::-1][:10]
    top = "; ".join(f"{names[idx]}({int(per_joint[idx])})" for idx in order)
    return {
        "mean_abs_joint_velocity": safe_mean(abs_vel),
        "max_abs_joint_velocity": safe_max(abs_vel),
        "mean_abs_joint_acceleration": safe_mean(np.abs(acc)),
        "max_abs_joint_acceleration": safe_max(np.abs(acc)),
        "mean_abs_joint_jerk": safe_mean(np.abs(jerk)),
        "max_abs_joint_jerk": safe_max(np.abs(jerk)),
        "sudden_jump_count": int(np.sum(np.any(jump_mask, axis=1))),
        "top_jump_joints": top,
    }


def foot_quality_metrics(foot_pos: Optional[np.ndarray], contacts: Optional[np.ndarray], fps: float, floor: float, contact_height: float) -> Dict[str, Any]:
    if foot_pos is None or foot_pos.ndim != 3 or foot_pos.shape[-1] < 3:
        return {
            "left_foot_sliding_m": np.nan,
            "right_foot_sliding_m": np.nan,
            "total_foot_sliding_m": np.nan,
            "mean_foot_sliding_velocity_mps": np.nan,
            "contact_frame_ratio": np.nan,
        }
    nfeet = min(2, foot_pos.shape[1])
    total_slide = 0.0
    total_contact_steps = 0
    total_contact_velocity = 0.0
    slide_by_side = []
    contact_any = []
    for idx in range(nfeet):
        foot = foot_pos[:, idx, :]
        contact = contact_for_foot(foot, contacts, idx, floor, contact_height)
        contact_any.append(contact)
        if len(foot) < 2:
            slide = np.zeros(0)
            contact_step = np.zeros(0, dtype=bool)
        else:
            step = np.linalg.norm(np.diff(foot[:, :2], axis=0), axis=1)
            contact_step = contact[:-1] & contact[1:]
            slide = np.where(contact_step, step, 0.0)
        distance = float(np.nansum(slide))
        slide_by_side.append(distance)
        total_slide += distance
        total_contact_steps += int(np.sum(contact_step))
        total_contact_velocity += float(np.nansum(slide * fps))
    contact_stack = np.stack(contact_any, axis=1) if contact_any else np.zeros((len(foot_pos), 0), dtype=bool)
    return {
        "left_foot_sliding_m": slide_by_side[0] if len(slide_by_side) > 0 else np.nan,
        "right_foot_sliding_m": slide_by_side[1] if len(slide_by_side) > 1 else np.nan,
        "total_foot_sliding_m": total_slide,
        "mean_foot_sliding_velocity_mps": total_contact_velocity / total_contact_steps if total_contact_steps > 0 else 0.0,
        "contact_frame_ratio": float(np.mean(np.any(contact_stack, axis=1))) if contact_stack.size else np.nan,
    }


def penetration_metrics(foot_pos: Optional[np.ndarray], body_pos: Optional[np.ndarray], body_names: List[str], floor: float) -> Dict[str, Any]:
    points = None
    source = "unavailable"
    if foot_pos is not None and foot_pos.ndim == 3:
        points = foot_pos
        source = "foot_pos"
    elif body_pos is not None and body_pos.ndim == 3:
        start = 1 if body_names and str(body_names[0]).lower() == "world" else 0
        points = body_pos[:, start:, :]
        source = "body_pos"
    if points is None or points.size == 0:
        return {
            "max_ground_penetration_m": np.nan,
            "mean_ground_penetration_m": np.nan,
            "penetration_frame_ratio": np.nan,
            "penetration_source": source,
        }
    depth = np.maximum(0.0, floor - points[..., 2])
    per_frame = np.nanmax(depth.reshape(depth.shape[0], -1), axis=1)
    return {
        "max_ground_penetration_m": safe_max(depth),
        "mean_ground_penetration_m": safe_mean(depth),
        "penetration_frame_ratio": float(np.mean(per_frame > 0.0)) if len(per_frame) else np.nan,
        "penetration_source": source,
    }


def success_from_metrics(
    root_min: float,
    max_penetration: float,
    self_collision_count: float,
    fall_count: int,
    terminated_count: int,
    root_height_threshold: float,
    penetration_threshold: float,
    self_collision_threshold: int,
    use_status_flags: bool,
) -> Tuple[bool, List[str]]:
    reasons = []
    if np.isfinite(root_min) and root_min < root_height_threshold:
        reasons.append(f"root_min_height={root_min:.3f}<threshold={root_height_threshold:.3f}")
    if np.isfinite(max_penetration) and max_penetration > penetration_threshold:
        reasons.append(f"max_penetration={max_penetration:.3f}>threshold={penetration_threshold:.3f}")
    if np.isfinite(self_collision_count) and self_collision_count > self_collision_threshold:
        reasons.append(f"self_collision_count={self_collision_count}>threshold={self_collision_threshold}")
    if use_status_flags:
        if fall_count > 0:
            reasons.append(f"fall_count={fall_count}")
        if terminated_count > 0:
            reasons.append(f"terminated_count={terminated_count}")
    return len(reasons) == 0, reasons


def names_for_dof(data: Dict[str, Any], width: int) -> List[str]:
    raw = data.get("dof_joint_names") or data.get("robot_joint_names") or data.get("joint_names") or JOINT_NAMES_29
    if not isinstance(raw, (list, tuple)):
        raw = JOINT_NAMES_29
    names = [str(name).replace("_hinge", "") for name in raw]
    if len(names) == width:
        return names
    if len(names) > width:
        return names[-width:]
    return names + [f"joint_{idx}" for idx in range(len(names), width)]


def contact_for_foot(foot: np.ndarray, contacts: Optional[np.ndarray], idx: int, floor: float, contact_height: float) -> np.ndarray:
    if contacts is not None and contacts.ndim == 2 and contacts.shape[0] == foot.shape[0] and contacts.shape[1] > idx:
        return contacts[:, idx].astype(bool)
    return foot[:, 2] <= floor + contact_height


def motion_id(path: Path, pattern: str) -> str:
    match = re.search(pattern, path.stem)
    if match:
        return match.group(1) if match.groups() else match.group(0)
    return path.stem


def fps_of(data: Dict[str, Any]) -> float:
    return scalar(data.get("fps"), fallback_from_dt(data.get("dt"), 30.0))


def fallback_from_dt(value: Any, default: float) -> float:
    try:
        dt = float(np.asarray(value).reshape(-1)[0])
        return 1.0 / dt if dt > 0 else default
    except Exception:
        return default


def array_or_none(value: Any) -> Optional[np.ndarray]:
    if value is None:
        return None
    try:
        arr = np.asarray(value, dtype=float)
    except Exception:
        return None
    return arr


def first_array(data: Dict[str, Any], keys: List[str]) -> Optional[np.ndarray]:
    for key in keys:
        arr = array_or_none(data.get(key))
        if arr is not None:
            return arr
    return None


def scalar(value: Any, default: float) -> float:
    try:
        out = float(np.asarray(value).reshape(-1)[0])
        return out if np.isfinite(out) and out > 0 else default
    except Exception:
        return default


def duration(frames: int, fps: float) -> float:
    return (frames - 1) / max(fps, 1e-9) if frames > 1 else 0.0


def duration_of(value: Optional[np.ndarray], fps: float) -> float:
    return duration(len(value), fps) if value is not None and value.ndim > 0 else 0.0


def first_frame_count(values: List[Optional[np.ndarray]]) -> int:
    for value in values:
        if value is not None and value.ndim > 0:
            return int(value.shape[0])
    return 0


def resample(value: Optional[np.ndarray], fps: float, frame_count: int, target_duration: float) -> Optional[np.ndarray]:
    if value is None or value.ndim == 0 or frame_count <= 0:
        return None
    if len(value) == frame_count:
        return value
    old_duration = duration_of(value, fps)
    if old_duration <= 0.0:
        return value[:frame_count]
    old_t = np.linspace(0.0, old_duration, len(value))
    new_t = np.linspace(0.0, min(target_duration, old_duration), frame_count)
    flat = value.reshape(len(value), -1)
    out = np.empty((frame_count, flat.shape[1]), dtype=float)
    for idx in range(flat.shape[1]):
        out[:, idx] = np.interp(new_t, old_t, flat[:, idx])
    return out.reshape((frame_count,) + value.shape[1:])


def mean_vector_distance(a: Optional[np.ndarray], b: Optional[np.ndarray]) -> float:
    diff = comparable_diff(a, b)
    if diff is None:
        return np.nan
    return float(np.nanmean(np.linalg.norm(diff, axis=-1)))


def mean_relative_root_distance(body: Optional[np.ndarray], root: Optional[np.ndarray], ref_body: Optional[np.ndarray], ref_root: Optional[np.ndarray]) -> float:
    if body is None or ref_body is None:
        return np.nan
    n = min(body.shape[0], ref_body.shape[0])
    width = min(body.shape[1], ref_body.shape[1])
    body = body[:n, :width, :]
    ref_body = ref_body[:n, :width, :]
    if root is None:
        root = body[:, :1, :]
    else:
        root = root[:n].reshape(n, 1, 3)
    if ref_root is None:
        ref_root = ref_body[:, :1, :]
    else:
        ref_root = ref_root[:n].reshape(n, 1, 3)
    diff = (body - root) - (ref_body - ref_root)
    return float(np.nanmean(np.linalg.norm(diff, axis=-1)))


def mean_abs_diff(a: Optional[np.ndarray], b: Optional[np.ndarray]) -> float:
    diff = comparable_diff(a, b)
    if diff is None:
        return np.nan
    return float(np.nanmean(np.abs(diff)))


def comparable_diff(a: Optional[np.ndarray], b: Optional[np.ndarray]) -> Optional[np.ndarray]:
    if a is None or b is None:
        return None
    ndim = min(a.ndim, b.ndim)
    shape = tuple(min(a.shape[idx], b.shape[idx]) for idx in range(ndim))
    if not shape:
        return None
    slices = tuple(slice(0, dim) for dim in shape)
    return a[slices] - b[slices]


def shape_text(value: Optional[np.ndarray]) -> str:
    return "" if value is None else "x".join(str(dim) for dim in value.shape)


def bool_available(value: Any) -> bool:
    if value is None:
        return False
    try:
        return np.asarray(value).size > 0
    except Exception:
        return True


def bool_count(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(np.asarray(value).astype(bool).sum())
    except Exception:
        return int(bool(value))


def safe_mean(value: Any) -> float:
    arr = np.asarray(value, dtype=float)
    return float(np.nanmean(arr)) if arr.size and np.isfinite(arr).any() else np.nan


def safe_min(value: Any) -> float:
    arr = np.asarray(value, dtype=float)
    return float(np.nanmin(arr)) if arr.size and np.isfinite(arr).any() else np.nan


def safe_max(value: Any) -> float:
    arr = np.asarray(value, dtype=float)
    return float(np.nanmax(arr)) if arr.size and np.isfinite(arr).any() else np.nan


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows([{key: csv_value(value) for key, value in row.items()} for row in rows])


def write_report(path: Path, summary: List[Dict[str, Any]], per_motion: List[Dict[str, Any]], pairwise: List[Dict[str, Any]], missing: List[Dict[str, Any]], reference_method: str) -> None:
    lines = [
        "# PKL Method Evaluation",
        "",
        f"Reference method for global/relative body errors: `{reference_method}`.",
        "",
        "## Summary",
        "",
        "|method|success_rate|global_error_to_ref_mm|relative_root_error_to_ref_mm|joint_jumps|foot_sliding_m|penetration_m|self_collision|mean_acc|mean_jerk|",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        lines.append(
            f"|{row['method']}|{metric_text(row, 'mean_success', 3)}|"
            f"{metric_text(row, 'mean_global_body_position_error_to_reference_mm', 3)}|"
            f"{metric_text(row, 'mean_relative_root_error_to_reference_mm', 3)}|"
            f"{metric_text(row, 'mean_sudden_jump_count', 3)}|"
            f"{metric_text(row, 'mean_total_foot_sliding_m', 6)}|"
            f"{metric_text(row, 'mean_max_ground_penetration_m', 6)}|"
            f"{metric_text(row, 'mean_self_collision_count', 3)}|"
            f"{metric_text(row, 'mean_mean_abs_joint_acceleration', 6)}|"
            f"{metric_text(row, 'mean_mean_abs_joint_jerk', 6)}|"
        )
    lines += [
        "",
        "## Notes",
        "",
        "- Success defaults to physical thresholds only. `fall/terminated` fields are recorded but not used unless `--use_status_flags` is passed.",
        "- Global body position error and relative root error are PKL-to-PKL errors against the selected reference method, not human-reference MPBPE.",
        "- Foot sliding, penetration, self-collision, and joint jumps are absolute metrics computed directly from each method's PKL when those fields are available.",
        "- `N/A` means the PKL did not provide enough information for that metric; it is not treated as zero.",
        "",
        "## Missing",
        "",
    ]
    if missing:
        for row in missing:
            lines.append(f"- {row.get('motion', '')} / {row.get('method', '')}: {row.get('detail', '')}")
    else:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def csv_value(value: Any) -> Any:
    if isinstance(value, float) and not np.isfinite(value):
        return ""
    return value


def metric_text(row: Dict[str, Any], key: str, digits: int) -> str:
    value = row.get(key, np.nan)
    try:
        value = float(value)
    except Exception:
        return "N/A"
    if not np.isfinite(value):
        return "N/A"
    return f"{value:.{digits}f}"


def print_result(summary: List[Dict[str, Any]], pairwise: List[Dict[str, Any]], missing: List[Dict[str, Any]], output_dir: Path, reference_method: str) -> None:
    print(f"Reference method for body/root errors: {reference_method}")
    print(f"Missing records: {len(missing)}")
    print()
    print("method | success_rate | global_error_to_ref_mm | relative_root_error_to_ref_mm | joint_jumps | foot_sliding_m | penetration_m | self_collision | mean_acc | mean_jerk | fall/terminated")
    for row in summary:
        print(
            f"{row['method']} | {metric_text(row, 'mean_success', 3)} | "
            f"{metric_text(row, 'mean_global_body_position_error_to_reference_mm', 3)} | "
            f"{metric_text(row, 'mean_relative_root_error_to_reference_mm', 3)} | "
            f"{metric_text(row, 'mean_sudden_jump_count', 3)} | "
            f"{metric_text(row, 'mean_total_foot_sliding_m', 6)} | "
            f"{metric_text(row, 'mean_max_ground_penetration_m', 6)} | "
            f"{metric_text(row, 'mean_self_collision_count', 3)} | "
            f"{metric_text(row, 'mean_mean_abs_joint_acceleration', 6)} | "
            f"{metric_text(row, 'mean_mean_abs_joint_jerk', 6)} | "
            f"{row['sum_fall_count']}/{row['sum_terminated_count']}"
        )
    print()
    print(f"CSV/report output: {output_dir}")


if __name__ == "__main__":
    main()
