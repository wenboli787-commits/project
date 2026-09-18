#!/usr/bin/env python3
"""
Export exact W&B histories for the tracking reward ablation study and create
two publication-ready CSV tables. No values are estimated from screenshots.

Run inside the user's MJLab environment, where wandb is installed and logged in.

Example:
    cd /mnt/d/GMR_WORK/mjlab
    uv run python /mnt/d/GMR_WORK/GMR/outputs/final_results/export_wandb_ablation_exact.py

Output:
    all_history_exact.csv
    final100_summary_exact.csv
    table1_tracking_accuracy_exact.csv
    table2_physical_quality_exact.csv
    termination_summary_exact.csv
"""

from __future__ import annotations

from functools import reduce
from pathlib import Path
import math
import sys

import pandas as pd
import wandb


# ---------------------------------------------------------------------------
# EDIT THESE SETTINGS
# ---------------------------------------------------------------------------

ENTITY = "wenboli787-university-of-glasgow"
PROJECT = "mjlab"

# Preferred: paste the run ID from the end of each W&B run URL.
# Example URL: https://wandb.ai/<entity>/<project>/runs/abc123xy
# Then use "abc123xy".
RUN_IDS: dict[str, str] = {
    "Full": "",
    "No global root": "",
    "No body pose": "",
    "No velocity": "",
    "No action rate": "",
    "No joint limit": "",
    "No self collision": "",
}

# Fallback when RUN_IDS are blank: match the W&B display name.
# Change "05_04" to the exact motion used in this ablation if necessary.
RUN_NAME_SUBSTRINGS: dict[str, str] = {
    "Full": "2026-07-05_11-16-21",
    "No global root": "05_04_gmr_no_global_root_seed_42_iter_1000",
    "No body pose": "05_04_gmr_no_body_pose_seed_42_iter_1000",
    "No velocity": "05_04_gmr_no_velocity_seed_42_iter_1000",
    "No action rate": "05_04_gmr_no_action_rate_seed_42_iter_1000",
    "No joint limit": "05_04_gmr_no_joint_limit_seed_42_iter_1000",
    "No self collision": "05_04_gmr_no_self_collision_seed_42_iter_1000",
}

OUTPUT_DIR = Path(
    "/mnt/d/GMR_WORK/GMR/outputs/final results/tracking_ablation_exact"
)

FINAL_WINDOW = 100

# From episode_length_s / (timestep * decimation).
# Use 500 only if your environment has 10 s episodes, timestep=0.005,
# and decimation=4. Otherwise replace this value.
MAX_EPISODE_LENGTH = 500.0

METRICS = [
    "Train/mean_reward",
    "Train/mean_episode_length",
    "Policy/mean_std",

    "Episode_Metrics/root_position_error",
    "Episode_Metrics/root_orientation_error",
    "Episode_Metrics/body_position_error",
    "Episode_Metrics/body_orientation_error",
    "Episode_Metrics/body_linear_velocity_error",
    "Episode_Metrics/body_angular_velocity_error",
    "Episode_Metrics/action_rate_l2_raw",
    "Episode_Metrics/joint_limit_raw",
    "Episode_Metrics/self_collision_raw",

    "Episode_Termination/time_out",
    "Episode_Termination/anchor_pos",
    "Episode_Termination/anchor_ori",
    "Episode_Termination/ee_body_pos",
]

TRACKING_COLUMNS = {
    "Root position error": "Episode_Metrics/root_position_error",
    "Root orientation error": "Episode_Metrics/root_orientation_error",
    "Body position error": "Episode_Metrics/body_position_error",
    "Body orientation error": "Episode_Metrics/body_orientation_error",
    "Linear velocity error": "Episode_Metrics/body_linear_velocity_error",
    "Angular velocity error": "Episode_Metrics/body_angular_velocity_error",
}

PHYSICAL_COLUMNS = {
    "Action rate raw": "Episode_Metrics/action_rate_l2_raw",
    "Joint-limit raw": "Episode_Metrics/joint_limit_raw",
    "Self-collision raw": "Episode_Metrics/self_collision_raw",
    "Policy mean std": "Policy/mean_std",
}

TERMINATION_COLUMNS = [
    "Episode_Termination/time_out",
    "Episode_Termination/anchor_pos",
    "Episode_Termination/anchor_ori",
    "Episode_Termination/ee_body_pos",
]


