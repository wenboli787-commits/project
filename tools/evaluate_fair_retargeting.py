#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import pickle
import re
import shutil
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:  # pragma: no cover
    Image = None
    ImageDraw = None
    ImageFont = None


DEFAULT_CONFIG = r"D:\GMR_WORK\configs\fair_retarget_eval_unitree_g1.json"
METHOD_ORDER = ["Direct Mapping", "Basic IK", "GMR"]
METHOD_COLORS = {
    "Direct Mapping": "#E4572E",
    "Basic IK": "#4C78A8",
    "GMR": "#54A24B",
}
NAN = float("nan")


def main() -> None:
    args = build_parser().parse_args()
    config_path = host_path(args.config)
    config = load_json(config_path)
    if args.output_dir:
        config["output_dir"] = args.output_dir
    out_dir = host_path(config["output_dir"])
    dirs = make_output_dirs(out_dir)
    shutil.copyfile(config_path, dirs["root"] / "thresholds_config.json")

    warnings: List[str] = []
    model = parse_robot_xml(host_path(config["robot_xml"]), warnings)
    mujoco_available = check_mujoco(warnings)
    if not mujoco_available:
        warnings.append(
            "MuJoCo is not installed in this Python environment; FK, foot-geom lowest-point contact, "
            "mj_differentiatePos, and contact-pair self-collision are unavailable. Falling back to PKL body_pos, "
            "foot_pos, contacts, and self_collision fields where present."
        )

    originals = discover_files(host_path(config["original_motion_root"]), {".npz", ".npy", ".bvh"})
    original_by_motion = index_by_motion(originals, config["motion_id_regex"])
    method_files = {
        method: index_by_motion(discover_files(host_path(info["pkl_root"]), {".pkl", ".pickle"}), config["motion_id_regex"])
        for method, info in config["methods"].items()
    }
    source_files = index_by_motion(discover_files(host_path(config["source_reference"]["pkl_root"]), {".pkl", ".pickle"}), config["motion_id_regex"])

    all_original_motions = sorted(original_by_motion)
    extra_motion_warnings(original_by_motion, method_files, warnings)

    per_motion_rows: List[Dict[str, Any]] = []
    missing_rows: List[Dict[str, Any]] = []
    source_cache: Dict[str, Optional[Dict[str, Any]]] = {}

    for motion in all_original_motions:
        source = load_source_reference(motion, source_files.get(motion), original_by_motion.get(motion), config, warnings)
        source_cache[motion] = source
        for method in METHOD_ORDER:
            path = method_files.get(method, {}).get(motion)
            if path is None:
                row = missing_result_row(motion, method, original_by_motion[motion], "missing_pkl")
                per_motion_rows.append(row)
                missing_rows.append(row)
                continue
            try:
                row = evaluate_one_motion(motion, method, path, source, config, model, mujoco_available, warnings)
            except Exception as exc:
                row = missing_result_row(motion, method, original_by_motion[motion], f"load_or_eval_failed: {exc}")
                row["pkl_file"] = str(path)
                per_motion_rows.append(row)
                missing_rows.append(row)
                warnings.append(f"{motion}/{method}: evaluation failed for {path}: {exc}")
                continue
            per_motion_rows.append(row)

    summary_rows = summarize_by_method(per_motion_rows)
    counts_rows = success_failure_counts(per_motion_rows)
    failure_rows = failure_reason_counts(per_motion_rows)

    write_csv(dirs["csv"] / "fair_per_motion_metrics.csv", per_motion_rows)
    write_csv(dirs["csv"] / "fair_per_method_summary.csv", summary_rows)
    write_csv(dirs["csv"] / "success_failure_counts.csv", counts_rows)
    write_csv(dirs["csv"] / "failure_reason_counts.csv", failure_rows)
    write_csv(dirs["csv"] / "missing_files.csv", missing_rows)
    write_json(dirs["json"] / "fair_per_motion_metrics.json", per_motion_rows)
    write_json(dirs["json"] / "fair_per_method_summary.json", summary_rows)

    figures = make_figures(per_motion_rows, summary_rows, dirs["figures"], warnings)
    write_warnings(dirs["root"] / "warnings.txt", warnings)
    write_report(dirs["report"] / "FAIR_RETARGETING_EVALUATION_REPORT.md", config, model, per_motion_rows, summary_rows, counts_rows, failure_rows, figures, warnings)

    print("Fair retargeting evaluation finished.")
    print(f"Original motions: {len(all_original_motions)}")
    print(f"Rows: {len(per_motion_rows)}")
    print(f"Missing/eval failed rows: {len(missing_rows)}")
    print(f"Report: {dirs['report'] / 'FAIR_RETARGETING_EVALUATION_REPORT.md'}")
    print(f"Warnings: {dirs['root'] / 'warnings.txt'}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fair evaluation for Direct Mapping, Basic IK, and GMR retargeting results.")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--output_dir", default=None)
    return parser


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def host_path(value: str | Path) -> Path:
    text = str(value)
    if os.name != "nt":
        match = re.match(r"^([A-Za-z]):[\\/](.*)$", text)
        if match:
            drive = match.group(1).lower()
            rest = match.group(2).replace("\\", "/")
            return Path(f"/mnt/{drive}/{rest}")
    return Path(text).expanduser()


def make_output_dirs(root: Path) -> Dict[str, Path]:
    dirs = {
        "root": root,
        "csv": root / "csv",
        "json": root / "json",
        "figures": root / "figures",
        "report": root / "report",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def discover_files(root: Path, suffixes: set[str]) -> List[Path]:
    if not root.exists():
        return []
    if root.is_file():
        return [root] if root.suffix.lower() in suffixes else []
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes)


def index_by_motion(paths: Sequence[Path], pattern: str) -> Dict[str, Path]:
    out: Dict[str, Path] = {}
    for path in paths:
        motion = motion_id(path, pattern)
        out[motion] = path
    return out


def motion_id(path: Path, pattern: str) -> str:
    match = re.search(pattern, path.stem)
    if match:
        return match.group(1) if match.groups() else match.group(0)
    return path.stem


def extra_motion_warnings(originals: Dict[str, Path], method_files: Dict[str, Dict[str, Path]], warnings: List[str]) -> None:
    original_ids = set(originals)
    for method, files in method_files.items():
        extras = sorted(set(files) - original_ids)
        for motion in extras:
            warnings.append(f"{method}/{motion}: PKL exists but no matching original motion file was found; excluded from fair comparison.")


def check_mujoco(warnings: List[str]) -> bool:
    try:
        import mujoco  # noqa: F401

        return True
    except Exception as exc:
        warnings.append(f"MuJoCo import failed: {exc}")
        return False


def parse_robot_xml(path: Path, warnings: List[str]) -> Dict[str, Any]:
    model = {
        "xml": str(path),
        "model_nq": NAN,
        "joint_names": [],
        "joint_ranges": {},
        "robot_leg_length_m": NAN,
    }
    if not path.exists():
        warnings.append(f"Robot XML missing: {path}")
        return model
    try:
        root = ET.parse(path).getroot()
    except Exception as exc:
        warnings.append(f"Robot XML parse failed: {path}: {exc}")
        return model

    nq = 0
    freejoint_count = 0
    for freejoint in root.iter("freejoint"):
        if freejoint.get("name"):
            freejoint_count += 1
    nq += 7 * max(freejoint_count, 1)
    for joint in root.iter("joint"):
        name = joint.get("name")
        if not name:
            continue
        typ = joint.get("type", "hinge")
        if typ == "free":
            nq += 7
            continue
        width = 4 if typ == "ball" else 1
        nq += width
        rng = parse_range(joint.get("range"))
        model["joint_names"].append(name)
        model["joint_ranges"][name] = rng
    model["model_nq"] = nq
    model["robot_leg_length_m"] = estimate_robot_leg_length_from_xml(root, warnings)
    if not np.isfinite(model["robot_leg_length_m"]):
        warnings.append("Could not estimate robot leg length from XML; scale-normalized human similarity metrics may be unavailable.")
    return model


def parse_range(text: Optional[str]) -> Tuple[float, float]:
    if not text:
        return (-math.inf, math.inf)
    parts = [float(x) for x in text.split()]
    if len(parts) >= 2:
        return (parts[0], parts[1])
    return (-math.inf, math.inf)


def estimate_robot_leg_length_from_xml(root: ET.Element, warnings: List[str]) -> float:
    body_parent: Dict[str, Optional[str]] = {}
    body_pos: Dict[str, np.ndarray] = {}

    def walk(body: ET.Element, parent: Optional[str]) -> None:
        name = body.get("name")
        if name:
            body_parent[name] = parent
            body_pos[name] = parse_vec(body.get("pos"), 3)
            parent = name
        for child in body.findall("body"):
            walk(child, parent)

    worldbody = root.find("worldbody")
    if worldbody is None:
        return NAN
    for body in worldbody.findall("body"):
        walk(body, None)

    values = []
    for foot in ["left_toe_link", "right_toe_link"]:
        values.append(path_length(body_parent, body_pos, "pelvis", foot))
    finite = [x for x in values if np.isfinite(x) and x > 0]
    if finite:
        return float(np.mean(finite))
    warnings.append(f"Robot leg-length paths unavailable from XML. Values: {values}")
    return NAN


