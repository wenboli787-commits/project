#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gmr_eval.config import apply_cli_overrides, load_config
from gmr_eval.io import write_csv, write_json
from gmr_eval.metrics import add_overall_scores, aggregate_summary, evaluate_motion_pair
from gmr_eval.motion_loaders import ORIGINAL_EXTENSIONS, ROBOT_EXTENSIONS, load_original_motion, load_robot_pkl
from gmr_eval.report import generate_report
from gmr_eval.robot_fk import enrich_robot_with_fk
from gmr_eval.visualization import generate_figures


def main() -> None:
    args = build_parser().parse_args()
    config = apply_cli_overrides(load_config(args.config), args)
    output_dir = Path(config["output_dir"]).expanduser()
    figures_dir = output_dir / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    original_files = discover_files(config.get("original_dir"), ORIGINAL_EXTENSIONS)
    method_files, missing_rows, run_warnings = discover_method_files(config)
    matches, match_missing = match_files(original_files, method_files, str(config.get("name_regex", "")))
    missing_rows.extend(match_missing)

    per_motion_rows: List[Dict[str, Any]] = []
    keypoint_rows: List[Dict[str, Any]] = []
    joint_jump_rows: List[Dict[str, Any]] = []
    collision_rows: List[Dict[str, Any]] = []
    unavailable_all: Dict[str, Dict[str, str]] = {}

    if not original_files:
        missing_rows.append(
            {
                "motion_name": "",
                "method": "original",
                "missing_type": "missing_original_dir_or_files",
                "detail": f"No original .npz/.npy/.bvh files found in {config.get('original_dir')}",
            }
        )

    for original_path in original_files:
        try:
            reference = load_original_motion(original_path, config)
        except Exception as exc:
            missing_rows.append(
                {
                    "motion_name": original_path.stem,
                    "method": "original",
                    "missing_type": "load_original_failed",
                    "detail": f"{original_path}: {exc}",
                }
            )
            continue

        for method, pkl_path in matches.get(original_path, {}).items():
            if pkl_path is None:
                continue
            try:
                prediction = load_robot_pkl(pkl_path, config, method=method)
                prediction = enrich_robot_with_fk(prediction, config.get("robot_xml"), config)
                metrics, kp_rows, jump_rows, col_rows, unavailable = evaluate_motion_pair(reference, prediction, config)
                per_motion_rows.append(metrics)
                keypoint_rows.extend(kp_rows)
                joint_jump_rows.extend(jump_rows)
                collision_rows.extend(col_rows)
                unavailable_all[f"{reference.name}/{method}"] = unavailable
            except Exception as exc:
                missing_rows.append(
                    {
                        "motion_name": original_path.stem,
                        "method": method,
                        "missing_type": "load_or_eval_failed",
                        "detail": f"{pkl_path}: {exc}",
                    }
                )

    add_overall_scores(per_motion_rows, config)
    summary_rows = aggregate_summary(per_motion_rows)
    user_study_rows = build_user_study_template(per_motion_rows, config)

    write_csv(output_dir / "summary_metrics.csv", summary_rows)
    write_csv(output_dir / "per_motion_metrics.csv", per_motion_rows)
    write_csv(output_dir / "per_keypoint_error.csv", keypoint_rows)
    write_csv(output_dir / "per_joint_jump_stats.csv", joint_jump_rows)
    write_csv(output_dir / "self_collision_pairs.csv", collision_rows)
    write_csv(output_dir / "missing_files.csv", missing_rows, ["motion_name", "method", "missing_type", "detail"])
    write_csv(
        output_dir / "user_study_template.csv",
        user_study_rows,
        [
            "motion_name",
            "method",
            "video_path",
            "original_motion_path",
            "similarity_score_1_to_5",
            "naturalness_score_1_to_5",
            "foot_sliding_score_1_to_5",
            "comments",
        ],
    )

    figure_paths, figure_warnings = generate_figures(per_motion_rows, summary_rows, keypoint_rows, figures_dir)
    run_warnings.extend(figure_warnings)
    write_json(
        output_dir / "quality_raw_summary.json",
        {
            "config": config,
            "summary_metrics": summary_rows,
            "per_motion_metrics": per_motion_rows,
            "per_keypoint_error": keypoint_rows,
            "per_joint_jump_stats": joint_jump_rows,
            "self_collision_pairs": collision_rows,
            "missing_files": missing_rows,
            "unavailable": unavailable_all,
            "warnings": run_warnings,
        },
    )
    generate_report(output_dir, config, per_motion_rows, summary_rows, missing_rows, unavailable_all, figure_paths, run_warnings)

    best = best_method(summary_rows)
    print("Evaluation finished.")
    print(f"Output directory: {output_dir}")
    print(f"Evaluated motion-method pairs: {len(per_motion_rows)}")
    print(f"Missing/failed records: {len(missing_rows)}")
    print(f"Best method by average overall_score: {best or 'unavailable'}")
    print(f"Report: {output_dir / 'report.md'}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate human-to-Unitree-G1 retargeting quality for Direct Mapping, Basic IK, and GMR PKL results."
    )
    parser.add_argument("--config", default=str(ROOT / "configs" / "eval_mapping_unitree_g1.yaml"), help="YAML evaluation config.")
    parser.add_argument("--original_dir", default=None, help="Directory containing original .npz/.npy/.bvh motions.")
    parser.add_argument("--direct_dir", default=None, help="Directory containing Direct Mapping .pkl files.")
    parser.add_argument("--ik_dir", default=None, help="Directory containing Basic IK .pkl files.")
    parser.add_argument("--gmr_dir", default=None, help="Directory containing GMR .pkl files.")
    parser.add_argument("--robot_xml", default=None, help="Unitree G1 MuJoCo XML path. If missing, FK-only metrics are skipped.")
    parser.add_argument("--output_dir", default=None, help="Output directory for CSV/JSON/report/figures.")
    parser.add_argument("--name_regex", default=None, help="Regex for motion id matching. First group is used when present.")
    parser.add_argument("--sync_mode", choices=["resample", "trim"], default=None, help="Time synchronization mode.")
    parser.add_argument("--target_fps", type=float, default=None, help="Target fps for synchronized comparison.")
    return parser


