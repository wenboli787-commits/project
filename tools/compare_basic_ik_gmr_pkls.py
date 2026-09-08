#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import pickle
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


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
    basic_dir = Path(args.basic_ik_dir).expanduser()
    gmr_dir = Path(args.gmr_dir).expanduser()
    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    basic_files = sorted(basic_dir.glob("*.pkl"))
    gmr_files = sorted(gmr_dir.glob("*.pkl"))
    basic_by_id = {motion_id(path, args.name_regex): path for path in basic_files}
    gmr_by_id = {motion_id(path, args.name_regex): path for path in gmr_files}
    matched = sorted(set(basic_by_id) & set(gmr_by_id))
    missing_rows = []
    for mid in sorted(set(basic_by_id) - set(gmr_by_id)):
        missing_rows.append({"motion": mid, "method": "GMR", "detail": "missing matching GMR pkl"})
    for mid in sorted(set(gmr_by_id) - set(basic_by_id)):
        missing_rows.append({"motion": mid, "method": "Basic IK", "detail": "missing matching Basic IK pkl"})

    per_motion_rows: List[Dict[str, Any]] = []
    pairwise_rows: List[Dict[str, Any]] = []
    for mid in matched:
        basic = load_pkl(basic_by_id[mid])
        gmr = load_pkl(gmr_by_id[mid])
        basic_row = compute_single_metrics(mid, "Basic IK", basic_by_id[mid], basic, args.floor_height, args.foot_contact_height)
        gmr_row = compute_single_metrics(mid, "GMR", gmr_by_id[mid], gmr, args.floor_height, args.foot_contact_height)
        per_motion_rows.extend([basic_row, gmr_row])
        pairwise_rows.append(compute_pairwise_metrics(mid, basic, gmr))

    summary_rows = summarize(per_motion_rows)
    write_csv(output_dir / "basic_ik_vs_gmr_per_motion.csv", per_motion_rows)
    write_csv(output_dir / "basic_ik_vs_gmr_summary.csv", summary_rows)
    write_csv(output_dir / "basic_ik_vs_gmr_pairwise.csv", pairwise_rows)
    write_csv(output_dir / "basic_ik_vs_gmr_missing.csv", missing_rows, ["motion", "method", "detail"])

    print(f"Basic IK files: {len(basic_files)}")
    print(f"GMR files: {len(gmr_files)}")
    print(f"Matched motions: {len(matched)}")
    print(f"Missing pairs: {len(missing_rows)}")
    print()
    print("METHOD SUMMARY")
    print("method | motions | mean_total_foot_sliding_m | mean_max_ground_penetration_m | mean_abs_joint_velocity | mean_abs_joint_acceleration | mean_abs_joint_jerk | mean_sudden_jump_count | fall_count | terminated_count")
    for row in summary_rows:
        print(
            "{method} | {motion_count} | {mean_total_foot_sliding_m:.6f} | {mean_max_ground_penetration_m:.6f} | "
            "{mean_mean_abs_joint_velocity:.6f} | {mean_mean_abs_joint_acceleration:.6f} | {mean_mean_abs_joint_jerk:.6f} | "
            "{mean_sudden_jump_count:.3f} | {sum_fall_count} | {sum_terminated_count}".format(**row)
        )
    print()
    print("PAIRWISE BODY/FOOT DISTANCE")
    print("motion | body_mean_distance_m | foot_mean_distance_m | root_mean_distance_m | dof_mean_abs_diff_rad")
    for row in pairwise_rows:
        print(
            "{motion} | {body_mean_distance_m:.6f} | {foot_mean_distance_m:.6f} | {root_mean_distance_m:.6f} | {dof_mean_abs_diff_rad:.6f}".format(**row)
        )
    print()
    print(f"CSV output directory: {output_dir}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare newly generated Basic IK and GMR Unitree G1 PKL files.")
    parser.add_argument("--basic_ik_dir", default=r"D:\GMR_WORK\GMR\outputs\final product\pkl Basic IK")
    parser.add_argument("--gmr_dir", default=r"D:\GMR_WORK\GMR\outputs\final product\pkl")
    parser.add_argument("--output_dir", default=r"D:\GMR_WORK\GMR\outputs\final product")
    parser.add_argument("--name_regex", default=r"^([0-9]+_[0-9]+)")
    parser.add_argument("--floor_height", type=float, default=0.0)
    parser.add_argument("--foot_contact_height", type=float, default=0.04)
    return parser