# ---------------------------------------------------------------------------
# IMPLEMENTATION
# ---------------------------------------------------------------------------

def resolve_runs(api: wandb.Api) -> dict[str, wandb.apis.public.Run]:
    resolved: dict[str, wandb.apis.public.Run] = {}
    all_runs = None

    for label in RUN_IDS:
        run_id = RUN_IDS[label].strip()
        if run_id:
            resolved[label] = api.run(f"{ENTITY}/{PROJECT}/{run_id}")
            continue

        if all_runs is None:
            print(f"Scanning W&B runs in {ENTITY}/{PROJECT} ...")
            all_runs = list(api.runs(f"{ENTITY}/{PROJECT}"))

        needle = RUN_NAME_SUBSTRINGS[label]
        matches = [
            run for run in all_runs
            if needle in (run.name or "")
        ]

        if not matches:
            raise RuntimeError(
                f"No W&B run matched {label!r} using substring {needle!r}. "
                "Paste the exact run ID into RUN_IDS."
            )

        if len(matches) > 1:
            matches.sort(
                key=lambda run: str(getattr(run, "created_at", "")),
                reverse=True,
            )
            print(
                f"Warning: {len(matches)} runs matched {label!r}; "
                f"using newest: {matches[0].name} ({matches[0].id})"
            )

        resolved[label] = matches[0]

    return resolved


def export_metric(run, metric: str) -> pd.DataFrame:
    """Fetch all non-null values for one metric without history sampling."""
    rows = list(
        run.scan_history(
            keys=["_step", metric],
            page_size=200,
        )
    )
    if not rows:
        return pd.DataFrame(columns=["_step", metric])

    df = pd.DataFrame(rows)
    if "_step" not in df.columns or metric not in df.columns:
        return pd.DataFrame(columns=["_step", metric])

    df = df[["_step", metric]].copy()
    df[metric] = pd.to_numeric(df[metric], errors="coerce")
    df = df.dropna(subset=[metric])
    df = df.drop_duplicates(subset=["_step"], keep="last")
    return df


def export_run_history(label: str, run) -> pd.DataFrame:
    frames = []
    for metric in METRICS:
        metric_df = export_metric(run, metric)
        if not metric_df.empty:
            frames.append(metric_df)

    if not frames:
        raise RuntimeError(f"No history was exported for {label}: {run.url}")

    merged = reduce(
        lambda left, right: pd.merge(left, right, on="_step", how="outer"),
        frames,
    ).sort_values("_step").reset_index(drop=True)

    merged.insert(0, "Configuration", label)
    merged.insert(1, "Run ID", run.id)
    merged.insert(2, "Run name", run.name)

    safe_label = label.lower().replace(" ", "_").replace("-", "_")
    merged.to_csv(
        OUTPUT_DIR / f"{safe_label}_history_exact.csv",
        index=False,
    )
    return merged


def final_values(df: pd.DataFrame, metric: str) -> pd.Series:
    if metric not in df.columns:
        return pd.Series(dtype=float)
    return (
        pd.to_numeric(df[metric], errors="coerce")
        .dropna()
        .tail(FINAL_WINDOW)
    )