def discover_files(root: Any, suffixes: set[str]) -> List[Path]:
    if not root:
        return []
    path = Path(str(root)).expanduser()
    if not path.exists():
        return []
    if path.is_file() and path.suffix.lower() in suffixes:
        return [path]
    return sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in suffixes)


def discover_method_files(config: Dict[str, Any]) -> Tuple[Dict[str, List[Path]], List[Dict[str, Any]], List[str]]:
    method_files: Dict[str, List[Path]] = {}
    missing_rows: List[Dict[str, Any]] = []
    warnings: List[str] = []
    for method, info in config.get("methods", {}).items():
        method_dir = info.get("dir") if isinstance(info, dict) else info
        files = discover_files(method_dir, ROBOT_EXTENSIONS)
        if not files:
            fallback_files = []
            for fallback in info.get("fallback_dirs", []) if isinstance(info, dict) else []:
                fallback_files = discover_files(fallback, ROBOT_EXTENSIONS)
                if fallback_files:
                    warnings.append(f"{method}: using fallback dir {fallback}")
                    files = fallback_files
                    break
        if not files:
            missing_rows.append(
                {
                    "motion_name": "",
                    "method": method,
                    "missing_type": "missing_method_dir_or_pkls",
                    "detail": f"No .pkl files found in {method_dir}",
                }
            )
            continue
        method_files[method] = files
    return method_files, missing_rows, warnings