def path_length(parent: Dict[str, Optional[str]], pos: Dict[str, np.ndarray], start: str, end: str) -> float:
    if start not in parent or end not in parent:
        return NAN
    total = 0.0
    cur: Optional[str] = end
    while cur is not None and cur != start:
        total += float(np.linalg.norm(pos.get(cur, np.zeros(3))))
        cur = parent.get(cur)
    return total if cur == start else NAN


def parse_vec(text: Optional[str], n: int) -> np.ndarray:
    if not text:
        return np.zeros(n)
    parts = [float(x) for x in text.split()]
    while len(parts) < n:
        parts.append(0.0)
    return np.asarray(parts[:n], dtype=float)


def load_source_reference(
    motion: str,
    source_path: Optional[Path],
    original_path: Optional[Path],
    config: Dict[str, Any],
    warnings: List[str],
) -> Optional[Dict[str, Any]]:
    if source_path is None:
        warnings.append(f"{motion}: no source-reference PKL with source_body_pos/source_body_names; similarity metrics unavailable.")
        return None
    try:
        data = load_pickle(source_path)
    except Exception as exc:
        warnings.append(f"{motion}: source-reference PKL load failed: {source_path}: {exc}")
        return None
    fps = source_fps(data, original_path)
    keypoints = extract_human_keypoints(data, config)
    if "pelvis" not in keypoints:
        warnings.append(f"{motion}: source reference has no pelvis/root keypoint; similarity metrics unavailable.")
        return None
    if len(keypoints) < 4:
        warnings.append(f"{motion}: source reference has only {len(keypoints)} semantic keypoints; similarity metrics may be sparse.")
    return {
        "path": str(source_path),
        "fps": fps,
        "keypoints": keypoints,
        "frame_count": frame_count_from_keypoints(keypoints),
    }


def source_fps(data: Dict[str, Any], original_path: Optional[Path]) -> float:
    meta = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    source_meta = meta.get("source_metadata") if isinstance(meta.get("source_metadata"), dict) else {}
    for value in [source_meta.get("source_fps"), source_meta.get("output_fps"), data.get("fps")]:
        try:
            x = float(np.asarray(value).reshape(-1)[0])
            if np.isfinite(x) and x > 0:
                return x
        except Exception:
            pass
    if original_path is not None and original_path.suffix.lower() == ".npz":
        try:
            npz = np.load(original_path, allow_pickle=True)
            x = float(np.asarray(npz.get("mocap_framerate")).reshape(-1)[0])
            if np.isfinite(x) and x > 0:
                return x
        except Exception:
            pass
    return 30.0


def extract_human_keypoints(data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, np.ndarray]:
    out: Dict[str, np.ndarray] = {}
    source_key = data.get("source_key_body_pos") if isinstance(data.get("source_key_body_pos"), dict) else {}
    body = array_or_none(data.get("source_body_pos"))
    names = [str(x) for x in data.get("source_body_names", [])]
    index = {name: i for i, name in enumerate(names)}
    for semantic, aliases in config["semantic_keypoints"].items():
        candidates = list(aliases.get("human", []))
        found = None
        for name in candidates:
            if name in source_key:
                found = array_or_none(source_key[name])
                break
        if found is None and body is not None:
            for name in candidates:
                if name in index:
                    found = body[:, index[name], :3]
                    break
        if found is not None and found.ndim == 2 and found.shape[1] >= 3:
            out[semantic] = np.asarray(found[:, :3], dtype=float)
    return out


def evaluate_one_motion(
    motion: str,
    method: str,
    path: Path,
    source: Optional[Dict[str, Any]],
    config: Dict[str, Any],
    model: Dict[str, Any],
    mujoco_available: bool,
    warnings: List[str],
) -> Dict[str, Any]:
    data = load_pickle(path)
    robot = extract_robot_motion(data, config)
    if mujoco_available:
        robot = enrich_robot_with_mujoco(robot, config, warnings, motion, method)
    threshold = config["thresholds"]
    target_fps = float(config["target_fps"])
    local_warnings: List[str] = []

    qpos_valid = qpos_validity(robot["qpos"], int(model.get("model_nq", -1)))
    dof_eval = resample_numeric(robot["dof_pos"], robot["fps"], target_fps) if robot["dof_pos"] is not None else None
    joint_metrics = joint_limit_metrics(dof_eval, robot["dof_names"], model, float(threshold["joint_limit_margin_rad"]))
    contact_metrics = contact_quality(robot, target_fps, threshold)
    stability_metrics = base_stability(robot, threshold)
    smooth_metrics = smoothness_metrics(dof_eval, target_fps)
    self_collision_metrics = self_collision_from_pkl(robot, target_fps)
    similarity_metrics = similarity_unavailable()

    if source is None:
        local_warnings.append("source_reference_unavailable: similarity metrics not computed")
    else:
        similarity_metrics = compute_similarity_metrics(source, robot, config, model, local_warnings)

    if not mujoco_available:
        local_warnings.append("mujoco_unavailable: contact, ground penetration, and self-collision use PKL fallback fields")
    if robot["qpos"] is not None and robot["qpos"].shape[1] >= 7 and not mujoco_available:
        local_warnings.append("mujoco_unavailable: root quaternion qvel not computed with mj_differentiatePos; smoothness uses dof_pos only")

    failure_reasons = []
    if not qpos_valid["qpos_valid"]:
        failure_reasons.append("invalid_qpos_shape")
    if joint_metrics["joint_limit_violation_frames"] > threshold["max_joint_limit_violation_frames"]:
        failure_reasons.append("joint_limit_violation")
    if finite_gt(contact_metrics["foot_penetration_max_m"], threshold["severe_penetration_m"]):
        failure_reasons.append("severe_foot_penetration")
    if finite_gt(self_collision_metrics["self_collision_frames"], threshold["max_self_collision_frames"]):
        failure_reasons.append("severe_self_collision")
    if stability_metrics["base_abnormal"]:
        failure_reasons.append("base_abnormal")
    if stability_metrics["fall_detected"]:
        failure_reasons.append("fall_detected")

    row: Dict[str, Any] = {
        "motion": motion,
        "method": method,
        "pkl_file": str(path),
        "source_reference_file": source["path"] if source else "",
        "seed_policy": config["methods"][method].get("seed_policy", ""),
        "gmr_seeded": int(is_gmr_seeded(path, data)),
        "frames_original": source["frame_count"] if source else NAN,
        "frames_robot": robot["frame_count"],
        "fps_original": source["fps"] if source else NAN,
        "fps_robot": robot["fps"],
        "target_fps": target_fps,
        "scale_human_to_robot": similarity_metrics.get("scale_human_to_robot", NAN),
        "robot_leg_length_m": model.get("robot_leg_length_m", NAN),
        "kinematic_success": int(len(failure_reasons) == 0),
        "failure_reasons": ";".join(failure_reasons),
        "warnings": ";".join(local_warnings),
        **qpos_valid,
        **joint_metrics,
        **similarity_metrics,
        **contact_metrics,
        **self_collision_metrics,
        **stability_metrics,
        **smooth_metrics,
    }
    for warning in local_warnings:
        warnings.append(f"{motion}/{method}: {warning}")
    return row