def load_pkl(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        obj = pickle.load(f)
    if not isinstance(obj, dict):
        raise ValueError(f"Expected dict PKL: {path}")
    return obj


def motion_id(path: Path, pattern: str) -> str:
    match = re.search(pattern, path.stem)
    return match.group(1) if match and match.groups() else (match.group(0) if match else path.stem)


def compute_single_metrics(motion: str, method: str, path: Path, data: Dict[str, Any], floor: float, contact_height: float) -> Dict[str, Any]:
    fps = scalar(data.get("fps", 30.0), 30.0)
    root_pos = array_or_none(data.get("root_pos"))
    qpos = array_or_none(data.get("qpos"))
    dof_pos = array_or_none(data.get("dof_pos"))
    body_pos = array_or_none(data.get("body_pos"))
    foot_pos = array_or_none(data.get("foot_pos"))
    contacts = array_or_none(data.get("contacts"))
    if dof_pos is None and qpos is not None and qpos.shape[1] > 7:
        dof_pos = qpos[:, 7:]
    frames = first_frame_count([dof_pos, root_pos, body_pos, foot_pos, qpos])
    duration = (frames - 1) / fps if frames > 1 else 0.0

    smooth = smoothness_metrics(dof_pos, fps)
    foot = foot_metrics(foot_pos, contacts, fps, floor, contact_height)
    fall = bool_count(data.get("fall"))
    terminated = bool_count(data.get("terminated"))
    self_collision = bool_count(data.get("self_collision"))
    joint_names = data.get("dof_joint_names") or data.get("robot_joint_names") or data.get("joint_names") or JOINT_NAMES_29
    top_jump = top_jump_joints(dof_pos, fps, joint_names)

    return {
        "motion": motion,
        "method": method,
        "pkl_path": str(path),
        "frames": frames,
        "fps": fps,
        "duration_s": duration,
        "qpos_shape": shape_text(qpos),
        "dof_pos_shape": shape_text(dof_pos),
        "body_pos_shape": shape_text(body_pos),
        "foot_pos_shape": shape_text(foot_pos),
        "contacts_shape": shape_text(contacts),
        "root_xy_path_m": root_path(root_pos),
        "root_min_height_m": safe_min(root_pos[:, 2] if root_pos is not None and root_pos.ndim == 2 and root_pos.shape[1] >= 3 else None),
        "fall_count": fall,
        "terminated_count": terminated,
        "self_collision_count": self_collision,
        "top_jump_joints": top_jump,
        **smooth,
        **foot,
    }


def compute_pairwise_metrics(motion: str, basic: Dict[str, Any], gmr: Dict[str, Any]) -> Dict[str, Any]:
    bfps = scalar(basic.get("fps", 30.0), 30.0)
    gfps = scalar(gmr.get("fps", 30.0), 30.0)
    b_root = array_or_none(basic.get("root_pos"))
    g_root = array_or_none(gmr.get("root_pos"))
    b_body = array_or_none(basic.get("body_pos"))
    g_body = array_or_none(gmr.get("body_pos"))
    b_foot = array_or_none(basic.get("foot_pos"))
    g_foot = array_or_none(gmr.get("foot_pos"))
    b_dof = array_or_none(basic.get("dof_pos"))
    g_dof = array_or_none(gmr.get("dof_pos"))
    if b_dof is None and array_or_none(basic.get("qpos")) is not None:
        b_dof = array_or_none(basic.get("qpos"))[:, 7:]
    if g_dof is None and array_or_none(gmr.get("qpos")) is not None:
        g_dof = array_or_none(gmr.get("qpos"))[:, 7:]
    duration = min(duration_of(b_root, bfps), duration_of(g_root, gfps))
    n = max(2, int(round(duration * 30.0)) + 1) if duration > 0 else min(first_frame_count([b_root]), first_frame_count([g_root]))

    b_root_r = resample(b_root, bfps, n, duration)
    g_root_r = resample(g_root, gfps, n, duration)
    b_body_r = resample(b_body, bfps, n, duration)
    g_body_r = resample(g_body, gfps, n, duration)
    b_foot_r = resample(b_foot, bfps, n, duration)
    g_foot_r = resample(g_foot, gfps, n, duration)
    b_dof_r = resample(b_dof, bfps, n, duration)
    g_dof_r = resample(g_dof, gfps, n, duration)

    return {
        "motion": motion,
        "synced_frames": n,
        "body_mean_distance_m": mean_vector_distance(g_body_r, b_body_r),
        "body_max_distance_m": max_vector_distance(g_body_r, b_body_r),
        "foot_mean_distance_m": mean_vector_distance(g_foot_r, b_foot_r),
        "foot_max_distance_m": max_vector_distance(g_foot_r, b_foot_r),
        "root_mean_distance_m": mean_vector_distance(g_root_r, b_root_r),
        "root_max_distance_m": max_vector_distance(g_root_r, b_root_r),
        "dof_mean_abs_diff_rad": mean_abs_diff(g_dof_r, b_dof_r),
        "dof_max_abs_diff_rad": max_abs_diff(g_dof_r, b_dof_r),
    }


def smoothness_metrics(dof: Optional[np.ndarray], fps: float) -> Dict[str, float]:
    if dof is None or len(dof) < 2:
        return {
            "mean_abs_joint_velocity": np.nan,
            "max_abs_joint_velocity": np.nan,
            "mean_abs_joint_acceleration": np.nan,
            "max_abs_joint_acceleration": np.nan,
            "mean_abs_joint_jerk": np.nan,
            "max_abs_joint_jerk": np.nan,
            "sudden_jump_count": np.nan,
        }
    vel = np.diff(dof, axis=0) * fps
    acc = np.diff(vel, axis=0) * fps if len(vel) >= 2 else np.zeros((0, dof.shape[1]))
    jerk = np.diff(acc, axis=0) * fps if len(acc) >= 2 else np.zeros((0, dof.shape[1]))
    abs_vel = np.abs(vel)
    threshold = np.nanmean(abs_vel, axis=0) + 3.0 * np.nanstd(abs_vel, axis=0)
    sudden = np.any(abs_vel > threshold.reshape(1, -1), axis=1)
    return {
        "mean_abs_joint_velocity": safe_mean(abs_vel),
        "max_abs_joint_velocity": safe_max(abs_vel),
        "mean_abs_joint_acceleration": safe_mean(np.abs(acc)),
        "max_abs_joint_acceleration": safe_max(np.abs(acc)),
        "mean_abs_joint_jerk": safe_mean(np.abs(jerk)),
        "max_abs_joint_jerk": safe_max(np.abs(jerk)),
        "sudden_jump_count": int(np.sum(sudden)),
    }


def foot_metrics(foot_pos: Optional[np.ndarray], contacts: Optional[np.ndarray], fps: float, floor: float, contact_height: float) -> Dict[str, float]:
    if foot_pos is None or foot_pos.ndim != 3 or foot_pos.shape[-1] < 3:
        return {
            "left_foot_sliding_m": np.nan,
            "right_foot_sliding_m": np.nan,
            "total_foot_sliding_m": np.nan,
            "mean_foot_sliding_velocity_mps": np.nan,
            "min_foot_height_m": np.nan,
            "mean_foot_height_m": np.nan,
            "max_ground_penetration_m": np.nan,
            "mean_ground_penetration_m": np.nan,
            "penetration_frame_ratio": np.nan,
            "contact_frame_ratio": np.nan,
        }
    nfeet = min(2, foot_pos.shape[1])
    slides = []
    contact_counts = []
    contact_vel_total = 0.0
    for idx in range(nfeet):
        foot = foot_pos[:, idx, :]
        if contacts is not None and contacts.ndim == 2 and contacts.shape[0] == foot_pos.shape[0] and contacts.shape[1] > idx:
            contact = contacts[:, idx].astype(bool)
        else:
            contact = foot[:, 2] <= floor + contact_height
        step = np.linalg.norm(np.diff(foot[:, :2], axis=0), axis=1) if len(foot) > 1 else np.zeros(0)
        contact_step = contact[:-1] & contact[1:] if len(contact) > 1 else np.zeros(0, dtype=bool)
        slide = np.where(contact_step, step, 0.0)
        slides.append(slide)
        contact_counts.append(int(np.sum(contact_step)))
        contact_vel_total += float(np.sum(slide * fps))
    left_slide = float(np.sum(slides[0])) if len(slides) > 0 else np.nan
    right_slide = float(np.sum(slides[1])) if len(slides) > 1 else np.nan
    total_slide = float(np.nansum([left_slide, right_slide]))
    total_contact_steps = int(np.sum(contact_counts))
    heights = foot_pos[:, :nfeet, 2]
    penetration = np.maximum(0.0, floor - heights)
    return {
        "left_foot_sliding_m": left_slide,
        "right_foot_sliding_m": right_slide,
        "total_foot_sliding_m": total_slide,
        "mean_foot_sliding_velocity_mps": contact_vel_total / total_contact_steps if total_contact_steps > 0 else 0.0,
        "min_foot_height_m": safe_min(heights),
        "mean_foot_height_m": safe_mean(heights),
        "max_ground_penetration_m": safe_max(penetration),
        "mean_ground_penetration_m": safe_mean(penetration),
        "penetration_frame_ratio": float(np.mean(np.any(penetration > 0.0, axis=1))) if len(penetration) else np.nan,
        "contact_frame_ratio": float(np.mean(np.any(heights <= floor + contact_height, axis=1))) if len(heights) else np.nan,
    }


def top_jump_joints(dof: Optional[np.ndarray], fps: float, names: Any) -> str:
    if dof is None or len(dof) < 2:
        return ""
    if not isinstance(names, (list, tuple)) or len(names) < dof.shape[1]:
        names = JOINT_NAMES_29
    names = [str(name).replace("_hinge", "") for name in names[-dof.shape[1]:]]
    vel = np.abs(np.diff(dof, axis=0) * fps)
    threshold = np.nanmean(vel, axis=0) + 3.0 * np.nanstd(vel, axis=0)
    counts = np.sum(vel > threshold.reshape(1, -1), axis=0)
    order = np.argsort(counts)[::-1][:5]
    return "; ".join(f"{names[idx]}({int(counts[idx])})" for idx in order)


def summarize(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    methods = sorted({row["method"] for row in rows})
    summary = []
    mean_columns = [
        "total_foot_sliding_m",
        "mean_foot_sliding_velocity_mps",
        "max_ground_penetration_m",
        "mean_ground_penetration_m",
        "penetration_frame_ratio",
        "root_xy_path_m",
        "root_min_height_m",
        "mean_abs_joint_velocity",
        "mean_abs_joint_acceleration",
        "mean_abs_joint_jerk",
        "sudden_jump_count",
        "self_collision_count",
    ]
    sum_columns = ["fall_count", "terminated_count"]
    for method in methods:
        subset = [row for row in rows if row["method"] == method]
        out: Dict[str, Any] = {"method": method, "motion_count": len(subset)}
        for col in mean_columns:
            out[f"mean_{col}"] = safe_mean([row.get(col, np.nan) for row in subset])
        for col in sum_columns:
            out[f"sum_{col}"] = int(np.nansum([row.get(col, 0) for row in subset]))
        summary.append(out)
    return summary


def resample(value: Optional[np.ndarray], fps: float, frame_count: int, duration: float) -> Optional[np.ndarray]:
    if value is None or frame_count <= 0:
        return None
    value = np.asarray(value, dtype=float)
    if len(value) == frame_count:
        return value
    old_duration = duration_of(value, fps)
    old_t = np.linspace(0.0, old_duration, len(value))
    new_t = np.linspace(0.0, min(duration, old_duration), frame_count)
    flat = value.reshape(len(value), -1)
    out = np.empty((frame_count, flat.shape[1]), dtype=float)
    for idx in range(flat.shape[1]):
        out[:, idx] = np.interp(new_t, old_t, flat[:, idx])
    return out.reshape((frame_count,) + value.shape[1:])


def array_or_none(value: Any) -> Optional[np.ndarray]:
    if value is None:
        return None
    try:
        return np.asarray(value, dtype=float)
    except Exception:
        return None


def scalar(value: Any, default: float) -> float:
    try:
        return float(np.asarray(value).reshape(-1)[0])
    except Exception:
        return default


def first_frame_count(values: List[Optional[np.ndarray]]) -> int:
    for value in values:
        if value is not None and value.ndim > 0:
            return int(value.shape[0])
    return 0


def duration_of(value: Optional[np.ndarray], fps: float) -> float:
    if value is None or len(value) <= 1:
        return 0.0
    return (len(value) - 1) / max(fps, 1e-9)


def shape_text(value: Optional[np.ndarray]) -> str:
    return "" if value is None else "x".join(str(dim) for dim in value.shape)


def root_path(root_pos: Optional[np.ndarray]) -> float:
    if root_pos is None or len(root_pos) < 2:
        return np.nan
    return float(np.sum(np.linalg.norm(np.diff(root_pos[:, :2], axis=0), axis=1)))


def bool_count(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(np.asarray(value).astype(bool).sum())
    except Exception:
        return int(bool(value))


def mean_vector_distance(a: Optional[np.ndarray], b: Optional[np.ndarray]) -> float:
    diff = comparable_diff(a, b)
    if diff is None:
        return np.nan
    return float(np.nanmean(np.linalg.norm(diff, axis=-1)))


def max_vector_distance(a: Optional[np.ndarray], b: Optional[np.ndarray]) -> float:
    diff = comparable_diff(a, b)
    if diff is None:
        return np.nan
    return float(np.nanmax(np.linalg.norm(diff, axis=-1)))


def mean_abs_diff(a: Optional[np.ndarray], b: Optional[np.ndarray]) -> float:
    diff = comparable_diff(a, b)
    return safe_mean(np.abs(diff)) if diff is not None else np.nan


def max_abs_diff(a: Optional[np.ndarray], b: Optional[np.ndarray]) -> float:
    diff = comparable_diff(a, b)
    return safe_max(np.abs(diff)) if diff is not None else np.nan


def comparable_diff(a: Optional[np.ndarray], b: Optional[np.ndarray]) -> Optional[np.ndarray]:
    if a is None or b is None:
        return None
    shape = tuple(min(x, y) for x, y in zip(a.shape, b.shape))
    if not shape:
        return None
    slices = tuple(slice(0, dim) for dim in shape)
    return a[slices] - b[slices]


def safe_mean(value: Any) -> float:
    arr = np.asarray(value, dtype=float)
    return float(np.nanmean(arr)) if arr.size and np.isfinite(arr).any() else np.nan


def safe_min(value: Any) -> float:
    if value is None:
        return np.nan
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
        writer.writerows(rows)


if __name__ == "__main__":
    main()
