from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - fallback is for minimal environments.
    yaml = None

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kinematics.alignment import prepare_pair
from kinematics.mujoco_fk import enrich_with_mujoco_fk
from loaders.load_bvh import load_bvh
from loaders.load_npy import load_npy
from loaders.load_npz import load_npz
from loaders.load_pkl import load_pkl
from metrics.contact_quality import compute_contact_quality
from metrics.kinematic_feasibility import compute_kinematic_feasibility
from metrics.physical_feasibility import compute_physical_feasibility
from metrics.scoring import add_scores
from metrics.similarity import compute_motion_similarity
from metrics.smoothness import compute_smoothness
from metrics.stability import compute_stability
from reports.generate_report import generate_report


ORIGINAL_EXTS = {".bvh", ".npz", ".npy"}


def main() -> None:
    """Command-line entry point."""
    args = build_parser().parse_args()
    config = load_config(args.config)
    apply_cli_overrides(config, args)
    out_dir = Path(config.get("output_dir", ROOT / "outputs")).expanduser()
    dirs = create_output_dirs(out_dir)

    originals = discover_files(config["original_motion_root"], ORIGINAL_EXTS)
    method_files = {
        method: discover_files(info.get("pkl_root", ""), {".pkl", ".pickle"})
        for method, info in config.get("methods", {}).items()
    }
    matches, missing_rows = match_all(originals, method_files)

    summary_rows: List[Dict[str, Any]] = []
    frame_rows: List[Dict[str, Any]] = []
    unavailable_all: Dict[str, Dict[str, str]] = {}

    for original_path in originals:
        method_matches = matches.get(original_path, {})
        if not any(path is not None for path in method_matches.values()):
            continue
        reference = load_original(original_path, config)
        motion_name = normalized_motion_id(original_path)
        for method, method_path in method_matches.items():
            if method_path is None:
                continue
            try:
                prediction = load_pkl(method_path, config, method=method)
                robot_xml = config.get("robot", {}).get("mujoco_xml")
                prediction = enrich_with_mujoco_fk(prediction, robot_xml, config)

                raw_ref, raw_pred, _ = prepare_pair(reference, prediction, config, mode="raw")
                aligned_ref, aligned_pred, _ = prepare_pair(reference, prediction, config, mode="aligned")
                ref, pred, alignment_notes = prepare_pair(reference, prediction, config, mode="full")

                raw_sim, _, raw_unavailable = compute_motion_similarity(raw_ref, raw_pred, config)
                aligned_sim, _, aligned_unavailable = compute_motion_similarity(aligned_ref, aligned_pred, config)
                sim, sim_pf, sim_unavailable = compute_motion_similarity(ref, pred, config)
                kin, kin_pf, kin_unavailable = compute_kinematic_feasibility(pred, config)
                phys, phys_pf, phys_unavailable = compute_physical_feasibility(pred, config, kin)
                contact, contact_pf, contact_unavailable = compute_contact_quality(ref, pred, config)
                stability, stability_pf, stability_unavailable = compute_stability(ref, pred, config, contact)
                smooth, smooth_pf, smooth_unavailable = compute_smoothness(pred, config)

                summary: Dict[str, Any] = {
                    "motion": original_path.stem,
                    "motion_id": motion_name,
                    "method": method,
                    "original_file": str(original_path),
                    "pkl_file": str(method_path),
                    "raw_error": raw_sim.get("mpjpe_mean", np.nan),
                    "aligned_error": aligned_sim.get("mpjpe_mean", np.nan),
                    "scale_normalized_error": sim.get("mpjpe_mean", np.nan),
                    "alignment_notes": "; ".join(alignment_notes),
                }
                for block in [sim, kin, phys, contact, stability, smooth]:
                    summary.update(block)
                add_scores(summary, config)
                summary_rows.append(summary)

                unavailable = {}
                for block in [raw_unavailable, aligned_unavailable, sim_unavailable, kin_unavailable, phys_unavailable, contact_unavailable, stability_unavailable, smooth_unavailable]:
                    unavailable.update(block)
                unavailable_all[f"{original_path.stem}/{method}"] = unavailable

                n = pred.num_frames
                merged_pf = {}
                for block in [sim_pf, kin_pf, phys_pf, contact_pf, stability_pf, smooth_pf]:
                    merged_pf.update(block)
                for frame in range(n):
                    row = {
                        "motion": original_path.stem,
                        "method": method,
                        "frame": frame,
                        "time": frame / max(pred.fps, 1e-9),
                    }
                    for key, value in merged_pf.items():
                        arr = np.asarray(value)
                        row[key] = arr[frame].item() if frame < len(arr) and np.asarray(arr[frame]).shape == () else (float(np.nan) if frame >= len(arr) else arr[frame])
                    frame_rows.append(row)
            except Exception as exc:
                missing_rows.append({
                    "motion": original_path.stem,
                    "method": method,
                    "missing_type": "load_or_eval_failed",
                    "detail": f"{method_path}: {exc}",
                })

    per_motion_df = pd.DataFrame(summary_rows)
    frame_df = pd.DataFrame(frame_rows)
    missing_df = pd.DataFrame(missing_rows)
    per_method_df = aggregate_by_method(per_motion_df)
    aggregate_df = aggregate_global(per_motion_df, missing_df)

    per_motion_df.to_csv(dirs["csv"] / "quality_per_motion.csv", index=False)
    per_method_df.to_csv(dirs["csv"] / "quality_per_method.csv", index=False)
    aggregate_df.to_csv(dirs["csv"] / "quality_aggregate.csv", index=False)
    frame_df.to_csv(dirs["csv"] / "frame_metrics_all.csv", index=False)
    missing_df.to_csv(dirs["csv"] / "missing_files.csv", index=False)
    write_json(dirs["json"] / "quality_raw_summary.json", {"per_motion": summary_rows, "unavailable": unavailable_all, "missing": missing_rows})
    write_json(dirs["json"] / "config_used.json", config)

    figures = generate_figures(per_motion_df, frame_df, dirs["figures"])
    generate_report(
        dirs["report"] / "RETARGETING_QUALITY_REPORT.md",
        dirs["report"] / "RETARGETING_QUALITY_REPORT.html",
        config=config,
        matched_count=len(summary_rows),
        missing_df=missing_df,
        per_motion_df=per_motion_df,
        per_method_df=per_method_df,
        unavailable=unavailable_all,
        figures=figures,
    )

    best = best_method(per_method_df)
    print("Evaluation finished.")
    print(f"Matched motions: {len(summary_rows)}")
    print(f"Missing files: {len(missing_rows)}")
    print(f"Best method by overall score: {best or 'not_available'}")
    print(f"Report saved to: {dirs['report'] / 'RETARGETING_QUALITY_REPORT.md'}")


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""
    parser = argparse.ArgumentParser(description="Evaluate Direct Mapping, Basic IK, and GMR retargeting PKL results against original motions.")
    parser.add_argument("--config", default=str(ROOT / "configs" / "eval_config.yaml"))
    parser.add_argument("--original_root", default=None)
    parser.add_argument("--direct_pkl_root", default=None)
    parser.add_argument("--ik_pkl_root", default=None)
    parser.add_argument("--gmr_pkl_root", default=None)
    parser.add_argument("--robot_xml", default=None)
    parser.add_argument("--smplx_body_model_path", default=None)
    parser.add_argument("--output_dir", default=None)
    return parser


def load_config(path: str | Path) -> Dict[str, Any]:
    """Load YAML config."""
    text = Path(path).read_text(encoding="utf-8")
    if yaml is not None:
        config = yaml.safe_load(text) or {}
    else:
        config = simple_yaml_load(text)
    config.setdefault("methods", {})
    config.setdefault("evaluation", {})
    config.setdefault("robot", {})
    config.setdefault("output_dir", str(ROOT / "outputs"))
    return config


def apply_cli_overrides(config: Dict[str, Any], args: argparse.Namespace) -> None:
    """Apply command-line path overrides to config."""
    if args.original_root:
        config["original_motion_root"] = args.original_root
    config.setdefault("methods", {})
    if args.direct_pkl_root:
        config["methods"].setdefault("direct_mapping", {})["pkl_root"] = args.direct_pkl_root
    if args.ik_pkl_root:
        config["methods"].setdefault("basic_ik", {})["pkl_root"] = args.ik_pkl_root
    if args.gmr_pkl_root:
        config["methods"].setdefault("gmr", {})["pkl_root"] = args.gmr_pkl_root
    if args.robot_xml:
        config.setdefault("robot", {})["mujoco_xml"] = args.robot_xml
    if args.smplx_body_model_path:
        config["smplx_body_model_path"] = args.smplx_body_model_path
    if args.output_dir:
        config["output_dir"] = args.output_dir