def load_pickle(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        data = pickle.load(f)
    if not isinstance(data, dict):
        raise ValueError("PKL is not a dict")
    return data


def extract_robot_motion(data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    fps = scalar(data.get("fps"), fallback_from_dt(data.get("dt"), float(config["target_fps"])))
    qpos = array_or_none(data.get("qpos"))
    dof = array_or_none(data.get("dof_pos"))
    if dof is None and qpos is not None and qpos.ndim == 2 and qpos.shape[1] > 7:
        dof = qpos[:, 7:]
    root_pos = array_or_none(data.get("root_pos"))
    if root_pos is None and qpos is not None and qpos.ndim == 2 and qpos.shape[1] >= 3:
        root_pos = qpos[:, :3]
    root_quat = array_or_none(data.get("root_quat"))
    if root_quat is None and qpos is not None and qpos.ndim == 2 and qpos.shape[1] >= 7:
        root_quat = qpos[:, 3:7]
    body_pos = array_or_none(data.get("body_pos"))
    body_names = [str(x) for x in data.get("body_names", [])]
    foot_pos = array_or_none(data.get("foot_pos"))
    contacts = array_or_none(data.get("contacts"))
    self_collision = data.get("self_collision")
    keypoints = extract_robot_keypoints(body_pos, body_names, root_pos, foot_pos, config)
    if root_pos is None and "pelvis" in keypoints:
        root_pos = keypoints["pelvis"]
    frame_count = first_frame_count([root_pos, body_pos, foot_pos, dof, qpos])
    return {
        "fps": fps,
        "frame_count": frame_count,
        "qpos": qpos,
        "dof_pos": dof,
        "dof_names": robot_dof_names(data, dof),
        "root_pos": root_pos,
        "root_quat": root_quat,
        "body_pos": body_pos,
        "body_names": body_names,
        "foot_pos": foot_pos,
        "foot_names": [str(x) for x in data.get("foot_names", [])],
        "contacts": contacts,
        "self_collision": self_collision,
        "keypoints": keypoints,
    }


def enrich_robot_with_mujoco(robot: Dict[str, Any], config: Dict[str, Any], warnings: List[str], motion: str, method: str) -> Dict[str, Any]:
    try:
        import mujoco
    except Exception as exc:
        warnings.append(f"{motion}/{method}: MuJoCo import failed during enrichment: {exc}")
        return robot

    qpos = robot.get("qpos")
    if qpos is None or qpos.ndim != 2:
        warnings.append(f"{motion}/{method}: MuJoCo enrichment skipped because qpos is unavailable.")
        return robot

    xml_path = host_path(config["robot_xml"])
    try:
        model = mujoco.MjModel.from_xml_path(str(xml_path))
        data = mujoco.MjData(model)
    except Exception as exc:
        warnings.append(f"{motion}/{method}: MuJoCo XML load failed: {xml_path}: {exc}")
        return robot

    if qpos.shape[1] != model.nq:
        warnings.append(f"{motion}/{method}: qpos width {qpos.shape[1]} != MuJoCo model.nq {model.nq}; MuJoCo FK uses overlapping prefix only.")

    body_names = mujoco_body_names(model, mujoco)
    body_index = {name: idx for idx, name in enumerate(body_names)}
    geom_names = mujoco_geom_names(model, mujoco)
    foot_geom_ids = foot_geom_candidates(model, mujoco, geom_names)
    ground_geom_ids = ground_geom_candidates(model, mujoco, geom_names, config)
    keypoint_body_ids = {
        semantic: first_mujoco_body_id(model, mujoco, aliases.get("robot", []))
        for semantic, aliases in config["semantic_keypoints"].items()
    }

    body_pos: List[np.ndarray] = []
    root_pos: List[np.ndarray] = []
    root_quat: List[np.ndarray] = []
    foot_pos: List[np.ndarray] = []
    foot_contacts: List[np.ndarray] = []
    self_collision: List[bool] = []
    keypoint_series: Dict[str, List[np.ndarray]] = {name: [] for name in keypoint_body_ids if keypoint_body_ids[name] is not None}

    for frame_qpos in np.asarray(qpos, dtype=float):
        data.qpos[:] = np.asarray(model.qpos0, dtype=float)
        n = min(model.nq, len(frame_qpos))
        data.qpos[:n] = frame_qpos[:n]
        mujoco.mj_forward(model, data)

        body_pos.append(np.asarray(data.xpos, dtype=float).copy())
        pelvis_id = body_index.get("pelvis", 1 if model.nbody > 1 else 0)
        root_pos.append(np.asarray(data.xpos[pelvis_id], dtype=float).copy())
        root_quat.append(np.asarray(data.xquat[pelvis_id], dtype=float).copy())

        for semantic, body_id in keypoint_body_ids.items():
            if body_id is not None:
                keypoint_series[semantic].append(np.asarray(data.xpos[body_id], dtype=float).copy())

        left_foot = lowest_foot_point(data, model, foot_geom_ids["left"])
        right_foot = lowest_foot_point(data, model, foot_geom_ids["right"])
        foot_pos.append(np.stack([left_foot, right_foot], axis=0))
        foot_contacts.append(
            np.asarray(
                [
                    has_foot_ground_contact(data, model, set(foot_geom_ids["left"]), ground_geom_ids),
                    has_foot_ground_contact(data, model, set(foot_geom_ids["right"]), ground_geom_ids),
                ],
                dtype=bool,
            )
        )
        self_collision.append(has_mujoco_self_collision(data, model, mujoco, geom_names, ground_geom_ids, config))

    robot["body_pos"] = np.asarray(body_pos, dtype=float)
    robot["body_names"] = body_names
    robot["root_pos"] = np.asarray(root_pos, dtype=float)
    robot["root_quat"] = np.asarray(root_quat, dtype=float)
    robot["foot_pos"] = np.asarray(foot_pos, dtype=float)
    robot["foot_names"] = ["left_foot_lowest_geom", "right_foot_lowest_geom"]
    robot["contacts"] = np.asarray(foot_contacts, dtype=bool)
    robot["self_collision"] = np.asarray(self_collision, dtype=bool)
    robot["keypoints"] = {name: np.asarray(values, dtype=float) for name, values in keypoint_series.items()}
    robot["keypoints"].setdefault("pelvis", robot["root_pos"])
    robot["mujoco_enriched"] = True
    return robot


def mujoco_body_names(model: Any, mujoco: Any) -> List[str]:
    names = []
    for body_id in range(model.nbody):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, body_id)
        names.append(name or f"body_{body_id}")
    return names


def mujoco_geom_names(model: Any, mujoco: Any) -> List[str]:
    names = []
    for geom_id in range(model.ngeom):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, geom_id)
        names.append(name or f"geom_{geom_id}")
    return names


def first_mujoco_body_id(model: Any, mujoco: Any, aliases: Sequence[str]) -> Optional[int]:
    for name in aliases:
        try:
            body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, str(name))
        except Exception:
            body_id = -1
        if body_id >= 0:
            return int(body_id)
    return None


def foot_geom_candidates(model: Any, mujoco: Any, geom_names: Sequence[str]) -> Dict[str, List[int]]:
    body_names = mujoco_body_names(model, mujoco)
    out = {"left": [], "right": []}
    for geom_id in range(model.ngeom):
        body_name = body_names[int(model.geom_bodyid[geom_id])]
        geom_name = geom_names[geom_id]
        for side in ["left", "right"]:
            if body_name.startswith(f"{side}_ankle_roll") or body_name.startswith(f"{side}_toe") or geom_name.startswith(f"{side}_toe") or geom_name.startswith(f"{side}_foot"):
                out[side].append(geom_id)
    for side in ["left", "right"]:
        if not out[side]:
            out[side] = [
                geom_id
                for geom_id in range(model.ngeom)
                if side in body_names[int(model.geom_bodyid[geom_id])] and ("ankle" in body_names[int(model.geom_bodyid[geom_id])] or "toe" in body_names[int(model.geom_bodyid[geom_id])])
            ]
        primitive = [geom_id for geom_id in out[side] if int(model.geom_type[geom_id]) != int(mujoco.mjtGeom.mjGEOM_MESH)]
        if primitive:
            out[side] = primitive
    return out


def ground_geom_candidates(model: Any, mujoco: Any, geom_names: Sequence[str], config: Dict[str, Any]) -> set[int]:
    names = {str(x).lower() for x in config.get("self_collision", {}).get("exclude_ground_geoms", ["floor", "ground", "plane"])}
    out = set()
    for geom_id, name in enumerate(geom_names):
        lname = name.lower()
        if any(token in lname for token in names):
            out.add(geom_id)
        if int(model.geom_bodyid[geom_id]) == 0 and int(model.geom_type[geom_id]) == int(mujoco.mjtGeom.mjGEOM_PLANE):
            out.add(geom_id)
    return out


def lowest_foot_point(data: Any, model: Any, geom_ids: Sequence[int]) -> np.ndarray:
    if not geom_ids:
        return np.asarray([NAN, NAN, NAN])
    best = None
    best_z = math.inf
    for geom_id in geom_ids:
        center = np.asarray(data.geom_xpos[geom_id], dtype=float)
        z = float(center[2] - geom_vertical_extent(model, geom_id))
        if z < best_z:
            best_z = z
            best = center.copy()
            best[2] = z
    return best if best is not None else np.asarray([NAN, NAN, NAN])


def geom_vertical_extent(model: Any, geom_id: int) -> float:
    size = np.asarray(model.geom_size[geom_id], dtype=float)
    if size.size == 0:
        return 0.0
    # Conservative approximation for contact primitives; foot contact spheres use size[0].
    return float(np.nanmax(size[:3])) if np.isfinite(size[:3]).any() else 0.0


def has_foot_ground_contact(data: Any, model: Any, foot_geom_ids: set[int], ground_geom_ids: set[int]) -> bool:
    if not foot_geom_ids or not ground_geom_ids:
        return False
    for idx in range(int(data.ncon)):
        contact = data.contact[idx]
        g1, g2 = int(contact.geom1), int(contact.geom2)
        if (g1 in foot_geom_ids and g2 in ground_geom_ids) or (g2 in foot_geom_ids and g1 in ground_geom_ids):
            return True
    return False


def has_mujoco_self_collision(data: Any, model: Any, mujoco: Any, geom_names: Sequence[str], ground_geom_ids: set[int], config: Dict[str, Any]) -> bool:
    excluded_pairs = {
        tuple(sorted((str(a), str(b))))
        for a, b in config.get("self_collision", {}).get("exclude_body_pairs", [])
        if isinstance(a, str) and isinstance(b, str)
    }
    body_names = mujoco_body_names(model, mujoco)
    for idx in range(int(data.ncon)):
        contact = data.contact[idx]
        g1, g2 = int(contact.geom1), int(contact.geom2)
        if g1 < 0 or g2 < 0 or g1 in ground_geom_ids or g2 in ground_geom_ids:
            continue
        b1, b2 = int(model.geom_bodyid[g1]), int(model.geom_bodyid[g2])
        if b1 == 0 or b2 == 0 or b1 == b2:
            continue
        if are_adjacent_bodies(model, b1, b2):
            continue
        pair = tuple(sorted((body_names[b1], body_names[b2])))
        if pair in excluded_pairs:
            continue
        return True
    return False


