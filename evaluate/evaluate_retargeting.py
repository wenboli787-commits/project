"""CLI entry point for comparing Direct Mapping, Basic IK and GMR outputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from loaders import load_canonical_motion
from metrics import evaluate_all_metrics
from plotting import save_plots
from report import write_markdown_report
from simulator_adapters import OfflineAdapter, create_adapter
from utils import align_time, flatten_summary, load_yaml, normalize_reference, write_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simulator-agnostic evaluation of Direct Mapping, Basic IK and GMR trajectories.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--simulator", required=True, choices=("mujoco", "isaac", "offline"))
    parser.add_argument("--robot_model", type=Path, default=None, help="MJCF/XML for MuJoCo, USD metadata path for Isaac, optional for offline.")
    parser.add_argument("--ref_motion", type=Path, required=True, help="Human/reference motion (.npz/.npy/.pkl/.csv/.bvh).")
    parser.add_argument("--direct_motion", type=Path, required=True, help="Direct Mapping result.")
    parser.add_argument("--ik_motion", type=Path, required=True, help="Basic IK result.")
    parser.add_argument("--gmr_motion", type=Path, required=True, help="GMR / constrained IK result.")
    parser.add_argument("--mapping", type=Path, required=True, help="Body/joint correspondence YAML.")
    parser.add_argument("--out_dir", type=Path, required=True)
    parser.add_argument("--resample", action="store_true", help="Resample candidates to reference FPS before clipping frames.")
    parser.add_argument("--no_plots", action="store_true", help="Do not save PNG plots.")
    return parser


def _validate_path(path: Path, label: str) -> Path:
    path = path.expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"{label} was not found: {path}")
    return path.resolve()


def run(args: argparse.Namespace) -> Path:
    mapping_path = _validate_path(args.mapping, "Mapping YAML")
    config = load_yaml(mapping_path)
    config.setdefault("simulator", {})["type"] = args.simulator
    config.setdefault("robot", {})["model_path"] = str(args.robot_model) if args.robot_model else config.get("robot", {}).get("model_path")
    reference_path = _validate_path(args.ref_motion, "Reference motion")
    candidates_paths = {"Direct Mapping": _validate_path(args.direct_motion, "Direct Mapping motion"), "Basic IK": _validate_path(args.ik_motion, "Basic IK motion"), "GMR / Constrained IK": _validate_path(args.gmr_motion, "GMR motion")}
    output = args.out_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    # A reference can be BVH/AMASS-converted/offline independent of the robot simulator.
    reference_adapter = OfflineAdapter()
    reference = reference_adapter.load_motion(reference_path, config)
    adapter = create_adapter(args.simulator, args.robot_model)
    raw_candidates = {method: adapter.load_motion(path, config) for method, path in candidates_paths.items()}
    summaries: dict[str, dict[str, Any]] = {}
    all_per_frame: list[pd.DataFrame] = []
    candidate_motions = {}
    aligned_references = {}
    alignment_notes: dict[str, dict[str, Any]] = {}
    use_resample = bool(args.resample or config.get("temporal", {}).get("resample_to_reference_fps", False))
    for method, motion in raw_candidates.items():
        paired_reference, paired_candidate, timing = align_time(reference, motion, resample=use_resample)
        normalized_reference, normalization = normalize_reference(paired_reference, paired_candidate, config)
        summary, frames = evaluate_all_metrics(normalized_reference, paired_candidate, config)
        summaries[method] = summary
        alignment_notes[method] = {**timing, "normalization": normalization}
        candidate_motions[method] = paired_candidate
        aligned_references[method] = normalized_reference
        frame_table = pd.DataFrame({"frame": range(paired_candidate.num_frames), "time_s": [index / paired_candidate.fps for index in range(paired_candidate.num_frames)], "method": method})
        for key, values in frames.items():
            if len(values) == len(frame_table):
                frame_table[key] = values
        all_per_frame.append(frame_table)

    warnings = reference_adapter.warnings + adapter.warnings
    run_metadata = {"simulator": args.simulator, "robot_model": str(args.robot_model.resolve()) if args.robot_model else None, "reference_path": str(reference_path), "mapping_path": str(mapping_path), "candidate_paths": {method: str(path) for method, path in candidates_paths.items()}, "resample": use_resample}
    complete = {"run": run_metadata, "alignment": alignment_notes, "warnings": warnings, "methods": summaries}
    write_json(output / "summary_metrics.json", complete)
    pd.DataFrame([{"method": method, **flatten_summary(summary)} for method, summary in summaries.items()]).to_csv(output / "summary_metrics.csv", index=False, encoding="utf-8-sig")
    pd.concat(all_per_frame, ignore_index=True).to_csv(output / "per_frame_metrics.csv", index=False, encoding="utf-8-sig")
    plot_files = [] if args.no_plots else save_plots(output / "plots", aligned_references, candidate_motions, summaries, {method: {column: table[column].to_numpy() for column in table.columns if column not in {"frame", "time_s", "method"}} for method, table in ((item["method"].iloc[0], item) for item in all_per_frame)})
    write_markdown_report(output / "evaluation_report.md", run_metadata, summaries, alignment_notes, warnings, plot_files)
    (output / "warnings.txt").write_text("\n".join(warnings) + ("\n" if warnings else ""), encoding="utf-8")
    print(f"Evaluation complete: {output}")
    for method, summary in summaries.items():
        print(f"  {method}: EE mean = {summary.get('end_effector_position_error', {}).get('aggregate_mean', 'unavailable')}")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        run(parser.parse_args(argv))
    except (FileNotFoundError, ValueError, ImportError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