def create_output_dirs(out_dir: Path) -> Dict[str, Path]:
    """Create required output directories."""
    dirs = {
        "root": out_dir,
        "csv": out_dir / "csv",
        "json": out_dir / "json",
        "figures": out_dir / "figures",
        "report": out_dir / "report",
        "curves": out_dir / "figures" / "per_frame_curves",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def discover_files(root: str | Path, suffixes: set[str]) -> List[Path]:
    """Recursively discover files under a root directory."""
    if not root:
        return []
    root = Path(root).expanduser()
    if not root.exists():
        return []
    if root.is_file() and root.suffix.lower() in suffixes:
        return [root]
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes)


def load_original(path: Path, config: Dict[str, Any]) -> Any:
    """Load an original motion by suffix."""
    suffix = path.suffix.lower()
    if suffix == ".npz":
        return load_npz(path, config, method="reference")
    if suffix == ".npy":
        return load_npy(path, config, method="reference")
    if suffix == ".bvh":
        return load_bvh(path, config, method="reference")
    raise ValueError(f"Unsupported original extension: {path}")


def match_all(originals: List[Path], method_files: Dict[str, List[Path]]) -> Tuple[Dict[Path, Dict[str, Optional[Path]]], List[Dict[str, str]]]:
    """Match originals to every method's PKL files."""
    matches: Dict[Path, Dict[str, Optional[Path]]] = {}
    missing: List[Dict[str, str]] = []
    if not originals:
        missing.append({"motion": "", "method": "original", "missing_type": "missing_original", "detail": "No original .bvh/.npz/.npy files found."})
    for original in originals:
        matches[original] = {}
        for method, files in method_files.items():
            best = find_best_match(original, files)
            matches[original][method] = best
            if best is None:
                missing.append({"motion": original.stem, "method": method, "missing_type": f"missing_{method}", "detail": f"No PKL matched {original.name}"})
    return matches, missing


def normalized_motion_id(path: str | Path) -> str:
    """Normalize file names for robust matching."""
    stem = Path(path).stem.lower()
    stem = re.sub(r"[^a-z0-9]+", "_", stem)
    remove = [
        "poses", "pose", "retargeted", "unitree", "g1", "robot", "pkl", "clean",
        "gmr", "basic", "ik", "direct", "mapping", "no", "seed", "retargeting",
        "walk_easy", "slow_walk", "run", "multi_direction", "soccer_kick",
        "sit_stand", "forward_jump", "large_stride",
    ]
    tokens = [token for token in stem.split("_") if token and token not in remove]
    return "_".join(tokens)


def find_best_match(original: Path, candidates: List[Path]) -> Optional[Path]:
    """Find the best fuzzy filename match."""
    if not candidates:
        return None
    target = normalized_motion_id(original)
    scored = []
    target_tokens = set(target.split("_"))
    for candidate in candidates:
        cid = normalized_motion_id(candidate)
        if cid == target:
            return candidate
        score = 0.0
        if cid.startswith(target) or target.startswith(cid):
            score += 3.0
        overlap = len(target_tokens & set(cid.split("_")))
        score += overlap / max(len(target_tokens), 1)
        if target and target in cid:
            score += 1.0
        scored.append((score, candidate))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1] if scored and scored[0][0] >= 1.0 else None


def aggregate_by_method(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate numeric metrics by method."""
    if df.empty:
        return pd.DataFrame()
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    grouped = df.groupby("method", as_index=False)[numeric_cols].mean(numeric_only=True)
    return grouped


def aggregate_global(per_motion_df: pd.DataFrame, missing_df: pd.DataFrame) -> pd.DataFrame:
    """Create one-row global aggregate summary."""
    best = best_method(aggregate_by_method(per_motion_df))
    return pd.DataFrame([{
        "matched_motion_method_pairs": int(len(per_motion_df)),
        "missing_records": int(len(missing_df)),
        "best_method_by_overall_score": best or "not_available",
    }])


def generate_figures(per_motion_df: pd.DataFrame, frame_df: pd.DataFrame, fig_dir: Path) -> List[str]:
    """Generate all requested figures."""
    try:
        from visualization.plot_bar import plot_bar
        from visualization.plot_curve import plot_single_motion_curves
        from visualization.plot_heatmap import plot_heatmap
        from visualization.plot_radar import plot_radar
    except Exception as exc:
        print(f"[plot warning] plotting dependencies unavailable: {exc}")
        return []

    generated: List[str] = []
    tasks = [
        ("overall_score_bar.png", lambda p: plot_bar(per_motion_df, "overall_score", p, title="Overall Score", ylabel="score")),
        ("similarity_mpjpe_bar.png", lambda p: plot_bar(per_motion_df, "mpjpe_mean", p, title="MPJPE Mean", ylabel="m")),
        ("foot_penetration_bar.png", lambda p: plot_bar(per_motion_df, "foot_penetration_mean", p, title="Foot Penetration Mean", ylabel="m")),
        ("foot_sliding_bar.png", lambda p: plot_bar(per_motion_df, "foot_sliding_total", p, title="Foot Sliding Total", ylabel="m")),
        ("joint_limit_violation_bar.png", lambda p: plot_bar(per_motion_df, "joint_limit_violation_rate", p, title="Joint Limit Violation Rate", ylabel="rate")),
        ("smoothness_jerk_bar.png", lambda p: plot_bar(per_motion_df, "joint_jerk_mean", p, title="Joint Jerk Mean", ylabel="jerk")),
        ("stability_root_height_bar.png", lambda p: plot_bar(per_motion_df, "root_height_error_against_reference", p, title="Root Height Error", ylabel="m")),
        ("method_radar_chart.png", lambda p: plot_radar(per_motion_df, p)),
        ("per_motion_heatmap.png", lambda p: plot_heatmap(per_motion_df, p, "overall_score")),
    ]
    for filename, func in tasks:
        path = fig_dir / filename
        try:
            if func(path):
                generated.append(str(path))
        except Exception as exc:
            print(f"[plot warning] {filename}: {exc}")
    try:
        generated.extend(plot_single_motion_curves(frame_df, fig_dir / "per_frame_curves"))
    except Exception as exc:
        print(f"[plot warning] per-frame curves: {exc}")
    return generated


def best_method(df: pd.DataFrame) -> Optional[str]:
    """Return best method by overall score."""
    if df.empty or "overall_score" not in df.columns:
        return None
    values = pd.to_numeric(df["overall_score"], errors="coerce")
    if values.notna().sum() == 0:
        return None
    return str(df.loc[values.idxmax(), "method"])


def write_json(path: Path, value: Any) -> None:
    """Write JSON with numpy values converted to Python scalars."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonify(value), ensure_ascii=False, indent=2, allow_nan=True), encoding="utf-8")


def _jsonify(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonify(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonify(v) for v in value]
    if isinstance(value, tuple):
        return [_jsonify(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def simple_yaml_load(text: str) -> Dict[str, Any]:
    """Parse the small YAML subset used by the default config when PyYAML is absent."""
    raw_lines = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        line = raw.rstrip()
        raw_lines.append(line)

    def indent_of(line: str) -> int:
        return len(line) - len(line.lstrip(" "))

    def parse_value(value: str) -> Any:
        value = value.strip()
        if value in {"", "null", "None", "~"}:
            return None
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if not inner:
                return []
            return [parse_value(part.strip()) for part in inner.split(",")]
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            return value[1:-1]
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            return value

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        is_list = index < len(raw_lines) and raw_lines[index].lstrip().startswith("- ") and indent_of(raw_lines[index]) == indent
        if is_list:
            result: list[Any] = []
            while index < len(raw_lines) and indent_of(raw_lines[index]) == indent and raw_lines[index].lstrip().startswith("- "):
                item = raw_lines[index].lstrip()[2:].strip()
                result.append(parse_value(item))
                index += 1
            return result, index
        result: Dict[str, Any] = {}
        while index < len(raw_lines):
            line = raw_lines[index]
            current = indent_of(line)
            if current < indent:
                break
            if current > indent:
                index += 1
                continue
            stripped = line.strip()
            if ":" not in stripped:
                index += 1
                continue
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            index += 1
            if value:
                result[key] = parse_value(value)
            else:
                if index < len(raw_lines) and indent_of(raw_lines[index]) > current:
                    result[key], index = parse_block(index, indent_of(raw_lines[index]))
                else:
                    result[key] = {}
        return result, index

    parsed, _ = parse_block(0, 0)
    return parsed if isinstance(parsed, dict) else {}


if __name__ == "__main__":
    main()