def match_files(originals: List[Path], method_files: Dict[str, List[Path]], name_regex: str) -> Tuple[Dict[Path, Dict[str, Optional[Path]]], List[Dict[str, Any]]]:
    matches: Dict[Path, Dict[str, Optional[Path]]] = {}
    missing: List[Dict[str, Any]] = []
    for original in originals:
        oid = motion_id(original, name_regex)
        matches[original] = {}
        for method, candidates in method_files.items():
            best = find_best_match(oid, candidates, name_regex)
            matches[original][method] = best
            if best is None:
                missing.append(
                    {
                        "motion_name": original.stem,
                        "method": method,
                        "missing_type": "missing_matched_pkl",
                        "detail": f"No PKL matched motion id '{oid}' for original {original.name}",
                    }
                )
    return matches, missing


def motion_id(path: Path, name_regex: str) -> str:
    stem = path.stem
    if name_regex:
        try:
            match = re.search(name_regex, stem)
            if match:
                return match.group(1) if match.groups() else match.group(0)
        except re.error:
            pass
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", stem).lower()
    drop = {
        "poses",
        "pose",
        "unitree",
        "g1",
        "gmr",
        "direct",
        "mapping",
        "raw",
        "basic",
        "ik",
        "no",
        "seed",
        "retargeting",
        "pkl",
    }
    tokens = [token for token in normalized.split("_") if token and token not in drop]
    return "_".join(tokens[:2]) if len(tokens) >= 2 and all(token.isdigit() for token in tokens[:2]) else "_".join(tokens)


def find_best_match(target_id: str, candidates: List[Path], name_regex: str) -> Optional[Path]:
    exact = [candidate for candidate in candidates if motion_id(candidate, name_regex) == target_id]
    if exact:
        return sorted(exact, key=lambda path: len(path.name))[0]
    scored: List[Tuple[float, Path]] = []
    target_tokens = set(target_id.split("_"))
    for candidate in candidates:
        cid = motion_id(candidate, name_regex)
        score = 0.0
        if cid.startswith(target_id) or target_id.startswith(cid):
            score += 3.0
        if target_id and target_id in candidate.stem:
            score += 2.0
        overlap = len(target_tokens & set(cid.split("_"))) / max(len(target_tokens), 1)
        score += overlap
        scored.append((score, candidate))
    scored.sort(key=lambda item: (item[0], -len(item[1].name)), reverse=True)
    return scored[0][1] if scored and scored[0][0] >= 1.0 else None


def build_user_study_template(per_motion_rows: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for row in per_motion_rows:
        rows.append(
            {
                "motion_name": row.get("motion_name", ""),
                "method": row.get("method", ""),
                "video_path": find_video_path(row.get("pkl_path", ""), config),
                "original_motion_path": row.get("original_motion_path", ""),
                "similarity_score_1_to_5": "",
                "naturalness_score_1_to_5": "",
                "foot_sliding_score_1_to_5": "",
                "comments": "",
            }
        )
    return rows


def find_video_path(pkl_path: Any, config: Dict[str, Any]) -> str:
    if not pkl_path:
        return ""
    pkl = Path(str(pkl_path))
    stem = pkl.stem
    search_dirs = [Path(path).expanduser() for path in config.get("video_dirs", [])]
    parent = pkl.parent
    search_dirs.extend(
        [
            parent,
            Path(str(parent).replace("pkl", "videos")),
            parent.parent / "videos",
            parent.parent / f"videos {parent.name.replace('pkl', '').strip()}",
        ]
    )
    for directory in search_dirs:
        if not directory.exists() or not directory.is_dir():
            continue
        for ext in [".mp4", ".mov", ".avi", ".mkv", ".gif"]:
            exact = directory / f"{stem}{ext}"
            if exact.exists():
                return str(exact)
        videos = sorted(p for p in directory.glob("*") if p.suffix.lower() in {".mp4", ".mov", ".avi", ".mkv", ".gif"} and stem.split("_unitree")[0] in p.stem)
        if videos:
            return str(videos[0])
    return ""


def best_method(summary_rows: List[Dict[str, Any]]) -> str:
    best = ""
    best_score = float("-inf")
    for row in summary_rows:
        try:
            score = float(row.get("mean_overall_score"))
        except Exception:
            continue
        if score > best_score:
            best = str(row.get("method", ""))
            best_score = score
    return best


if __name__ == "__main__":
    main()
