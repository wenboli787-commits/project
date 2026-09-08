from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


def generate_report(
    out_md: str | Path,
    out_html: str | Path,
    *,
    config: Dict[str, Any],
    matched_count: int,
    missing_df: pd.DataFrame,
    per_motion_df: pd.DataFrame,
    per_method_df: pd.DataFrame,
    unavailable: Dict[str, Dict[str, str]],
    figures: List[str],
) -> None:
    """Generate Markdown and simple HTML reports."""
    lines: List[str] = []
    lines.append("# Retargeting Quality Report")
    lines.append("")
    lines.append("## 1. 实验输入路径")
    lines.append("")
    lines.append(f"- 原始动作目录: `{config.get('original_motion_root')}`")
    for method, info in config.get("methods", {}).items():
        lines.append(f"- {method}: `{info.get('pkl_root')}`")
    lines.append(f"- MuJoCo XML: `{config.get('robot', {}).get('mujoco_xml')}`")
    lines.append("")
    lines.append("## 2. 匹配结果")
    lines.append("")
    lines.append(f"- 成功匹配动作-方法组合: **{matched_count}**")
    lines.append(f"- 缺失文件记录: **{len(missing_df)}**")
    if not missing_df.empty:
        lines.extend(_table(missing_df.head(80)))
    lines.append("")
    lines.append("## 3. 总体排名")
    lines.append("")
    if not per_method_df.empty and "overall_score" in per_method_df:
        ranking = per_method_df.sort_values("overall_score", ascending=False, na_position="last")
        lines.extend(_table(ranking[["method", "overall_score", "similarity_score", "kinematic_score", "physical_score", "contact_score", "stability_score", "smoothness_score"]]))
    else:
        lines.append("没有可用 overall_score。")
    lines.append("")
    lines.append("## 4. 六大类平均结果")
    lines.append("")
    cols = [c for c in ["method", "mpjpe_mean", "end_effector_error_mean", "joint_limit_violation_rate", "foot_penetration_mean", "foot_sliding_total", "root_height_error_against_reference", "body_tilt_max_deg", "joint_jerk_mean", "overall_score"] if c in per_method_df.columns]
    if cols:
        lines.extend(_table(per_method_df[cols]))
    else:
        lines.append("没有可汇总的指标列。")
    lines.append("")
    lines.append("## 5. 方法优缺点分析")
    lines.append("")
    lines.extend(_auto_analysis(per_method_df))
    lines.append("")
    lines.append("## 6. 每个动作详细结果")
    lines.append("")
    detail_cols = [c for c in ["motion", "method", "overall_score", "mpjpe_mean", "root_position_error_mean", "foot_sliding_total", "foot_penetration_mean", "joint_limit_violation_rate", "episode_completed"] if c in per_motion_df.columns]
    if detail_cols:
        lines.extend(_table(per_motion_df[detail_cols].head(120)))
    else:
        lines.append("没有动作级结果。")
    lines.append("")
    lines.append("## 7. 不可用指标说明")
    lines.append("")
    any_unavailable = False
    for key, items in unavailable.items():
        if not items:
            continue
        any_unavailable = True
        lines.append(f"### {key}")
        for metric, reason in sorted(items.items()):
            lines.append(f"- `{metric}`: {reason}")
        lines.append("")
    if not any_unavailable:
        lines.append("没有不可用指标。")
    lines.append("")
    lines.append("## 8. 图表")
    lines.append("")
    if figures:
        for fig in figures:
            lines.append(f"- `{fig}`")
    else:
        lines.append("没有生成图表，通常是对应指标不可用。")
    lines.append("")
    lines.append("## 9. 结论")
    lines.append("")
    lines.extend(_conclusion(per_method_df))
    lines.append("")
    lines.append("## 10. 重要说明")
    lines.append("")
    lines.append("人体和机器人骨架不同，本工具不会直接比较所有关节角，而是优先比较 pelvis/root、head、hands、feet、knees、elbows 等关键点。机器人自身可行性指标基于 qpos/qvel/qacc、joint limit、接触和稳定性 proxy。缺字段时相关指标记为 not_available/NaN，不参与综合分权重。")

    out_md = Path(out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines), encoding="utf-8")
    out_html = Path(out_html)
    out_html.write_text(_markdown_to_simple_html("\n".join(lines)), encoding="utf-8")


def _table(df: pd.DataFrame) -> List[str]:
    if df.empty:
        return ["无数据。"]
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(_fmt(row.get(c)) for c in cols) + " |")
    return lines


def _fmt(value: Any) -> str:
    if pd.isna(value) if not isinstance(value, (list, dict, tuple)) else False:
        return "NaN"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _auto_analysis(df: pd.DataFrame) -> List[str]:
    if df.empty:
        return ["- 没有可比较的方法结果。"]
    checks = [
        ("mpjpe_mean", True, "动作相似性"),
        ("end_effector_error_mean", True, "末端跟踪"),
        ("joint_limit_violation_rate", True, "关节限位"),
        ("foot_sliding_total", True, "脚滑控制"),
        ("foot_penetration_mean", True, "穿地控制"),
        ("stability_score", False, "稳定性"),
        ("smoothness_score", False, "平滑性"),
        ("overall_score", False, "综合表现"),
    ]
    lines = []
    for metric, lower, label in checks:
        if metric not in df.columns:
            continue
        values = pd.to_numeric(df[metric], errors="coerce")
        if values.notna().sum() == 0:
            continue
        idx = values.idxmin() if lower else values.idxmax()
        lines.append(f"- {label}最好: **{df.loc[idx, 'method']}** (`{metric}`={values.loc[idx]:.6g})")
    if not lines:
        lines.append("- 关键指标不可用，无法自动判断优缺点。")
    return lines


def _conclusion(df: pd.DataFrame) -> List[str]:
    if df.empty or "overall_score" not in df.columns or pd.to_numeric(df["overall_score"], errors="coerce").notna().sum() == 0:
        return ["- 当前可用结果不足，无法给出方法排序。请先确认三种方法的 PKL 输出目录是否与原始动作匹配。"]
    ranking = df.sort_values("overall_score", ascending=False, na_position="last")
    best = ranking.iloc[0]
    lines = [f"- 综合评分最高的方法是 **{best['method']}**，平均 overall_score 为 `{best['overall_score']:.3f}`。"]
    if "contact_score" in ranking and pd.notna(best.get("contact_score")):
        lines.append("- 如果接触分数明显低，需要优先检查脚部 body 名称、地面高度和 contact_threshold 配置。")
    lines.append("- overall_score 只是辅助排序；最终判断应结合 MPJPE、脚滑/穿地、关节超限、稳定性和平滑性单项指标。")
    return lines


def _markdown_to_simple_html(markdown: str) -> str:
    body = []
    for line in markdown.splitlines():
        escaped = html.escape(line)
        if line.startswith("# "):
            body.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            body.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            body.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("- "):
            body.append(f"<p>{escaped}</p>")
        elif line.startswith("|"):
            body.append(f"<pre>{escaped}</pre>")
        else:
            body.append(f"<p>{escaped}</p>" if line.strip() else "")
    return "<!doctype html><html><head><meta charset='utf-8'><title>Retargeting Quality Report</title><style>body{font-family:Arial,sans-serif;max-width:1200px;margin:32px auto;line-height:1.5}pre{background:#f6f8fa;padding:6px;overflow:auto}code{background:#f6f8fa;padding:2px 4px}</style></head><body>" + "\n".join(body) + "</body></html>"