def are_adjacent_bodies(model: Any, body_a: int, body_b: int) -> bool:
    return int(model.body_parentid[body_a]) == body_b or int(model.body_parentid[body_b]) == body_a


def extract_robot_keypoints(
    body_pos: Optional[np.ndarray],
    body_names: List[str],
    root_pos: Optional[np.ndarray],
    foot_pos: Optional[np.ndarray],
    config: Dict[str, Any],
) -> Dict[str, np.ndarray]:
    out: Dict[str, np.ndarray] = {}
    index = {name: i for i, name in enumerate(body_names)}
    for semantic, aliases in config["semantic_keypoints"].items():
        found = None
        if body_pos is not None:
            for name in aliases.get("robot", []):
                if name in index:
                    found = body_pos[:, index[name], :3]
                    break
        if found is None and semantic == "pelvis" and root_pos is not None:
            found = root_pos
        if found is None and foot_pos is not None and semantic == "left_foot" and foot_pos.ndim == 3 and foot_pos.shape[1] >= 1:
            found = foot_pos[:, 0, :3]
        if found is None and foot_pos is not None and semantic == "right_foot" and foot_pos.ndim == 3 and foot_pos.shape[1] >= 2:
            found = foot_pos[:, 1, :3]
        if found is not None and found.ndim == 2 and found.shape[1] >= 3:
            out[semantic] = np.asarray(found[:, :3], dtype=float)
    return out


def robot_dof_names(data: Dict[str, Any], dof: Optional[np.ndarray]) -> List[str]:
    raw = data.get("dof_joint_names") or data.get("robot_joint_names") or data.get("joint_names") or []
    names = [str(x).replace("_hinge", "") for x in raw]
    if names and names[0] == "pelvis":
        names = names[1:]
    if dof is not None and len(names) != dof.shape[1]:
        if len(names) > dof.shape[1]:
            names = names[-dof.shape[1] :]
        else:
            names = names + [f"joint_{i}" for i in range(len(names), dof.shape[1])]
    return names


def is_gmr_seeded(path: Path, data: Dict[str, Any]) -> bool:
    if "no_gmr_seed" in path.name.lower():
        return False
    meta = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    source = str(meta.get("initial_qpos_source", "")).lower()
    return "gmr" in source


def qpos_validity(qpos: Optional[np.ndarray], model_nq: int) -> Dict[str, Any]:
    width = int(qpos.shape[1]) if qpos is not None and qpos.ndim == 2 else 0
    return {
        "qpos_width": width,
        "model_nq": model_nq,
        "qpos_valid": int(qpos is not None and qpos.ndim == 2 and width == model_nq),
    }


def joint_limit_metrics(dof: Optional[np.ndarray], names: List[str], model: Dict[str, Any], margin: float) -> Dict[str, Any]:
    if dof is None or dof.ndim != 2:
        return {
            "joint_limit_available": 0,
            "joint_limit_violation_frames": NAN,
            "joint_limit_violation_ratio": NAN,
            "joint_limit_violation_count": NAN,
            "max_joint_limit_violation_rad": NAN,
            "joint_limit_top_violations": "",
        }
    ranges = model.get("joint_ranges", {})
    lo = np.full(dof.shape[1], -math.inf)
    hi = np.full(dof.shape[1], math.inf)
    available = 0
    for i, name in enumerate(names[: dof.shape[1]]):
        if name in ranges:
            lo[i], hi[i] = ranges[name]
            if np.isfinite(lo[i]) or np.isfinite(hi[i]):
                available += 1
    under = np.maximum(0.0, (lo.reshape(1, -1) - margin) - dof)
    over = np.maximum(0.0, dof - (hi.reshape(1, -1) + margin))
    violation = np.maximum(under, over)
    bad = violation > 1e-9
    per_joint = np.sum(bad, axis=0)
    order = np.argsort(per_joint)[::-1][:8]
    top = "; ".join(f"{names[i] if i < len(names) else i}({int(per_joint[i])})" for i in order if per_joint[i] > 0)
    frames = int(np.sum(np.any(bad, axis=1)))
    return {
        "joint_limit_available": int(available > 0),
        "joint_limit_violation_frames": frames,
        "joint_limit_violation_ratio": frames / max(len(dof), 1),
        "joint_limit_violation_count": int(np.sum(bad)),
        "max_joint_limit_violation_rad": safe_max(violation),
        "joint_limit_top_violations": top,
    }


def compute_similarity_metrics(
    source: Dict[str, Any],
    robot: Dict[str, Any],
    config: Dict[str, Any],
    model: Dict[str, Any],
    warnings: List[str],
) -> Dict[str, Any]:
    target_fps = float(config["target_fps"])
    human = resample_keypoints(source["keypoints"], source["fps"], target_fps)
    robot_kp = resample_keypoints(robot["keypoints"], robot["fps"], target_fps)
    human_full_frames = frame_count_from_keypoints(human)
    robot_full_frames = frame_count_from_keypoints(robot_kp)
    human_full_duration = (human_full_frames - 1) / target_fps if human_full_frames > 1 else 0.0
    robot_full_duration = (robot_full_frames - 1) / target_fps if robot_full_frames > 1 else 0.0
    n = min(frame_count_from_keypoints(human), frame_count_from_keypoints(robot_kp))
    if n <= 1 or "pelvis" not in human or "pelvis" not in robot_kp:
        warnings.append("similarity_unavailable: missing root keypoints or insufficient common frames")
        return similarity_unavailable()
    human = trim_keypoints(human, n)
    robot_kp = trim_keypoints(robot_kp, n)
    human_leg = human_leg_length(human)
    robot_leg = float(model.get("robot_leg_length_m", NAN))
    scale = robot_leg / human_leg if np.isfinite(robot_leg) and np.isfinite(human_leg) and human_leg > 1e-9 else NAN
    if not np.isfinite(scale):
        warnings.append("scale_unavailable: human or robot leg length unavailable")
        return similarity_unavailable()

    human_yaw = initial_heading(human["pelvis"])
    robot_yaw = initial_heading(robot_kp["pelvis"])
    h_rel = relative_keypoints(human, "pelvis", -human_yaw, scale)
    r_rel = relative_keypoints(robot_kp, "pelvis", -robot_yaw, 1.0)
    names = [name for name in config["semantic_keypoints"] if name in h_rel and name in r_rel]
    if not names:
        warnings.append("similarity_unavailable: no shared semantic keypoints after mapping")
        return similarity_unavailable(scale)

    per_name = {}
    distances = []
    for name in names:
        d = np.linalg.norm(r_rel[name] - h_rel[name], axis=1)
        per_name[f"{name}_root_relative_error_mm"] = safe_mean(d) * 1000.0
        if name != "pelvis":
            distances.append(d)
    all_dist = np.concatenate(distances) if distances else np.asarray([NAN])

    bone_angles = bone_direction_errors(h_rel, r_rel, config["bones"])
    ee_names = [name for name in config["end_effectors"] if name in h_rel and name in r_rel]
    ee_dist = []
    for name in ee_names:
        ee_dist.append(np.linalg.norm(r_rel[name] - h_rel[name], axis=1))
    ee = np.concatenate(ee_dist) if ee_dist else np.asarray([NAN])
    root_traj = normalized_root_trajectory_metrics(human["pelvis"], robot_kp["pelvis"], human_yaw, robot_yaw, scale, robot_leg, target_fps)
    rhythm = motion_rhythm_metrics(human, robot_kp, target_fps, config["thresholds"], scale, human_full_duration, robot_full_duration)

    return {
        "similarity_available": 1,
        "scale_human_to_robot": scale,
        "human_leg_length_m": human_leg,
        "shared_keypoint_count": len(names),
        "root_relative_keypoint_error_mm": safe_mean(all_dist) * 1000.0,
        "bone_direction_error_deg": safe_mean(bone_angles),
        "end_effector_relative_error_mm": safe_mean(ee) * 1000.0,
        **per_name,
        **root_traj,
        **rhythm,
    }


def similarity_unavailable(scale: float = NAN) -> Dict[str, Any]:
    return {
        "similarity_available": 0,
        "scale_human_to_robot": scale,
        "human_leg_length_m": NAN,
        "shared_keypoint_count": 0,
        "root_relative_keypoint_error_mm": NAN,
        "bone_direction_error_deg": NAN,
        "end_effector_relative_error_mm": NAN,
        "normalized_root_trajectory_error": NAN,
        "root_velocity_direction_error_deg": NAN,
        "root_speed_profile_error": NAN,
        "root_yaw_change_error_deg": NAN,
        "motion_duration_error_s": NAN,
        "motion_duration_error_ratio": NAN,
        "foot_contact_timing_mismatch_ratio": NAN,
        "keypoint_velocity_peak_timing_error_s": NAN,
    }


def resample_keypoints(keypoints: Dict[str, np.ndarray], fps: float, target_fps: float) -> Dict[str, np.ndarray]:
    return {name: resample_numeric(arr, fps, target_fps) for name, arr in keypoints.items()}


def trim_keypoints(keypoints: Dict[str, np.ndarray], n: int) -> Dict[str, np.ndarray]:
    return {name: arr[:n] for name, arr in keypoints.items() if arr is not None and len(arr) >= n}


def relative_keypoints(keypoints: Dict[str, np.ndarray], root_name: str, yaw: float, scale: float) -> Dict[str, np.ndarray]:
    root = keypoints[root_name]
    out = {}
    for name, arr in keypoints.items():
        rel = (arr - root) * scale
        out[name] = rotate_xy(rel, yaw)
    return out


def human_leg_length(keypoints: Dict[str, np.ndarray]) -> float:
    root = keypoints.get("pelvis")
    if root is None:
        return NAN
    values = []
    for foot in ["left_foot", "right_foot"]:
        if foot in keypoints:
            values.append(np.linalg.norm(keypoints[foot] - root, axis=1))
    if not values:
        return NAN
    return safe_median(np.concatenate(values))


def initial_heading(root: np.ndarray) -> float:
    if root is None or len(root) < 2:
        return 0.0
    idx = min(len(root) - 1, 30)
    delta = root[idx, :2] - root[0, :2]
    if np.linalg.norm(delta) < 1e-6:
        diffs = np.diff(root[:, :2], axis=0)
        norms = np.linalg.norm(diffs, axis=1)
        if np.nanmax(norms) > 1e-6:
            delta = diffs[int(np.nanargmax(norms))]
    if np.linalg.norm(delta) < 1e-6:
        return 0.0
    return float(math.atan2(delta[1], delta[0]))


def rotate_xy(value: np.ndarray, yaw: float) -> np.ndarray:
    c, s = math.cos(yaw), math.sin(yaw)
    rot = np.asarray([[c, -s], [s, c]], dtype=float)
    out = np.asarray(value, dtype=float).copy()
    flat = out.reshape(-1, out.shape[-1])
    flat[:, :2] = flat[:, :2] @ rot.T
    return flat.reshape(out.shape)


def bone_direction_errors(human_rel: Dict[str, np.ndarray], robot_rel: Dict[str, np.ndarray], bones: Sequence[Sequence[str]]) -> np.ndarray:
    angles = []
    for a, b in bones:
        if a not in human_rel or b not in human_rel or a not in robot_rel or b not in robot_rel:
            continue
        hv = human_rel[b] - human_rel[a]
        rv = robot_rel[b] - robot_rel[a]
        hnorm = np.linalg.norm(hv, axis=1)
        rnorm = np.linalg.norm(rv, axis=1)
        mask = (hnorm > 1e-9) & (rnorm > 1e-9)
        if not np.any(mask):
            continue
        hu = hv[mask] / hnorm[mask, None]
        ru = rv[mask] / rnorm[mask, None]
        cos = np.sum(hu * ru, axis=1)
        angles.append(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))
    return np.concatenate(angles) if angles else np.asarray([NAN])


def normalized_root_trajectory_metrics(
    human_root: np.ndarray,
    robot_root: np.ndarray,
    human_yaw: float,
    robot_yaw: float,
    scale: float,
    robot_leg: float,
    fps: float,
) -> Dict[str, Any]:
    n = min(len(human_root), len(robot_root))
    h = rotate_xy((human_root[:n] - human_root[0]) * scale, -human_yaw)
    r = rotate_xy(robot_root[:n] - robot_root[0], -robot_yaw)
    denom = max(robot_leg, trajectory_length(h[:, :2]), 1e-6)
    traj_err = safe_mean(np.linalg.norm(r[:, :2] - h[:, :2], axis=1)) / denom
    hv = np.diff(h[:, :2], axis=0) * fps
    rv = np.diff(r[:, :2], axis=0) * fps
    hs = np.linalg.norm(hv, axis=1)
    rs = np.linalg.norm(rv, axis=1)
    mask = (hs > 1e-5) & (rs > 1e-5)
    if np.any(mask):
        cos = np.sum(hv[mask] * rv[mask], axis=1) / np.maximum(hs[mask] * rs[mask], 1e-9)
        dir_err = safe_mean(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))
    else:
        dir_err = NAN
    speed_err = safe_mean(np.abs(rs - hs)) / max(safe_mean(hs), 1e-6) if len(hs) and np.isfinite(safe_mean(hs)) else NAN
    h_yaw_change = path_heading_change(h[:, :2])
    r_yaw_change = path_heading_change(r[:, :2])
    yaw_err = abs(wrap_pi(r_yaw_change - h_yaw_change)) * 180.0 / math.pi if np.isfinite(h_yaw_change) and np.isfinite(r_yaw_change) else NAN
    return {
        "normalized_root_trajectory_error": traj_err,
        "root_velocity_direction_error_deg": dir_err,
        "root_speed_profile_error": speed_err,
        "root_yaw_change_error_deg": yaw_err,
    }


def motion_rhythm_metrics(
    human: Dict[str, np.ndarray],
    robot: Dict[str, np.ndarray],
    fps: float,
    thresholds: Dict[str, Any],
    scale: float,
    human_full_duration: float,
    robot_full_duration: float,
) -> Dict[str, Any]:
    n = min(frame_count_from_keypoints(human), frame_count_from_keypoints(robot))
    duration_h = human_full_duration
    duration_r = robot_full_duration
    contact_mismatch = []
    for side in ["left_foot", "right_foot"]:
        if side not in human or side not in robot:
            continue
        hc = infer_contact_from_foot(human[side][:n] * scale, fps, None, thresholds)
        rc = infer_contact_from_foot(robot[side][:n], fps, float(thresholds["floor_height_m"]), thresholds)
        contact_mismatch.append(np.mean(hc != rc) if len(hc) and len(rc) else NAN)
    peak_errors = []
    for key in ["left_hand", "right_hand", "left_foot", "right_foot", "head"]:
        if key not in human or key not in robot or n < 3:
            continue
        hs = speed_series(human[key][:n] * scale, fps)
        rs = speed_series(robot[key][:n], fps)
        if len(hs) and len(rs):
            peak_errors.append(abs(int(np.nanargmax(hs)) - int(np.nanargmax(rs))) / fps)
    return {
        "motion_duration_error_s": abs(duration_r - duration_h),
        "motion_duration_error_ratio": abs(duration_r - duration_h) / max(duration_h, 1e-9),
        "foot_contact_timing_mismatch_ratio": safe_mean(contact_mismatch),
        "keypoint_velocity_peak_timing_error_s": safe_mean(peak_errors),
    }


def contact_quality(robot: Dict[str, Any], fps: float, thresholds: Dict[str, Any]) -> Dict[str, Any]:
    foot = resample_numeric(robot["foot_pos"], robot["fps"], fps) if robot["foot_pos"] is not None else None
    contacts = resample_bool(robot["contacts"], robot["fps"], fps) if robot["contacts"] is not None else None
    if foot is None or foot.ndim != 3 or foot.shape[-1] < 3:
        return {
            "contact_metrics_available": 0,
            "foot_skating_frames": NAN,
            "foot_skating_distance_m": NAN,
            "foot_skating_mean_velocity_mps": NAN,
            "foot_penetration_max_m": NAN,
            "foot_penetration_mean_m": NAN,
            "foot_penetration_frames": NAN,
            "contact_frame_ratio": NAN,
        }
    floor = float(thresholds["floor_height_m"])
    contact_height = float(thresholds["foot_contact_height_m"])
    skate_vel = float(thresholds["skating_velocity_threshold_mps"])
    skating_frames = 0
    skating_dist = 0.0
    skating_vel = []
    contact_any = []
    depths = np.maximum(0.0, floor - foot[..., 2])
    for i in range(min(2, foot.shape[1])):
        f = foot[:, i, :3]
        if contacts is not None and contacts.ndim == 2 and contacts.shape[0] == foot.shape[0] and contacts.shape[1] > i:
            contact = contacts[:, i].astype(bool)
        else:
            contact = f[:, 2] < floor + contact_height
        contact_any.append(contact)
        if len(f) > 1:
            step = np.linalg.norm(np.diff(f[:, :2], axis=0), axis=1)
            vel = step * fps
            contact_step = contact[:-1] & contact[1:]
            skate = contact_step & (vel > skate_vel)
            skating_frames += int(np.sum(skate))
            skating_dist += float(np.sum(step[skate]))
            if np.any(skate):
                skating_vel.extend(vel[skate].tolist())
    contact_stack = np.stack(contact_any, axis=1) if contact_any else np.zeros((len(foot), 0), dtype=bool)
    per_frame_depth = np.nanmax(depths.reshape(depths.shape[0], -1), axis=1)
    return {
        "contact_metrics_available": 1,
        "foot_skating_frames": skating_frames,
        "foot_skating_distance_m": skating_dist,
        "foot_skating_mean_velocity_mps": safe_mean(skating_vel),
        "foot_penetration_max_m": safe_max(depths),
        "foot_penetration_mean_m": safe_mean(depths),
        "foot_penetration_frames": int(np.sum(per_frame_depth > 0.0)),
        "contact_frame_ratio": float(np.mean(np.any(contact_stack, axis=1))) if contact_stack.size else NAN,
    }


def self_collision_from_pkl(robot: Dict[str, Any], target_fps: float) -> Dict[str, Any]:
    value = robot.get("self_collision")
    if value is None:
        return {
            "self_collision_available": 0,
            "self_collision_frames": NAN,
            "self_collision_ratio": NAN,
        }
    arr = resample_bool(np.asarray(value).astype(bool), robot["fps"], target_fps)
    arr = np.asarray(arr).astype(bool).reshape(-1)
    return {
        "self_collision_available": 1,
        "self_collision_frames": int(np.sum(arr)),
        "self_collision_ratio": float(np.mean(arr)) if len(arr) else NAN,
    }


def base_stability(robot: Dict[str, Any], thresholds: Dict[str, Any]) -> Dict[str, Any]:
    root = robot["root_pos"]
    quat = robot["root_quat"]
    if root is None or root.ndim != 2 or root.shape[1] < 3:
        return {
            "base_metrics_available": 0,
            "base_height_mean_m": NAN,
            "base_height_std_m": NAN,
            "base_roll_mean_deg": NAN,
            "base_pitch_mean_deg": NAN,
            "base_roll_std_deg": NAN,
            "base_pitch_std_deg": NAN,
            "fall_frames": NAN,
            "fall_detected": 0,
            "base_abnormal": 0,
        }
    z = root[:, 2]
    roll = np.full(len(z), NAN)
    pitch = np.full(len(z), NAN)
    if quat is not None and quat.ndim == 2 and quat.shape[1] == 4:
        rp = np.asarray([quat_to_roll_pitch(q) for q in quat[: len(z)]])
        roll = rp[:, 0]
        pitch = rp[:, 1]
    tilt = np.maximum(np.abs(roll), np.abs(pitch))
    fall = (z < float(thresholds["fall_base_height_m"])) | (tilt > float(thresholds["fall_tilt_deg"]))
    base_abnormal = (
        safe_min(z) < float(thresholds["min_base_height_m"])
        or safe_std(z) > float(thresholds["max_base_height_std_m"])
        or safe_std(roll) > float(thresholds["max_base_roll_pitch_std_deg"])
        or safe_std(pitch) > float(thresholds["max_base_roll_pitch_std_deg"])
    )
    return {
        "base_metrics_available": 1,
        "base_height_mean_m": safe_mean(z),
        "base_height_std_m": safe_std(z),
        "base_roll_mean_deg": safe_mean(roll),
        "base_pitch_mean_deg": safe_mean(pitch),
        "base_roll_std_deg": safe_std(roll),
        "base_pitch_std_deg": safe_std(pitch),
        "fall_frames": int(np.sum(fall)),
        "fall_detected": int(np.any(fall)),
        "base_abnormal": int(base_abnormal),
    }


def smoothness_metrics(dof: Optional[np.ndarray], fps: float) -> Dict[str, Any]:
    if dof is None or dof.ndim != 2 or len(dof) < 2:
        return {
            "smoothness_available": 0,
            "mean_joint_velocity_rad_s": NAN,
            "mean_joint_acceleration_rad_s2": NAN,
            "mean_joint_jerk_rad_s3": NAN,
            "max_joint_jerk_rad_s3": NAN,
        }
    vel = np.diff(dof, axis=0) * fps
    acc = np.diff(vel, axis=0) * fps if len(vel) > 1 else np.zeros((0, dof.shape[1]))
    jerk = np.diff(acc, axis=0) * fps if len(acc) > 1 else np.zeros((0, dof.shape[1]))
    return {
        "smoothness_available": 1,
        "mean_joint_velocity_rad_s": safe_mean(np.abs(vel)),
        "mean_joint_acceleration_rad_s2": safe_mean(np.abs(acc)),
        "mean_joint_jerk_rad_s3": safe_mean(np.abs(jerk)),
        "max_joint_jerk_rad_s3": safe_max(np.abs(jerk)),
    }


def missing_result_row(motion: str, method: str, original_path: Path, reason: str) -> Dict[str, Any]:
    return {
        "motion": motion,
        "method": method,
        "pkl_file": "",
        "source_reference_file": "",
        "seed_policy": "",
        "gmr_seeded": 0,
        "frames_original": NAN,
        "frames_robot": 0,
        "fps_original": NAN,
        "fps_robot": NAN,
        "target_fps": NAN,
        "scale_human_to_robot": NAN,
        "robot_leg_length_m": NAN,
        "kinematic_success": 0,
        "failure_reasons": reason,
        "warnings": reason,
        "qpos_width": 0,
        "model_nq": 0,
        "qpos_valid": 0,
        "missing": 1,
        "original_file": str(original_path),
    }


