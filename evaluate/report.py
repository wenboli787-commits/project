"""Markdown reporting for a completed three-method evaluation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils import UNAVAILABLE


def _nested(data: dict[str, Any], *keys: str) -> Any:
    value: Any = data
    for key in keys:
        if not isinstance(value, dict):
            return UNAVAILABLE
        value = value.get(key, UNAVAILABLE)
    return value


def _display(value: Any, digits: int = 5) -> str:
    if value is None or value == UNAVAILABLE:
        return "unavailable"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.{digits}g}"
    return str(value)


def _mean_contact_f1(summary: dict[str, Any]) -> Any:
    contact = _nested(summary, "contact", "foot_contact_accuracy")
    if not isinstance(contact, dict):
        return UNAVAILABLE
    values = [item.get("f1") for key, item in contact.items() if key in {"left_foot", "right_foot"} and isinstance(item, dict)]
    return sum(values) / len(values) if values else UNAVAILABLE


def write_markdown_report(path: Path, run_metadata: dict[str, Any], summaries: dict[str, dict[str, Any]], alignment: dict[str, dict[str, Any]], warnings: list[str], plot_files: list[Path]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 人形机器人动作重定向评估报告",
        "",
        f"生成时间（UTC）：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 本次输入",
        "",
        f"- Simulator：`{run_metadata.get('simulator', 'unknown')}`",
        f"- Reference：`{run_metadata.get('reference_path', '')}`",
        f"- Robot model：`{run_metadata.get('robot_model', 'not supplied')}`",
        f"- Mapping：`{run_metadata.get('mapping_path', '')}`",
        "",
        "`unavailable` 表示日志没有提供该指标所需的数据；它不是 0，也不代表通过。",
        "",
        "## 方法总览",
        "",
        "| Method | EE mean error (m) | Root mean error (m) | Contact F1 | Joint-limit frame ratio | Fall | Mean DOF jerk | Energy proxy | Tracking |",
        "|---|---:|---:|---:|---:|---|---:|---:|---:|",
    ]
    for method, summary in summaries.items():
        lines.append("| " + " | ".join([
            method,
            _display(_nested(summary, "end_effector_position_error", "aggregate_mean")),
            _display(_nested(summary, "root_trajectory_error", "position", "mean")),
            _display(_mean_contact_f1(summary)),
            _display(_nested(summary, "joint_limit_violation", "violation_frame_ratio")),
            _display(_nested(summary, "stability", "fall_detected")),
            _display(_nested(summary, "smoothness", "dof", "mean_jerk")),
            _display(_nested(summary, "effort_energy", "energy_proxy")),
            _display(_nested(summary, "tracking_error", "dof_pos", "mean")),
        ]) + " |")
    lines.extend(["", "## 时间对齐与归一化", ""])
    for method, notes in alignment.items():
        lines.append(f"- **{method}**：{notes}")
    lines.extend(["", "## 解读提示", "", "- 末端、根轨迹和旋转误差用于比较动作相似度；它们要求 reference 与 robot landmark 在 YAML 中正确对应。", "- Joint-limit、接触、穿透、平滑度和 effort 描述可执行性/动作质量；它们不直接等于动作像不像。", "- Tracking error 只在同时存在 target 与 actual 轨迹时才有意义。仅有重定向 qpos 时会显示 `unavailable`。", "- Locomotion success 的默认含义是未摔倒且位移达到 YAML 的 `min_forward_displacement`；非移动动作请据任务重写该规则。", "", "## 输出文件", "", "- `summary_metrics.json`：完整的嵌套指标，保留 unavailable 状态。", "- `summary_metrics.csv`：适合 Excel 对比的扁平表。", "- `per_frame_metrics.csv`：每帧误差、接触、穿透等序列。", "- `plots/`：图表。", ""])
    if plot_files:
        lines.append("生成图表：" + ", ".join(f"`plots/{item.name}`" for item in plot_files))
        lines.append("")
    lines.extend(["## Warnings", ""])
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- 无。")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
