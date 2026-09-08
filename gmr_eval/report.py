from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Dict, List

import numpy as np


def generate_report(
    output_dir: Path,
    config: Dict[str, Any],
    per_motion_rows: List[Dict[str, Any]],
    summary_rows: List[Dict[str, Any]],
    missing_rows: List[Dict[str, Any]],
    unavailable: Dict[str, Dict[str, str]],
    figure_paths: List[str],
    warnings: List[str],
) -> None:
    """Write Markdown and HTML reports for the evaluation run."""
    output_dir.mkdir(parents=True, exist_ok=True)
    md = build_markdown_report(config, per_motion_rows, summary_rows, missing_rows, unavailable, figure_paths, warnings)
    (output_dir / "report.md").write_text(md, encoding="utf-8")
    (output_dir / "report.html").write_text(markdown_to_html(md), encoding="utf-8")


def build_markdown_report(
    config: Dict[str, Any],
    per_motion_rows: List[Dict[str, Any]],
    summary_rows: List[Dict[str, Any]],
    missing_rows: List[Dict[str, Any]],
    unavailable: Dict[str, Dict[str, str]],
    figure_paths: List[str],
    warnings: List[str],
) -> str:
    best_method = _best_method(summary_rows)
    lines: List[str] = []
    lines.append("# Retargeting Quality Evaluation Report")
    lines.append("")
    lines.append("## Overall Conclusion")
    if best_method:
        lines.append(f"- Overall best method by average overall_score: **{best_method}**.")
    else:
        lines.append("- Overall best method: unavailable because no valid motion-method rows were evaluated.")
    lines.append(f"- Evaluated motion-method pairs: **{len(per_motion_rows)}**.")
    lines.append(f"- Missing/failed records: **{len(missing_rows)}**.")
    lines.append(f"- Sync mode: `{config.get('sync_mode')}`, target_fps: `{config.get('target_fps')}`.")
    if warnings:
        lines.append("- Run warnings: " + " | ".join(dict.fromkeys(warnings)))
    lines.append("")

    lines.append("## Method Summary")
    if summary_rows:
        header = [
            "method",
            "success_rate",
            "mean_overall_score",
            "mean_aligned_global_error_mm",
            "mean_root_relative_error_mm",
            "mean_total_foot_sliding_m",
            "mean_max_ground_penetration_m",
            "mean_self_collision_count",
            "mean_sudden_jump_count",
        ]
        lines.extend(_markdown_table(summary_rows, header))
    else:
        lines.append("No summary metrics available.")
    lines.append("")

    lines.append("## Main Problems By Method")
    for row in summary_rows:
        method = row.get("method", "")
        problems = []
        for label, key, unit in [
            ("global error", "mean_aligned_global_error_mm", "mm"),
            ("root-relative error", "mean_root_relative_error_mm", "mm"),
            ("foot sliding", "mean_total_foot_sliding_m", "m"),
            ("ground penetration", "mean_max_ground_penetration_m", "m"),
            ("self collision", "mean_self_collision_count", "count"),
            ("sudden jumps", "mean_sudden_jump_count", "count"),
        ]:
            value = _to_float(row.get(key, np.nan))
            if np.isfinite(value):
                problems.append((value, f"{label}={value:.4g}{unit}"))
        if problems:
            worst = sorted(problems, key=lambda item: item[0], reverse=True)[:3]
            lines.append(f"- **{method}**: " + ", ".join(item[1] for item in worst))
        else:
            lines.append(f"- **{method}**: no numeric problem metrics available.")
    lines.append("")

    best_worst = _best_worst_per_motion(per_motion_rows)
    lines.append("## Best And Worst Method Per Motion")
    if best_worst:
        lines.extend(_markdown_table(best_worst, ["motion_name", "best_method", "best_score", "worst_method", "worst_score"]))
    else:
        lines.append("No per-motion ranking available.")
    lines.append("")

    recommendations = _recommendations(per_motion_rows)
    lines.append("## Thesis Display Suggestions")
    if recommendations:
        lines.append("- Motions suitable for thesis video/table display: " + ", ".join(recommendations))
    else:
        lines.append("- No clear high-quality examples could be selected from available scores.")
    lines.append("- For final thesis numbers, install `mujoco` and `matplotlib` in WSL so FK/contact figures are fully computed.")
    lines.append("")

    lines.append("## Figures")
    for fig in figure_paths:
        name = Path(fig).name
        rel = f"figures/{name}"
        lines.append(f"- [{name}]({rel})")
        lines.append(f"  ![]({rel})")
    lines.append("")

    lines.append("## Missing Files")
    if missing_rows:
        lines.extend(_markdown_table(missing_rows[:50], ["motion_name", "method", "missing_type", "detail"]))
        if len(missing_rows) > 50:
            lines.append(f"- Additional missing/failed records omitted from report table: {len(missing_rows) - 50}")
    else:
        lines.append("No missing files were recorded.")
    lines.append("")

    lines.append("## Unavailable Metrics")
    if unavailable:
        for item, details in list(unavailable.items())[:80]:
            if details:
                lines.append(f"- **{item}**: " + "; ".join(f"{k}: {v}" for k, v in sorted(details.items())[:12]))
        if len(unavailable) > 80:
            lines.append(f"- Additional unavailable-metric groups omitted: {len(unavailable) - 80}")
    else:
        lines.append("No unavailable metrics were reported.")
    lines.append("")

    lines.append("## Notes")
    lines.append("- `raw_global_error_mm` is computed without root/heading alignment.")
    lines.append("- `aligned_global_error_mm` uses initial root and heading alignment.")
    lines.append("- `root_relative_error_mm` removes root translation and emphasizes body pose structure.")
    lines.append("- `bone_orientation_error_deg` is a fallback when no mapped robot reference joint angles are available.")
    return "\n".join(lines) + "\n"


def markdown_to_html(markdown: str) -> str:
    """Small Markdown-to-HTML renderer sufficient for the generated report."""
    body_lines = []
    in_ul = False
    in_table = False
    for raw in markdown.splitlines():
        line = raw.rstrip()
        if line.startswith("|") and line.endswith("|"):
            if not in_table:
                body_lines.append("<table>")
                in_table = True
            cells = [html.escape(cell.strip()) for cell in line.strip("|").split("|")]
            if set(cells[0]) <= {"-", ":"}:
                continue
            tag = "th" if all(part.startswith("-") or part == "" for part in cells) else "td"
            if any(cell in {"---", ":---", "---:", ":---:"} for cell in cells):
                continue
            body_lines.append("<tr>" + "".join(f"<{tag}>{cell}</{tag}>" for cell in cells) + "</tr>")
            continue
        if in_table:
            body_lines.append("</table>")
            in_table = False
        stripped = line.strip()
        if stripped.startswith("![](") and stripped.endswith(")"):
            src = html.escape(stripped[4:-1])
            body_lines.append(f'<img src="{src}" alt="">')
            continue
        if line.startswith("# "):
            body_lines.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            body_lines.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("- "):
            if not in_ul:
                body_lines.append("<ul>")
                in_ul = True
            body_lines.append(f"<li>{_inline_markdown(line[2:])}</li>")
        elif not line:
            if in_ul:
                body_lines.append("</ul>")
                in_ul = False
        else:
            body_lines.append(f"<p>{_inline_markdown(line)}</p>")
    if in_ul:
        body_lines.append("</ul>")
    if in_table:
        body_lines.append("</table>")
    return """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Retargeting Quality Evaluation Report</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; line-height: 1.55; color: #202124; }
table { border-collapse: collapse; width: 100%; margin: 12px 0 24px; font-size: 14px; }
td, th { border: 1px solid #ddd; padding: 6px 8px; text-align: left; }
th { background: #f5f5f5; }
img { max-width: 900px; width: 100%; border: 1px solid #eee; margin: 8px 0 18px; }
code { background: #f3f4f4; padding: 1px 4px; border-radius: 3px; }
</style>
</head>
<body>
""" + "\n".join(body_lines) + "\n</body>\n</html>\n"


def _markdown_table(rows: List[Dict[str, Any]], columns: List[str]) -> List[str]:
    lines = ["|" + "|".join(columns) + "|", "|" + "|".join(["---"] * len(columns)) + "|"]
    for row in rows:
        values = []
        for col in columns:
            value = row.get(col, "")
            value = _format_value(value)
            values.append(str(value).replace("\n", " "))
        lines.append("|" + "|".join(values) + "|")
    return lines


def _best_method(summary_rows: List[Dict[str, Any]]) -> str:
    finite = [(row.get("method", ""), _to_float(row.get("mean_overall_score", np.nan))) for row in summary_rows]
    finite = [(method, score) for method, score in finite if method and np.isfinite(score)]
    if not finite:
        return ""
    return str(max(finite, key=lambda item: item[1])[0])


def _best_worst_per_motion(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    motions = sorted({str(row.get("motion_name", "")) for row in rows if row.get("motion_name")})
    out = []
    for motion in motions:
        subset = [row for row in rows if row.get("motion_name") == motion and np.isfinite(_to_float(row.get("overall_score", np.nan)))]
        if not subset:
            continue
        best = max(subset, key=lambda row: _to_float(row.get("overall_score", np.nan)))
        worst = min(subset, key=lambda row: _to_float(row.get("overall_score", np.nan)))
        out.append(
            {
                "motion_name": motion,
                "best_method": best.get("method", ""),
                "best_score": best.get("overall_score", np.nan),
                "worst_method": worst.get("method", ""),
                "worst_score": worst.get("overall_score", np.nan),
            }
        )
    return out


def _recommendations(rows: List[Dict[str, Any]]) -> List[str]:
    good = [
        row
        for row in rows
        if _to_float(row.get("success", 0)) >= 1
        and np.isfinite(_to_float(row.get("overall_score", np.nan)))
    ]
    good.sort(key=lambda row: _to_float(row.get("overall_score", np.nan)), reverse=True)
    labels = []
    for row in good[:5]:
        labels.append(f"{row.get('motion_name')} ({row.get('method')}, score={_to_float(row.get('overall_score')):.3f})")
    return labels


def _inline_markdown(text: str) -> str:
    text = html.escape(text)
    text = text.replace("**", "")
    return text


def _format_value(value: Any) -> str:
    number = _to_float(value)
    if np.isfinite(number):
        return f"{number:.6g}"
    if value is None:
        return ""
    return str(value)


def _to_float(value: Any) -> float:
    try:
        return float(np.asarray(value).reshape(-1)[0])
    except Exception:
        return np.nan