def make_summary(histories: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for label, df in histories.items():
        row: dict[str, object] = {"Configuration": label}
        for metric in METRICS:
            values = final_values(df, metric)
            row[f"{metric} | mean"] = (
                float(values.mean()) if not values.empty else math.nan
            )
            row[f"{metric} | temporal SD"] = (
                float(values.std(ddof=1)) if len(values) > 1 else math.nan
            )
            row[f"{metric} | N"] = int(len(values))
        rows.append(row)
    return pd.DataFrame(rows)


def mean_col(metric: str) -> str:
    return f"{metric} | mean"


def temporal_sd_col(metric: str) -> str:
    return f"{metric} | temporal SD"


def relative_change(value: float, baseline: float) -> float:
    if pd.isna(value) or pd.isna(baseline) or baseline == 0:
        return math.nan
    return (value - baseline) / abs(baseline) * 100.0


def make_tracking_table(summary: pd.DataFrame) -> pd.DataFrame:
    by_cfg = summary.set_index("Configuration")
    full = by_cfg.loc["Full"]
    rows = []

    for configuration, source in by_cfg.iterrows():
        row: dict[str, object] = {"Configuration": configuration}

        for table_name, metric in TRACKING_COLUMNS.items():
            value = source[mean_col(metric)]
            row[table_name] = value
            row[f"{table_name} temporal SD"] = source[temporal_sd_col(metric)]
            row[f"{table_name} change vs Full (%)"] = relative_change(
                value, full[mean_col(metric)]
            )

        episode_length = source[mean_col("Train/mean_episode_length")]
        row["Mean episode length"] = episode_length
        row["Episode length temporal SD"] = source[
            temporal_sd_col("Train/mean_episode_length")
        ]
        row["Normalized episode length"] = (
            episode_length / MAX_EPISODE_LENGTH
            if not pd.isna(episode_length)
            else math.nan
        )
        row["Episode length change vs Full (%)"] = relative_change(
            episode_length,
            full[mean_col("Train/mean_episode_length")],
        )
        rows.append(row)

    return pd.DataFrame(rows)


def make_physical_table(summary: pd.DataFrame) -> pd.DataFrame:
    by_cfg = summary.set_index("Configuration")
    full = by_cfg.loc["Full"]
    rows = []

    for configuration, source in by_cfg.iterrows():
        row: dict[str, object] = {"Configuration": configuration}
        for table_name, metric in PHYSICAL_COLUMNS.items():
            value = source[mean_col(metric)]
            row[table_name] = value
            row[f"{table_name} temporal SD"] = source[temporal_sd_col(metric)]
            row[f"{table_name} change vs Full (%)"] = relative_change(
                value, full[mean_col(metric)]
            )
        rows.append(row)

    return pd.DataFrame(rows)


def make_termination_table(histories: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for configuration, df in histories.items():
        sums: dict[str, float] = {}
        for metric in TERMINATION_COLUMNS:
            values = final_values(df, metric)
            sums[metric] = float(values.sum()) if not values.empty else math.nan

        valid = [v for v in sums.values() if not pd.isna(v)]
        total = sum(valid) if valid else math.nan
        timeout = sums["Episode_Termination/time_out"]

        row = {
            "Configuration": configuration,
            "Time-out count (final window)": timeout,
            "Anchor-pos count (final window)": sums[
                "Episode_Termination/anchor_pos"
            ],
            "Anchor-ori count (final window)": sums[
                "Episode_Termination/anchor_ori"
            ],
            "EE-body-pos count (final window)": sums[
                "Episode_Termination/ee_body_pos"
            ],
            # This is not a strict success rate if termination terms overlap.
            "Time-out event share (%)": (
                timeout / total * 100.0
                if not pd.isna(total) and total > 0
                else math.nan
            ),
        }
        rows.append(row)

    return pd.DataFrame(rows)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    api = wandb.Api()

    runs = resolve_runs(api)
    histories: dict[str, pd.DataFrame] = {}

    for label, run in runs.items():
        print(f"Exporting {label}: {run.name} ({run.id})")
        histories[label] = export_run_history(label, run)

    all_history = pd.concat(histories.values(), ignore_index=True, sort=False)
    all_history.to_csv(
        OUTPUT_DIR / "all_history_exact.csv",
        index=False,
    )

    summary = make_summary(histories)
    summary.to_csv(
        OUTPUT_DIR / "final100_summary_exact.csv",
        index=False,
    )

    tracking = make_tracking_table(summary)
    tracking.to_csv(
        OUTPUT_DIR / "table1_tracking_accuracy_exact.csv",
        index=False,
    )

    physical = make_physical_table(summary)
    physical.to_csv(
        OUTPUT_DIR / "table2_physical_quality_exact.csv",
        index=False,
    )

    terminations = make_termination_table(histories)
    terminations.to_csv(
        OUTPUT_DIR / "termination_summary_exact.csv",
        index=False,
    )

    print("\nCreated exact output files:")
    for name in [
        "all_history_exact.csv",
        "final100_summary_exact.csv",
        "table1_tracking_accuracy_exact.csv",
        "table2_physical_quality_exact.csv",
        "termination_summary_exact.csv",
    ]:
        print("  ", OUTPUT_DIR / name)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise
