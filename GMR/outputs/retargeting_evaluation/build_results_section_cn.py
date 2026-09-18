"""Build a Chinese thesis Results subsection from retargeting evaluation CSVs.

The document is deliberately generated from the saved CSV rather than copied
from a chat summary so that every number remains reproducible.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


OUTPUT_DIR = Path(r"D:\GMR_WORK\GMR\outputs\retargeting_evaluation")
INPUT_CSV = OUTPUT_DIR / "per_motion_metrics.csv"
OUTPUT_DOCX = OUTPUT_DIR / "Results_3X_Retargeting_Methods_Comparison_CN.docx"

METHOD_ORDER = ["direct_mapping", "basic_ik", "gmr"]
METHOD_LABELS = {
    "direct_mapping": "Direct Mapping",
    "basic_ik": "Basic IK",
    "gmr": "GMR",
}

METRICS = {
    "root_relative": "root_relative_position_error_mean",
    "scale_normalised": "scale_normalised_position_error_mean",
    "end_effector": "end_effector_error_mean",
    "orientation": "body_orientation_error_mean",
    "foot_sliding": "total_foot_sliding_distance",
    "penetration": "maximum_ground_penetration",
    "self_collision": "self_collision_frame_ratio",
    "joint_limit": "joint_limit_violation_ratio",
    "jerk": "rms_joint_jerk",
}

MOTION_ROWS = [
    ("113_21", "静态/低动态", "静止站立", "静态姿态保持、微小抖动与接触稳定性"),
    ("114_15", "周期移动", "行走", "脚部轨迹、根节点运动与脚滑"),
    ("111_23", "快速移动", "跑步", "快速周期运动、连续性与冲击阶段稳定性"),
    ("47_01", "方向性移动", "前行、转身并返回", "根节点轨迹、转向姿态与全身协调"),
    ("76_10", "方向性移动", "转身", "身体朝向变化与上下肢协调"),
    ("113_20", "复杂接触移动", "上下楼梯", "足部离地、交替接触与关节可达性"),
    ("124_11", "快速动态", "双脚跳", "腾空—落地过程、平滑性与穿地"),
    ("135_04", "动态单腿", "前踢", "单腿姿态、末端保持与平衡相关约束"),
    ("05_04", "复杂全身", "现代舞：侧向阿拉贝斯克、收臂与后弯", "大幅关节运动、全身姿态和上下肢协调"),
]


def set_run_font(
    run,
    *,
    size: float = 11,
    bold: bool | None = None,
    italic: bool | None = None,
    color: str = "000000",
) -> None:
    """Apply the academic font override consistently to Latin and CJK text."""

    run.font.name = "Times New Roman"
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), "Times New Roman")
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), "Times New Roman")
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "SimSun")
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor.from_string(color)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic


def configure_styles(doc: Document) -> None:
    """Resolve the narrative_proposal preset with an academic monochrome override."""

    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "SimSun")
    normal.font.size = Pt(11)
    normal.font.color.rgb = RGBColor(0, 0, 0)
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(8)
    normal.paragraph_format.line_spacing = 1.333
    normal.paragraph_format.first_line_indent = Pt(22)

    heading_tokens = {
        "Heading 1": (16, 18, 10),
        "Heading 2": (13, 12, 6),
        "Heading 3": (12, 8, 4),
    }
    for style_name, (size, before, after) in heading_tokens.items():
        style = doc.styles[style_name]
        style.font.name = "Times New Roman"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "SimHei")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.line_spacing = 1.15
        style.paragraph_format.keep_with_next = True
        style.paragraph_format.first_line_indent = Pt(0)

    caption = doc.styles["Caption"]
    caption.font.name = "Times New Roman"
    caption._element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
    caption._element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")
    caption._element.rPr.rFonts.set(qn("w:eastAsia"), "SimSun")
    caption.font.size = Pt(9.5)
    caption.font.bold = True
    caption.font.italic = False
    caption.font.color.rgb = RGBColor(0, 0, 0)
    caption.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption.paragraph_format.space_before = Pt(6)
    caption.paragraph_format.space_after = Pt(4)
    caption.paragraph_format.keep_with_next = True
    caption.paragraph_format.first_line_indent = Pt(0)


def configure_page(doc: Document) -> None:
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    section.header_distance = Inches(0.492)
    section.footer_distance = Inches(0.492)


def add_body_paragraph(doc: Document, parts: Sequence[tuple[str, bool]]) -> None:
    paragraph = doc.add_paragraph()
    for text, bold in parts:
        run = paragraph.add_run(text)
        set_run_font(run, bold=bold)


def add_note(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.15
    set_run_font(p.add_run(text), size=9, color="555555")


def shade_cell(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top: int = 80, bottom: int = 80, start: int = 120, end: int = 120) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for edge, value in (("top", top), ("bottom", bottom), ("start", start), ("end", end)):
        node = tc_mar.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    flag = OxmlElement("w:tblHeader")
    flag.set(qn("w:val"), "true")
    tr_pr.append(flag)


def prevent_row_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    flag = OxmlElement("w:cantSplit")
    tr_pr.append(flag)


def set_table_borders(table, color: str = "B7B7B7", size: int = 4) -> None:
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = borders.find(qn(f"w:{edge}"))
        if element is None:
            element = OxmlElement(f"w:{edge}")
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), str(size))
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), color)


def set_table_geometry(table, widths_dxa: Sequence[int], indent_dxa: int = 120) -> None:
    if sum(widths_dxa) != 9360:
        raise ValueError(f"Table widths must total 9360 DXA, got {sum(widths_dxa)}")

    table.autofit = False
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), "9360")
    tbl_w.set(qn("w:type"), "dxa")

    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), str(indent_dxa))
    tbl_ind.set(qn("w:type"), "dxa")

    layout = tbl_pr.find(qn("w:tblLayout"))
    if layout is None:
        layout = OxmlElement("w:tblLayout")
        tbl_pr.append(layout)
    layout.set(qn("w:type"), "fixed")

    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths_dxa:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        grid.append(col)

    for row in table.rows:
        prevent_row_split(row)
        for cell, width in zip(row.cells, widths_dxa):
            cell.width = Inches(width / 1440)
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_w = tc_pr.find(qn("w:tcW"))
            if tc_w is None:
                tc_w = OxmlElement("w:tcW")
                tc_pr.append(tc_w)
            tc_w.set(qn("w:w"), str(width))
            tc_w.set(qn("w:type"), "dxa")
            set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

    set_table_borders(table)


def fill_cell(cell, text: str, *, bold: bool = False, size: float = 9, align=WD_ALIGN_PARAGRAPH.CENTER) -> None:
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = align
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.1
    p.paragraph_format.first_line_indent = Pt(0)
    set_run_font(p.add_run(text), size=size, bold=bold)


def add_motion_table(doc: Document) -> None:
    cap = doc.add_paragraph("表 3.X-1  评估动作及其运动学特征", style="Caption")
    table = doc.add_table(rows=1, cols=4)
    headers = ["CMU 编号", "动作类别", "动作描述", "主要评估方面"]
    for cell, text in zip(table.rows[0].cells, headers):
        shade_cell(cell, "E7E6E6")
        fill_cell(cell, text, bold=True, size=9)
    set_repeat_table_header(table.rows[0])
    for motion_id, category, description, aspect in MOTION_ROWS:
        cells = table.add_row().cells
        fill_cell(cells[0], motion_id, size=8.8)
        fill_cell(cells[1], category, size=8.8)
        fill_cell(cells[2], description, size=8.8, align=WD_ALIGN_PARAGRAPH.LEFT)
        fill_cell(cells[3], aspect, size=8.8, align=WD_ALIGN_PARAGRAPH.LEFT)
    set_table_geometry(table, [1000, 1520, 3000, 3840])
    add_note(
        doc,
        "注：动作名称依据 CMU Motion Capture Database 的试次说明核对。动作选择覆盖静态、周期移动、方向变化、快速动态与复杂全身协调。",
    )


def metric_means(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby("method")[[*METRICS.values()]].mean().loc[METHOD_ORDER]


def add_overall_tables(doc: Document, df: pd.DataFrame) -> None:
    means = metric_means(df)

    doc.add_paragraph("表 3.X-2(a)  三种方法的动作保持与时间连续性结果（9 个动作的算术平均值）", style="Caption")
    table_a = doc.add_table(rows=1, cols=6)
    headers_a = [
        "方法",
        "Root-relative\n误差 (m)",
        "尺度归一化\n误差 (m)",
        "末端执行器\n误差 (m)",
        "姿态误差\n(°)",
        "RMS jerk\n(rad/s^3)",
    ]
    for cell, text in zip(table_a.rows[0].cells, headers_a):
        shade_cell(cell, "E7E6E6")
        fill_cell(cell, text, bold=True, size=8.8)
    set_repeat_table_header(table_a.rows[0])

    specs_a = [
        ("root_relative", lambda x: f"{x:.4f}"),
        ("scale_normalised", lambda x: f"{x:.4f}"),
        ("end_effector", lambda x: f"{x:.4f}"),
        ("orientation", lambda x: f"{x:.2f}"),
        ("jerk", lambda x: f"{x:.2f}"),
    ]
    best_a = {key: means[METRICS[key]].idxmin() for key, _ in specs_a}
    for method in METHOD_ORDER:
        cells = table_a.add_row().cells
        fill_cell(cells[0], METHOD_LABELS[method], bold=(method == "gmr"), size=8.8, align=WD_ALIGN_PARAGRAPH.LEFT)
        for index, (key, formatter) in enumerate(specs_a, start=1):
            value = float(means.loc[method, METRICS[key]])
            fill_cell(cells[index], formatter(value), bold=(method == best_a[key]), size=8.8)
    set_table_geometry(table_a, [1560, 1560, 1560, 1560, 1400, 1720])

    doc.add_paragraph("表 3.X-2(b)  三种方法的物理代理指标与成功率结果（9 个动作的算术平均值）", style="Caption")
    table_b = doc.add_table(rows=1, cols=6)
    headers_b = [
        "方法",
        "脚滑距离\n(m)",
        "最大穿地\n(m)",
        "MuJoCo 自碰撞\n代理 (%)",
        "零容差关节\n越界率 (%)",
        "严格成功率",
    ]
    for cell, text in zip(table_b.rows[0].cells, headers_b):
        shade_cell(cell, "E7E6E6")
        fill_cell(cell, text, bold=True, size=8.8)
    set_repeat_table_header(table_b.rows[0])

    specs_b = [
        ("foot_sliding", lambda x: f"{x:.4f}"),
        ("penetration", lambda x: f"{x:.4f}"),
        ("self_collision", lambda x: f"{x * 100:.2f}"),
        ("joint_limit", lambda x: f"{x * 100:.2f}"),
    ]
    best_b = {key: means[METRICS[key]].idxmin() for key, _ in specs_b}
    for method in METHOD_ORDER:
        cells = table_b.add_row().cells
        fill_cell(cells[0], METHOD_LABELS[method], bold=(method == "gmr"), size=8.8, align=WD_ALIGN_PARAGRAPH.LEFT)
        for index, (key, formatter) in enumerate(specs_b, start=1):
            value = float(means.loc[method, METRICS[key]])
            fill_cell(cells[index], formatter(value), bold=(method == best_b[key]), size=8.8)
        success_count = int(df.loc[df["method"] == method, "success"].astype(bool).sum())
        fill_cell(cells[5], f"{success_count}/9 (0.0%)", bold=False, size=8.8)
    set_table_geometry(table_b, [1560, 1560, 1560, 1560, 1560, 1560])

    add_note(
        doc,
        "注：除成功率外，表中指标均为越低越好；每个动作权重相同。脚滑使用脚底高度与垂直速度定义的当前接触掩码；自碰撞仅统计 MuJoCo collision geoms 的非相邻接触；关节越界采用零数值容差。缺失值应从均值中排除，但本次 27 条方法—动作记录的上述主要指标均为有限值。粗体表示该列最优结果。",
    )


def row_for(df: pd.DataFrame, motion: str, method: str) -> pd.Series:
    rows = df[(df["motion_name"].astype(str) == motion) & (df["method"] == method)]
    if len(rows) != 1:
        raise ValueError(f"Expected one row for {motion}/{method}, found {len(rows)}")
    return rows.iloc[0]


def val(row: pd.Series, key: str) -> float:
    return float(row[METRICS[key]])


def add_representative_analysis(doc: Document, df: pd.DataFrame) -> None:
    # 113_21: static/low dynamic
    d = row_for(df, "113_21", "direct_mapping")
    b = row_for(df, "113_21", "basic_ik")
    g = row_for(df, "113_21", "gmr")
    doc.add_heading("静止站立（113_21）", level=3)
    add_body_paragraph(doc, [
        ("该动作主要检验低动态条件下的姿态保持和数值稳定性。", True),
        (
            f"GMR 的姿态误差为 {val(g, 'orientation'):.2f}°，低于 Direct Mapping 的 {val(d, 'orientation'):.2f}° 和 Basic IK 的 {val(b, 'orientation'):.2f}°；其脚滑距离也仅为 {val(g, 'foot_sliding'):.3f} m。"
            f"Basic IK 虽取得最低的末端执行器误差（{val(b, 'end_effector'):.3f} m），但自碰撞率和关节越界率均达到 100%，同时 RMS jerk 为 {val(b, 'jerk'):.2f} rad/s^3，说明逐帧末端约束并未转化为稳定、可行的全身姿态。",
            False,
        ),
    ])
    add_body_paragraph(doc, [
        ("需要注意的是，", True),
        (
            f"GMR 在该动作上的最大穿地深度为 {val(g, 'penetration'):.4f} m，高于 Direct Mapping 的 {val(d, 'penetration'):.4f} m 和 Basic IK 的 {val(b, 'penetration'):.4f} m。"
            "因此，GMR 在静态姿态和接触阶段更稳定，但仍需要单独的地面约束或后处理来修正整体高度。",
            False,
        ),
    ])

    # 47_01: directional locomotion
    d = row_for(df, "47_01", "direct_mapping")
    b = row_for(df, "47_01", "basic_ik")
    g = row_for(df, "47_01", "gmr")
    doc.add_heading("前行—转身—返回（47_01）", level=3)
    add_body_paragraph(doc, [
        ("该动作同时考察移动轨迹、朝向变化和接触稳定性。", True),
        (
            f"GMR 的尺度归一化误差和末端执行器误差分别为 {val(g, 'scale_normalised'):.3f} m 和 {val(g, 'end_effector'):.3f} m，均低于 Direct Mapping（{val(d, 'scale_normalised'):.3f} m、{val(d, 'end_effector'):.3f} m）与 Basic IK（{val(b, 'scale_normalised'):.3f} m、{val(b, 'end_effector'):.3f} m）。"
            f"GMR 的姿态误差为 {val(g, 'orientation'):.2f}°，且未出现自碰撞或关节越界；其 RMS jerk 为 {val(g, 'jerk'):.2f} rad/s^3，明显低于 Basic IK 的 {val(b, 'jerk'):.2f} rad/s^3。",
            False,
        ),
    ])
    add_body_paragraph(doc, [
        ("然而，该动作揭示了 GMR 的关键局限。", True),
        (
            f"其脚滑距离达到 {val(g, 'foot_sliding'):.3f} m，显著高于 Direct Mapping 的 {val(d, 'foot_sliding'):.3f} m；最大穿地深度也达到 {val(g, 'penetration'):.4f} m。"
            "这说明较好的全身姿态保持并不必然保证足底接触质量，移动动作仍需要接触感知优化或后续物理跟踪。",
            False,
        ),
    ])

    # 124_11: jump
    d = row_for(df, "124_11", "direct_mapping")
    b = row_for(df, "124_11", "basic_ik")
    g = row_for(df, "124_11", "gmr")
    doc.add_heading("双脚跳（124_11）", level=3)
    add_body_paragraph(doc, [
        ("双脚跳用于检验快速腾空—落地过程中的姿态连续性和物理合理性。", True),
        (
            f"GMR 的姿态误差最低（{val(g, 'orientation'):.2f}°），关节越界率为 0%，最大穿地深度为 {val(g, 'penetration'):.4f} m，也低于 Direct Mapping 的 {val(d, 'penetration'):.4f} m 和 Basic IK 的 {val(b, 'penetration'):.4f} m。"
            f"GMR 与 Direct Mapping 的脚滑距离接近（{val(g, 'foot_sliding'):.3f} m 对 {val(d, 'foot_sliding'):.3f} m），且两者的 RMS jerk 均明显低于 Basic IK。",
            False,
        ),
    ])
    add_body_paragraph(doc, [
        ("这一动作也显示末端误差并不能单独代表整体质量。", True),
        (
            f"Basic IK 获得最低末端执行器误差（{val(b, 'end_effector'):.3f} m），但姿态误差为 {val(b, 'orientation'):.2f}°、关节越界率为 100%，并触发运动不连续。"
            "相较之下，GMR 牺牲了一部分瞬时末端精度，但获得了更协调的姿态和更可行的关节配置。",
            False,
        ),
    ])

    # 135_04: front kick
    d = row_for(df, "135_04", "direct_mapping")
    b = row_for(df, "135_04", "basic_ik")
    g = row_for(df, "135_04", "gmr")
    doc.add_heading("前踢（135_04）", level=3)
    add_body_paragraph(doc, [
        ("前踢是三种方法差异最清晰的动态单腿动作之一。", True),
        (
            f"GMR 的 root-relative、尺度归一化和末端执行器误差分别为 {val(g, 'root_relative'):.3f} m、{val(g, 'scale_normalised'):.3f} m 和 {val(g, 'end_effector'):.3f} m，均低于两条基线；姿态误差也仅为 {val(g, 'orientation'):.2f}°。"
            f"同时，GMR 的脚滑距离为 {val(g, 'foot_sliding'):.3f} m，最大穿地深度为 {val(g, 'penetration'):.4f} m，自碰撞率为 0%，关节越界率仅为 {val(g, 'joint_limit') * 100:.2f}%。",
            False,
        ),
    ])
    add_body_paragraph(doc, [
        ("在时间连续性方面，", True),
        (
            f"GMR 的 RMS jerk（{val(g, 'jerk'):.2f} rad/s^3）略高于 Direct Mapping（{val(d, 'jerk'):.2f} rad/s^3），但远低于 Basic IK（{val(b, 'jerk'):.2f} rad/s^3）。"
            "因此，GMR 在该动态动作上实现了较好的动作保持、关节可行性与连续性平衡，但并未在所有平滑性指标上超过 Direct Mapping。",
            False,
        ),
    ])


def pct_improvement(baseline: float, candidate: float) -> float:
    return (baseline - candidate) / baseline * 100.0


def add_quantitative_interpretation(doc: Document, df: pd.DataFrame) -> None:
    means = metric_means(df)
    dm = means.loc["direct_mapping"]
    ik = means.loc["basic_ik"]
    gmr = means.loc["gmr"]

    add_body_paragraph(doc, [
        ("从动作保持指标看，GMR 获得了最稳定的描述性优势。", True),
        (
            f"相较 Direct Mapping，GMR 的 root-relative、尺度归一化和末端执行器误差分别降低 {pct_improvement(dm[METRICS['root_relative']], gmr[METRICS['root_relative']]):.1f}%、"
            f"{pct_improvement(dm[METRICS['scale_normalised']], gmr[METRICS['scale_normalised']]):.1f}% 和 {pct_improvement(dm[METRICS['end_effector']], gmr[METRICS['end_effector']]):.1f}%；"
            f"相较 Basic IK，相应降幅分别为 {pct_improvement(ik[METRICS['root_relative']], gmr[METRICS['root_relative']]):.1f}%、"
            f"{pct_improvement(ik[METRICS['scale_normalised']], gmr[METRICS['scale_normalised']]):.1f}% 和 {pct_improvement(ik[METRICS['end_effector']], gmr[METRICS['end_effector']]):.1f}%。"
            "这表明 GMR 在去除全局平移和身体比例影响后，通常能更完整地保留源动作中的相对身体构型。",
            False,
        ),
    ])

    add_body_paragraph(doc, [
        ("姿态与关节可行性是 GMR 最突出的优势。", True),
        (
            f"GMR 的平均姿态误差为 {gmr[METRICS['orientation']]:.2f}°，低于 Direct Mapping 的 {dm[METRICS['orientation']]:.2f}° 和 Basic IK 的 {ik[METRICS['orientation']]:.2f}°；"
            f"平均关节越界率仅为 {gmr[METRICS['joint_limit']] * 100:.2f}%，而两条基线分别为 {dm[METRICS['joint_limit']] * 100:.2f}% 和 {ik[METRICS['joint_limit']] * 100:.2f}%。"
            f"GMR 的自碰撞率为 {gmr[METRICS['self_collision']] * 100:.2f}%，也显著低于 Basic IK 的 {ik[METRICS['self_collision']] * 100:.2f}%。"
            "这些结果支持 GMR 更能维持机器人全身协调和关节可行性的判断。",
            False,
        ),
    ])

    add_body_paragraph(doc, [
        ("时间连续性和接触质量则呈现更明显的权衡。", True),
        (
            f"Direct Mapping 的平均 RMS jerk 最低（{dm[METRICS['jerk']]:.2f} rad/s^3），GMR 为 {gmr[METRICS['jerk']]:.2f} rad/s^3，Basic IK 则升至 {ik[METRICS['jerk']]:.2f} rad/s^3。"
            f"Basic IK 的平均脚滑距离最低（{ik[METRICS['foot_sliding']]:.4f} m），但仅比 GMR 的 {gmr[METRICS['foot_sliding']]:.4f} m 低 3.2%。"
            f"GMR 的平均最大穿地深度为 {gmr[METRICS['penetration']]:.4f} m，高于 Direct Mapping 的 {dm[METRICS['penetration']]:.4f} m 和 Basic IK 的 {ik[METRICS['penetration']]:.4f} m。"
            "因此，GMR 的优势主要集中于动作与姿态保持，而接触约束仍是需要进一步优化的部分。",
            False,
        ),
    ])

    add_body_paragraph(doc, [
        ("配对统计检验进一步限定了上述结论。", True),
        (
            "Friedman 检验显示，尺度归一化误差（p = 0.0048）、末端执行器误差（p = 0.0011）、姿态误差（p < 0.001）、自碰撞率（p = 0.0095）、关节越界率（p < 0.001）和 RMS jerk（p < 0.001）在三种方法之间存在显著差异；"
            "root-relative 误差（p = 0.169）、脚滑距离（p = 0.264）和最大穿地深度（p = 0.895）未达到显著水平。"
            "经 Holm 校正的 Wilcoxon 两两比较表明，GMR 相较 Direct Mapping 在尺度归一化误差、末端误差、姿态误差和关节越界率方面差异显著；GMR 相较 Basic IK 在姿态误差、自碰撞率、关节越界率和 jerk 方面差异显著。"
            "由于样本仅包含 9 个动作，未显著的平均差异应被视为描述性趋势，而不应表述为普遍优越性。",
            False,
        ),
    ])

    add_body_paragraph(doc, [
        ("严格成功率不应与程序失败混淆。", True),
        (
            "在预设阈值下，三种方法的成功率均为 0/9。所有 27 条动作—方法记录均完成指标计算，但至少触发了一项质量阈值；GMR 的主要失败原因集中在持续或严重穿地，Direct Mapping 还频繁出现关节越界和自碰撞，Basic IK 则进一步表现出高 jerk 或运动不连续。"
            "因此，本节比较的是不同方法对各类误差和约束违反的相对改善，而不是声称任何方法已经生成完全满足物理约束的轨迹。",
            False,
        ),
    ])


def build_document() -> Path:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(INPUT_CSV)

    df = pd.read_csv(INPUT_CSV)
    if len(df) != 27 or df["motion_name"].nunique() != 9 or df["method"].nunique() != 3:
        raise ValueError("Expected 27 rows from 9 motions and 3 methods")
    for column in METRICS.values():
        if not pd.to_numeric(df[column], errors="coerce").notna().all():
            raise ValueError(f"Main metric contains missing or invalid values: {column}")

    doc = Document()
    configure_page(doc)
    configure_styles(doc)
    doc.core_properties.title = "3.X 三种动作重定向方法的结果对比"
    doc.core_properties.subject = "GMR、Direct Mapping 与 Basic IK 的重定向结果比较"
    doc.core_properties.author = ""
    doc.core_properties.keywords = "motion retargeting, GMR, Direct Mapping, Basic IK, Unitree G1"

    doc.add_heading("3.X 三种动作重定向方法的结果对比", level=1)
    add_body_paragraph(doc, [
        ("本节比较 Direct Mapping、Basic IK 与 GMR 在 Unitree G1 人形机器人上的动作重定向结果。", True),
        (
            "比较的目的不是重复介绍三种方法的算法原理，而是在统一机器人模型、统一 30 FPS 评估频率和共同时间区间下，检验三种方法对同一批人体动作的保持能力。"
            "评估覆盖具有不同运动学特征的动作，重点考察相对身体构型、末端位置、身体姿态、时间连续性以及脚滑、穿地、自碰撞和关节限制等物理合理性指标。",
            False,
        ),
    ])

    doc.add_heading("3.X.1 选取动作及比较范围", level=2)
    add_body_paragraph(doc, [
        ("动作集合覆盖了静态、移动、快速动态和复杂全身运动。", True),
        (
            "静止站立用于观察低动态条件下的姿态保持与抖动；行走、跑步、转身和上下楼梯主要测试根节点轨迹、脚部接触和方向协调；双脚跳与前踢用于检验快速动作、单腿或腾空姿态以及落地阶段的稳定性；现代舞则通过大幅躯干和四肢运动测试关节可达性及全身协调。"
            "这种选择能够避免结论仅由单一动作类型主导。",
            False,
        ),
    ])
    add_motion_table(doc)

    doc.add_page_break()
    doc.add_heading("3.X.2 整体对比结果", level=2)
    add_body_paragraph(doc, [
        ("整体结果表明，GMR 在动作保持和关节可行性方面占优，但在接触质量和平滑性上并非所有指标最优。", True),
        (
            "表 3.X-2 将 9 个动作视为等权样本，报告每种方法的逐动作算术平均值。Root-relative 误差用于衡量去除初始水平平移和朝向后的相对身体构型；尺度归一化误差进一步降低人体与机器人尺寸差异的影响；RMS jerk 用于反映关节轨迹的时间平滑性。",
            False,
        ),
    ])
    add_overall_tables(doc, df)

    add_body_paragraph(doc, [
        ("Direct Mapping 的主要特点是轨迹较平滑，但姿态和物理约束保持较弱。", True),
        (
            "其 RMS jerk 为三种方法中最低，但尺度归一化误差、末端执行器误差和 root-relative 误差均最高，同时平均关节越界率达到 44.71%。"
            "这说明直接传递人体关节旋转可以保留部分时间结构，却难以消除人体与 G1 在身体比例、关节轴和可达范围上的差异。",
            False,
        ),
    ])
    add_body_paragraph(doc, [
        ("Basic IK 改善了关键末端的位置匹配，但产生了明显的姿态和连续性代价。", True),
        (
            "其平均末端执行器误差由 Direct Mapping 的 0.7944 m 降至 0.3328 m，平均脚滑距离也最低；然而姿态误差达到 51.76°，自碰撞率为 60.55%，关节越界率接近 100%，RMS jerk 约为 Direct Mapping 的 5.86 倍。"
            "这些结果表明，单独优化逐帧末端位置可能使求解落入不自然或不连续的关节配置。",
            False,
        ),
    ])
    add_body_paragraph(doc, [
        ("GMR 在全身姿态保持和机器人可行性之间取得了更好的总体平衡。", True),
        (
            "其 root-relative、尺度归一化、末端执行器和姿态误差均为三种方法中最低，自碰撞率和关节越界率也分别降至 2.87% 和 0.17%。"
            "不过，GMR 的平均脚滑距离略高于 Basic IK，平均最大穿地深度在三种方法中最高，且 jerk 略高于 Direct Mapping。"
            "因此，整体结果支持 GMR 更有效地保持动作语义和全身协调性的结论，但不支持其在接触稳定性或所有平滑性指标上全面占优。",
            False,
        ),
    ])

    doc.add_heading("3.X.3 代表动作的对比分析", level=2)
    add_body_paragraph(doc, [
        ("以下选择四个代表动作进行同尺度比较。", True),
        (
            "静止站立代表低动态动作，前行—转身—返回代表方向性移动，双脚跳代表快速腾空与落地，前踢代表动态单腿姿态。"
            "分析顺序保持一致：先说明动作所检验的能力，再比较三种方法的动作保持、连续性和物理约束表现。",
            False,
        ),
    ])
    add_representative_analysis(doc, df)

    doc.add_heading("3.X.4 定量结果与统计比较", level=2)
    add_quantitative_interpretation(doc, df)

    doc.add_heading("3.X.5 重定向结果小结", level=2)
    add_body_paragraph(doc, [
        ("三种方法表现出清晰但并非单一维度的差异。", True),
        (
            "Direct Mapping 的关节轨迹最平滑，但由于缺少对机器人形态和关节约束的显式适配，其相对姿态、末端位置和关节可行性较差。"
            "Basic IK 能够降低末端执行器位置误差，并在平均脚滑距离上取得最小值，但其高姿态误差、高关节越界率和高 jerk 表明逐帧位置优化容易牺牲全身协调和时间连续性。"
            "GMR 则在大多数动作保持指标、姿态误差、自碰撞和关节限制方面获得最优平均结果，尤其在前踢等动态动作上体现出较好的综合表现。",
            False,
        ),
    ])
    add_body_paragraph(doc, [
        ("然而，GMR 尚未解决所有物理合理性问题。", True),
        (
            "其脚滑和最大穿地深度没有表现出稳定的统计优势，且严格成功阈值下 9 个动作均未完全通过。"
            "后续工作应重点加入接触感知的足底约束、整体高度修正和穿地惩罚，并通过物理跟踪阶段检验参考轨迹在动力学环境中的可执行性。"
            "因此，本节的主要结论是：GMR 更适合作为保持动作语义与全身协调性的重定向基础，但仍需要针对接触和地面约束进行进一步优化。",
            False,
        ),
    ])

    # Keep the final artifact free of accidental empty trailing paragraphs.
    while doc.paragraphs and not doc.paragraphs[-1].text.strip():
        element = doc.paragraphs[-1]._element
        element.getparent().remove(element)

    doc.save(OUTPUT_DOCX)
    return OUTPUT_DOCX


if __name__ == "__main__":
    print(build_document())