def summarize_by_method(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    metrics = [
        "kinematic_success",
        "similarity_available",
        "root_relative_keypoint_error_mm",
        "bone_direction_error_deg",
        "end_effector_relative_error_mm",
        "normalized_root_trajectory_error",
        "root_velocity_direction_error_deg",
        "root_speed_profile_error",
        "root_yaw_change_error_deg",
        "motion_duration_error_s",
        "foot_contact_timing_mismatch_ratio",
        "keypoint_velocity_peak_timing_error_s",
        "qpos_valid",
        "joint_limit_violation_frames",
        "joint_limit_violation_ratio",
        "max_joint_limit_violation_rad",
        "foot_skating_frames",
        "foot_skating_distance_m",
        "foot_skating_mean_velocity_mps",
        "foot_penetration_max_m",
        "foot_penetration_mean_m",
        "self_collision_frames",
        "self_collision_ratio",
        "base_height_mean_m",
        "base_height_std_m",
        "base_roll_std_deg",
        "base_pitch_std_deg",
        "fall_frames",
        "mean_joint_velocity_rad_s",
        "mean_joint_acceleration_rad_s2",
        "mean_joint_jerk_rad_s3",
        "max_joint_jerk_rad_s3",
    ]
    out = []
    for method in METHOD_ORDER:
        subset = [row for row in rows if row.get("method") == method]
        valid = [row for row in subset if not row.get("missing")]
        row = {
            "method": method,
            "motion_count_expected": len(subset),
            "evaluated_count": len(valid),
            "missing_count": len(subset) - len(valid),
            "kinematic_success_count": int(sum(int(x.get("kinematic_success", 0)) for x in subset)),
            "kinematic_failure_count": int(sum(1 for x in subset if not x.get("missing") and int(x.get("kinematic_success", 0)) == 0)),
        }
        row["kinematic_success_rate"] = row["kinematic_success_count"] / max(len(subset), 1)
        for metric in metrics:
            row[f"mean_{metric}"] = safe_mean([x.get(metric, NAN) for x in valid])
            row[f"median_{metric}"] = safe_median([x.get(metric, NAN) for x in valid])
        out.append(row)
    return out


def success_failure_counts(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for method in METHOD_ORDER:
        subset = [row for row in rows if row.get("method") == method]
        missing = sum(1 for row in subset if row.get("missing"))
        success = sum(int(row.get("kinematic_success", 0)) for row in subset)
        failed = len(subset) - missing - success
        out.append(
            {
                "method": method,
                "expected_count": len(subset),
                "success_count": success,
                "failure_count": failed,
                "missing_count": missing,
                "kinematic_success_rate": success / max(len(subset), 1),
            }
        )
    return out


def failure_reason_counts(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    counter: Dict[Tuple[str, str], int] = Counter()
    for row in rows:
        method = row.get("method", "")
        reasons = [x for x in str(row.get("failure_reasons", "")).split(";") if x]
        for reason in reasons:
            counter[(method, reason)] += 1
    return [{"method": method, "failure_reason": reason, "count": count} for (method, reason), count in sorted(counter.items())]


def make_figures(rows: List[Dict[str, Any]], summary: List[Dict[str, Any]], out_dir: Path, warnings: List[str]) -> List[str]:
    figure_specs = [
        ("root_relative_keypoint_error_mm", "Root-relative Keypoint Error", "mm"),
        ("bone_direction_error_deg", "Bone Direction Error", "deg"),
        ("end_effector_relative_error_mm", "End-effector Relative Error", "mm"),
        ("normalized_root_trajectory_error", "Normalized Root Trajectory Error", "ratio"),
        ("foot_skating_distance_m", "Foot Skating Distance", "m"),
        ("foot_penetration_max_m", "Max Foot Penetration", "m"),
        ("self_collision_frames", "Self-collision Frames", "frames"),
        ("joint_limit_violation_frames", "Joint-limit Violation Frames", "frames"),
        ("mean_joint_jerk_rad_s3", "Mean Joint Jerk", "rad/s^3"),
    ]
    figures = []
    for metric, title, unit in figure_specs:
        path = out_dir / f"{metric}_by_motion.png"
        if draw_grouped_bar_by_motion(rows, metric, title, unit, path):
            figures.append(str(path))
        else:
            warnings.append(f"Figure skipped for {metric}: no finite values or Pillow unavailable.")
    path = out_dir / "kinematic_success_rate_by_method.png"
    if draw_summary_bar(summary, "kinematic_success_rate", "Kinematic Success Rate", "rate", path):
        figures.append(str(path))
    return figures


def draw_grouped_bar_by_motion(rows: List[Dict[str, Any]], metric: str, title: str, unit: str, path: Path) -> bool:
    if Image is None:
        return False
    motions = sorted({row["motion"] for row in rows})
    data = {(row["motion"], row["method"]): row.get(metric, NAN) for row in rows}
    values = [float(v) for v in data.values() if is_finite_number(v)]
    if not values:
        return False
    width, height = 1800, 980
    ml, mr, mt, mb = 110, 70, 145, 150
    plot_w, plot_h = width - ml - mr, height - mt - mb
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    title_font = load_font(34, True)
    font = load_font(22, False)
    small = load_font(17, False)
    label_font = load_font(15, False)
    y_ticks = nice_ticks(max(values))
    y_max = y_ticks[-1] if y_ticks else max(values)
    draw.text((ml, 38), title, fill="#222222", font=title_font)
    draw.text((ml, 80), f"Same source motions, target fps, keypoint map, alignment, scale rule, and thresholds | unit: {unit}", fill="#555555", font=font)
    for tick in y_ticks:
        y = mt + plot_h - (tick / y_max) * plot_h if y_max > 0 else mt + plot_h
        draw.line((ml, y, width - mr, y), fill="#E5E7EB", width=1)
        draw.text((ml - 18, y - 10), f"{tick:g}", fill="#555555", font=small, anchor="ra")
    draw.line((ml, mt, ml, mt + plot_h), fill="#333333", width=2)
    draw.line((ml, mt + plot_h, width - mr, mt + plot_h), fill="#333333", width=2)
    group_w = plot_w / max(len(motions), 1)
    bar_w = min(38, group_w * 0.2)
    offsets = [-bar_w * 1.2, 0.0, bar_w * 1.2]
    for i, motion in enumerate(motions):
        center = ml + group_w * (i + 0.5)
        for method, offset in zip(METHOD_ORDER, offsets):
            v = data.get((motion, method), NAN)
            if not is_finite_number(v):
                continue
            v = float(v)
            bar_h = (v / y_max) * plot_h if y_max > 0 else 0.0
            x0 = center + offset - bar_w / 2
            x1 = center + offset + bar_w / 2
            y0 = mt + plot_h - bar_h
            y1 = mt + plot_h
            draw.rounded_rectangle((x0, y0, x1, y1), radius=4, fill=METHOD_COLORS[method])
            if v > 0:
                label = compact_number(v)
                draw.text((x0 + bar_w / 2, max(mt + 15, y0 - 18)), label, fill="#222222", font=label_font, anchor="ma")
        draw.text((center, mt + plot_h + 42), motion, fill="#333333", font=font, anchor="mm")
    draw.text((ml, height - 50), "Motion ID", fill="#333333", font=font)
    draw.text((ml, mt - 24), unit, fill="#333333", font=font)
    draw_legend(draw, width - mr - 520, 45, small)
    img.save(path)
    return True


def draw_summary_bar(summary: List[Dict[str, Any]], metric: str, title: str, unit: str, path: Path) -> bool:
    if Image is None:
        return False
    values = [row.get(metric, NAN) for row in summary if is_finite_number(row.get(metric, NAN))]
    if not values:
        return False
    width, height = 1100, 720
    ml, mr, mt, mb = 110, 60, 130, 120
    plot_w, plot_h = width - ml - mr, height - mt - mb
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    title_font = load_font(32, True)
    font = load_font(21)
    small = load_font(16)
    y_max = 1.0 if unit == "rate" else max(values)
    ticks = [0, 0.25, 0.5, 0.75, 1.0] if unit == "rate" else nice_ticks(y_max)
    draw.text((ml, 40), title, fill="#222222", font=title_font)
    draw.text((ml, 80), "kinematic_success_rate is based on kinematic validity, not dynamic tracking.", fill="#555555", font=font)
    for tick in ticks:
        y = mt + plot_h - (tick / y_max) * plot_h if y_max > 0 else mt + plot_h
        draw.line((ml, y, width - mr, y), fill="#E5E7EB")
        draw.text((ml - 18, y - 10), f"{tick:.2f}" if unit == "rate" else f"{tick:g}", fill="#555555", font=small, anchor="ra")
    group_w = plot_w / len(METHOD_ORDER)
    bar_w = min(80, group_w * 0.45)
    for i, method in enumerate(METHOD_ORDER):
        row = next((x for x in summary if x["method"] == method), {})
        v = row.get(metric, NAN)
        if not is_finite_number(v):
            continue
        v = float(v)
        center = ml + group_w * (i + 0.5)
        h = (v / y_max) * plot_h if y_max > 0 else 0.0
        draw.rounded_rectangle((center - bar_w / 2, mt + plot_h - h, center + bar_w / 2, mt + plot_h), radius=5, fill=METHOD_COLORS[method])
        draw.text((center, mt + plot_h - h - 18), f"{v:.3f}", fill="#222222", font=small, anchor="ma")
        draw.text((center, mt + plot_h + 38), method, fill="#333333", font=font, anchor="mm")
    draw.line((ml, mt, ml, mt + plot_h), fill="#333333", width=2)
    draw.line((ml, mt + plot_h, width - mr, mt + plot_h), fill="#333333", width=2)
    img.save(path)
    return True


def draw_legend(draw: Any, x: int, y: int, font: Any) -> None:
    for i, method in enumerate(METHOD_ORDER):
        xx = x + i * 175
        draw.rounded_rectangle((xx, y + 4, xx + 28, y + 24), radius=4, fill=METHOD_COLORS[method])
        draw.text((xx + 38, y), method, fill="#333333", font=font)


def write_report(
    path: Path,
    config: Dict[str, Any],
    model: Dict[str, Any],
    rows: List[Dict[str, Any]],
    summary: List[Dict[str, Any]],
    counts: List[Dict[str, Any]],
    failures: List[Dict[str, Any]],
    figures: List[str],
    warnings: List[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Fair Retargeting Evaluation Report",
        "",
        "This report compares Direct Mapping, Basic IK, and GMR with the same original motions, Unitree G1 XML, target fps, semantic keypoint map, scale rule, root/yaw alignment rule, and thresholds.",
        "",
        "Important: `kinematic_success_rate` is not dynamic tracking success. It only means the qpos file is complete enough and passes kinematic checks: qpos shape, joint limits, foot penetration, self-collision, base stability, and fall detection.",
        "",
        "## Data and Configuration",
        "",
        f"- Original motion root: `{config['original_motion_root']}`",
        f"- Robot XML: `{config['robot_xml']}`",
        f"- XML-derived model_nq: `{model.get('model_nq')}`",
        f"- XML-derived robot leg length: `{format_num(model.get('robot_leg_length_m'), 4)}` m",
        f"- Target fps: `{config['target_fps']}`",
        "- Human source reference: `source_body_pos/source_body_names` from the shared source-reference PKLs, not GMR robot output.",
        "",
        "## Method Summary",
        "",
        "|method|expected|evaluated|missing|kinematic_success_rate|pose_error_mm|bone_error_deg|ee_error_mm|foot_skating_m|penetration_m|self_collision_frames|joint_limit_frames|mean_jerk|",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        lines.append(
            f"|{row['method']}|{row['motion_count_expected']}|{row['evaluated_count']}|{row['missing_count']}|"
            f"{format_num(row['kinematic_success_rate'], 3)}|"
            f"{format_num(row.get('mean_root_relative_keypoint_error_mm'), 3)}|"
            f"{format_num(row.get('mean_bone_direction_error_deg'), 3)}|"
            f"{format_num(row.get('mean_end_effector_relative_error_mm'), 3)}|"
            f"{format_num(row.get('mean_foot_skating_distance_m'), 6)}|"
            f"{format_num(row.get('mean_foot_penetration_max_m'), 6)}|"
            f"{format_num(row.get('mean_self_collision_frames'), 3)}|"
            f"{format_num(row.get('mean_joint_limit_violation_frames'), 3)}|"
            f"{format_num(row.get('mean_mean_joint_jerk_rad_s3'), 3)}|"
        )
    lines += [
        "",
        "## Success / Failure / Missing",
        "",
        "|method|success|failure|missing|kinematic_success_rate|",
        "|---|---:|---:|---:|---:|",
    ]
    for row in counts:
        lines.append(
            f"|{row['method']}|{row['success_count']}|{row['failure_count']}|{row['missing_count']}|{format_num(row['kinematic_success_rate'], 3)}|"
        )
    lines += [
        "",
        "## Failure Reason Counts",
        "",
        "|method|failure_reason|count|",
        "|---|---|---:|",
    ]
    if failures:
        for row in failures:
            lines.append(f"|{row['method']}|{row['failure_reason']}|{row['count']}|")
    else:
        lines.append("|all|none|0|")

    lines += [
        "",
        "## Category Winners",
        "",
        f"- Most similar to original motion: {winner(summary, 'mean_root_relative_keypoint_error_mm', lower=True)}",
        f"- Least foot skating: {winner(summary, 'mean_foot_skating_distance_m', lower=True)}",
        f"- Least foot penetration: {winner(summary, 'mean_foot_penetration_max_m', lower=True)}",
        f"- Least self-collision: {winner(summary, 'mean_self_collision_frames', lower=True)}",
        f"- Least joint-limit violation: {winner(summary, 'mean_joint_limit_violation_frames', lower=True)}",
        f"- Smoothest motion by mean jerk: {winner(summary, 'mean_mean_joint_jerk_rad_s3', lower=True)}",
        f"- Highest kinematic_success_rate: {winner(summary, 'kinematic_success_rate', lower=False)}",
        "",
        "These are separate conclusions; no single overall score is used to declare a universal best method.",
        "",
        "## Figures",
        "",
    ]
    for fig in figures:
        lines.append(f"- `{fig}`")
    lines += [
        "",
        "## Warnings",
        "",
    ]
    if warnings:
        for item in warnings[:80]:
            lines.append(f"- {item}")
        if len(warnings) > 80:
            lines.append(f"- ... {len(warnings) - 80} additional warnings. See `warnings.txt`.")
    else:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def winner(summary: List[Dict[str, Any]], key: str, *, lower: bool) -> str:
    candidates = [(row["method"], row.get(key, NAN)) for row in summary if is_finite_number(row.get(key, NAN))]
    if not candidates:
        return "N/A"
    best_value = (min if lower else max)(value for _, value in candidates)
    tied = [method for method, value in candidates if abs(float(value) - float(best_value)) <= 1e-9]
    return f"{' / '.join(tied)} ({format_num(best_value, 3)})"


def write_warnings(path: Path, warnings: List[str]) -> None:
    path.write_text("\n".join(warnings) + ("\n" if warnings else ""), encoding="utf-8")


def write_json(path: Path, rows: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(make_jsonable(rows), indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: List[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key, "")) for key in fieldnames})


def make_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): make_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [make_jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def csv_value(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
        return "" if not math.isfinite(value) else value
    return value


def array_or_none(value: Any) -> Optional[np.ndarray]:
    if value is None:
        return None
    try:
        arr = np.asarray(value, dtype=float)
    except Exception:
        return None
    return arr


def scalar(value: Any, default: float) -> float:
    try:
        out = float(np.asarray(value).reshape(-1)[0])
        return out if np.isfinite(out) and out > 0 else default
    except Exception:
        return default


def fallback_from_dt(value: Any, default: float) -> float:
    try:
        dt = float(np.asarray(value).reshape(-1)[0])
        return 1.0 / dt if dt > 0 else default
    except Exception:
        return default


def first_frame_count(values: Sequence[Optional[np.ndarray]]) -> int:
    for value in values:
        if value is not None and getattr(value, "ndim", 0) > 0:
            return int(value.shape[0])
    return 0


def frame_count_from_keypoints(keypoints: Dict[str, np.ndarray]) -> int:
    for value in keypoints.values():
        if value is not None and value.ndim > 0:
            return int(value.shape[0])
    return 0


def resample_numeric(value: Optional[np.ndarray], fps: float, target_fps: float) -> Optional[np.ndarray]:
    if value is None:
        return None
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 0 or len(arr) <= 1 or abs(fps - target_fps) < 1e-8:
        return arr
    duration = (len(arr) - 1) / max(fps, 1e-9)
    n = max(2, int(round(duration * target_fps)) + 1)
    old_t = np.linspace(0.0, duration, len(arr))
    new_t = np.linspace(0.0, duration, n)
    flat = arr.reshape(len(arr), -1)
    out = np.empty((n, flat.shape[1]), dtype=float)
    for i in range(flat.shape[1]):
        out[:, i] = np.interp(new_t, old_t, flat[:, i])
    return out.reshape((n,) + arr.shape[1:])


def resample_bool(value: Optional[np.ndarray], fps: float, target_fps: float) -> Optional[np.ndarray]:
    arr = resample_numeric(value, fps, target_fps)
    return None if arr is None else arr >= 0.5


def infer_contact_from_foot(foot: np.ndarray, fps: float, floor: Optional[float], thresholds: Dict[str, Any]) -> np.ndarray:
    if foot is None or len(foot) == 0:
        return np.zeros(0, dtype=bool)
    z_floor = float(np.nanmin(foot[:, 2])) if floor is None else floor
    height = float(thresholds["foot_contact_height_m"])
    speed_thr = float(thresholds["foot_contact_speed_mps"])
    speed = np.r_[0.0, np.linalg.norm(np.diff(foot[:, :2], axis=0), axis=1) * fps]
    return (foot[:, 2] <= z_floor + height) & (speed <= speed_thr)


def speed_series(pos: np.ndarray, fps: float) -> np.ndarray:
    if pos is None or len(pos) < 2:
        return np.zeros(0)
    return np.linalg.norm(np.diff(pos, axis=0), axis=1) * fps


def trajectory_length(xy: Optional[np.ndarray]) -> float:
    if xy is None or len(xy) < 2:
        return 0.0
    return float(np.nansum(np.linalg.norm(np.diff(xy, axis=0), axis=1)))


def path_heading_change(xy: np.ndarray) -> float:
    if xy is None or len(xy) < 3:
        return NAN
    diffs = np.diff(xy, axis=0)
    speed = np.linalg.norm(diffs, axis=1)
    mask = speed > 1e-6
    if np.sum(mask) < 2:
        return NAN
    heading = np.unwrap(np.arctan2(diffs[mask, 1], diffs[mask, 0]))
    return float(heading[-1] - heading[0])


def wrap_pi(value: float) -> float:
    return (value + math.pi) % (2 * math.pi) - math.pi


def quat_to_roll_pitch(q: np.ndarray) -> Tuple[float, float]:
    q = np.asarray(q, dtype=float)
    if q.shape[0] != 4 or not np.isfinite(q).all():
        return (NAN, NAN)
    q = q / max(np.linalg.norm(q), 1e-12)
    w, x, y, z = q
    roll = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    s = 2 * (w * y - z * x)
    s = max(-1.0, min(1.0, s))
    pitch = math.asin(s)
    return (math.degrees(roll), math.degrees(pitch))


def finite_gt(value: Any, threshold: float) -> bool:
    try:
        x = float(value)
    except Exception:
        return False
    return math.isfinite(x) and x > threshold


def is_finite_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except Exception:
        return False


def safe_mean(value: Iterable[Any]) -> float:
    arr = np.asarray(list(value) if not isinstance(value, np.ndarray) else value, dtype=float)
    return float(np.nanmean(arr)) if arr.size and np.isfinite(arr).any() else NAN


def safe_median(value: Iterable[Any]) -> float:
    arr = np.asarray(list(value) if not isinstance(value, np.ndarray) else value, dtype=float)
    return float(np.nanmedian(arr)) if arr.size and np.isfinite(arr).any() else NAN


def safe_std(value: Iterable[Any]) -> float:
    arr = np.asarray(list(value) if not isinstance(value, np.ndarray) else value, dtype=float)
    return float(np.nanstd(arr)) if arr.size and np.isfinite(arr).any() else NAN


def safe_min(value: Iterable[Any]) -> float:
    arr = np.asarray(list(value) if not isinstance(value, np.ndarray) else value, dtype=float)
    return float(np.nanmin(arr)) if arr.size and np.isfinite(arr).any() else NAN


def safe_max(value: Iterable[Any]) -> float:
    arr = np.asarray(list(value) if not isinstance(value, np.ndarray) else value, dtype=float)
    return float(np.nanmax(arr)) if arr.size and np.isfinite(arr).any() else NAN


def format_num(value: Any, digits: int = 3) -> str:
    if not is_finite_number(value):
        return "N/A"
    return f"{float(value):.{digits}f}"


def compact_number(value: float) -> str:
    value = float(value)
    if abs(value) >= 100:
        return f"{value:.0f}"
    if abs(value) >= 10:
        return f"{value:.1f}"
    if abs(value) >= 1:
        return f"{value:.2f}"
    return f"{value:.3f}"


def nice_ticks(max_value: float, count: int = 6) -> List[float]:
    if not math.isfinite(max_value) or max_value <= 0:
        return [0.0, 1.0]
    raw = max_value / max(count - 1, 1)
    mag = 10 ** math.floor(math.log10(raw))
    residual = raw / mag
    if residual <= 1:
        step = mag
    elif residual <= 2:
        step = 2 * mag
    elif residual <= 5:
        step = 5 * mag
    else:
        step = 10 * mag
    top = math.ceil(max_value / step) * step
    ticks = []
    cur = 0.0
    while cur <= top + step * 0.5:
        ticks.append(cur)
        cur += step
    return ticks


def load_font(size: int, bold: bool = False) -> Any:
    if ImageFont is None:
        return None
    paths = [
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\calibrib.ttf" if bold else r"C:\Windows\Fonts\calibri.ttf",
    ]
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


if __name__ == "__main__":
    main()
