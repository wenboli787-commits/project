# GMR Optimisation 操作手册

## 1. 环境准备

进入 Ubuntu/WSL：

```bash
cd /mnt/d/GMR_WORK/GMR
conda activate gmr
```

确认依赖：

```bash
python - <<'PY'
import numpy
import mujoco
import scipy
import matplotlib
print("environment ok")
PY
```

本模块依赖：

- `numpy`
- `mujoco`
- `scipy`，可选；没有时 smoothing 会退化为 moving average
- `matplotlib`

## 2. 默认路径

Raw GMR pkl 输入：

```text
/mnt/d/GMR_WORK/GMR/outputs/final results/pkl gmr
```

Optimised GMR pkl 输出：

```text
/mnt/d/GMR_WORK/GMR/outputs/final results/pkl gmr optimised
```

评估结果输出：

```text
/mnt/d/GMR_WORK/GMR/outputs/final results/gmr optimisation evaluation
```

Optimised mjlab csv 输出：

```text
/mnt/d/GMR_WORK/GMR/outputs/final results/mjlab csv optimised
```

Unitree G1 XML：

```text
/mnt/d/GMR_WORK/GMR/assets/unitree_g1/g1_mocap_29dof.xml
```

## 3. 第一步：检查 pkl 结构

先选择一个 Raw GMR pkl 做结构检查：

```bash
python scripts/mjlab_tools/inspect_gmr_pkl.py \
  --input_pkl "/mnt/d/GMR_WORK/GMR/outputs/final results/pkl gmr/某个文件.pkl" \
  --output_json "/mnt/d/GMR_WORK/GMR/outputs/final results/gmr optimisation evaluation/pkl_structure_report.json"
```

检查输出中是否能识别：

- `qpos`
- `dof_pos`
- `root_pos`
- `root_quat`
- `body_pos`
- `body_names`
- `fps` 或 `dt`

如果有 warning，不一定代表失败；warning 的作用是提示哪些字段无法自动识别。

## 4. 第二步：评估单个 Raw GMR

```bash
python scripts/mjlab_tools/evaluate_gmr_executability.py \
  --input_pkl "/mnt/d/GMR_WORK/GMR/outputs/final results/pkl gmr/某个文件.pkl" \
  --xml_path "/mnt/d/GMR_WORK/GMR/assets/unitree_g1/g1_mocap_29dof.xml" \
  --output_json "/mnt/d/GMR_WORK/GMR/outputs/final results/gmr optimisation evaluation/example_raw_eval.json"
```

调试时可以只跑前 N 帧：

```bash
python scripts/mjlab_tools/evaluate_gmr_executability.py \
  --input_pkl "/mnt/d/GMR_WORK/GMR/outputs/final results/pkl gmr/某个文件.pkl" \
  --xml_path "/mnt/d/GMR_WORK/GMR/assets/unitree_g1/g1_mocap_29dof.xml" \
  --output_json "/mnt/d/GMR_WORK/GMR/outputs/final results/gmr optimisation evaluation/example_raw_eval.json" \
  --max_frames 100
```

正式评估不要加 `--max_frames`。

## 5. 第三步：优化单个动作

单动作优化命令：

```bash
python scripts/mjlab_tools/optimise_gmr_motion.py \
  --input_pkl "/mnt/d/GMR_WORK/GMR/outputs/final results/pkl gmr/某个文件.pkl" \
  --output_pkl "/mnt/d/GMR_WORK/GMR/outputs/final results/pkl gmr optimised/某个文件_optimised.pkl" \
  --xml_path "/mnt/d/GMR_WORK/GMR/assets/unitree_g1/g1_mocap_29dof.xml" \
  --report_json "/mnt/d/GMR_WORK/GMR/outputs/final results/gmr optimisation evaluation/reports/某个文件_optimisation_report.json" \
  --max_candidates 80 \
  --ground_z 0.0 \
  --random_seed 42
```

默认不会做 joint limit clipping，只会检测 violation。若论文实验需要允许 clipping：

```bash
python scripts/mjlab_tools/optimise_gmr_motion.py \
  --input_pkl "/mnt/d/GMR_WORK/GMR/outputs/final results/pkl gmr/某个文件.pkl" \
  --output_pkl "/mnt/d/GMR_WORK/GMR/outputs/final results/pkl gmr optimised/某个文件_optimised.pkl" \
  --xml_path "/mnt/d/GMR_WORK/GMR/assets/unitree_g1/g1_mocap_29dof.xml" \
  --report_json "/mnt/d/GMR_WORK/GMR/outputs/final results/gmr optimisation evaluation/reports/某个文件_optimisation_report.json" \
  --allow_joint_limit_clipping True
```

建议默认先不用 clipping，因为 clipping 可能引入 joint jump。

## 6. 第四步：批量优化所有 Raw GMR

直接运行：

```bash
bash scripts/mjlab_tools/run_batch_gmr_optimisation.sh
```

脚本会自动：

1. 遍历 `/mnt/d/GMR_WORK/GMR/outputs/final results/pkl gmr` 中所有 `.pkl`。
2. 对每个动作运行 `optimise_gmr_motion.py`。
3. 输出 optimised pkl 到 `pkl gmr optimised`。
4. 输出每个动作的 JSON report 到 `gmr optimisation evaluation/reports`。
5. 汇总生成：

```text
/mnt/d/GMR_WORK/GMR/outputs/final results/gmr optimisation evaluation/gmr_raw_vs_optimised_summary.csv
```

可选环境变量：

```bash
MAX_CANDIDATES=120 bash scripts/mjlab_tools/run_batch_gmr_optimisation.sh
```

```bash
ALLOW_JOINT_LIMIT_CLIPPING=True bash scripts/mjlab_tools/run_batch_gmr_optimisation.sh
```

```bash
GROUND_Z=0.0 RANDOM_SEED=42 bash scripts/mjlab_tools/run_batch_gmr_optimisation.sh
```

## 7. 第五步：生成对比图和 markdown 报告

```bash
python scripts/mjlab_tools/plot_gmr_optimisation_comparison.py \
  --summary_csv "/mnt/d/GMR_WORK/GMR/outputs/final results/gmr optimisation evaluation/gmr_raw_vs_optimised_summary.csv" \
  --output_dir "/mnt/d/GMR_WORK/GMR/outputs/final results/gmr optimisation evaluation/plots"
```

会生成：

- `composite_score_raw_vs_optimised.png`
- `max_penetration_depth_raw_vs_optimised.png`
- `penetration_frame_count_raw_vs_optimised.png`
- `total_foot_sliding_raw_vs_optimised.png`
- `self_collision_frame_count_raw_vs_optimised.png`
- `mean_jerk_raw_vs_optimised.png`
- `max_joint_jump_raw_vs_optimised.png`
- `joint_limit_violation_ratio_raw_vs_optimised.png`
- `improvement_percentage_overview.png`

同时生成：

```text
/mnt/d/GMR_WORK/GMR/outputs/final results/gmr optimisation evaluation/gmr_optimisation_report.md
```

图表标题、坐标轴和图例均为英文，便于直接放入英国硕士论文。

## 8. 第六步：把 optimised pkl 转成 mjlab csv

```bash
bash scripts/mjlab_tools/run_batch_optimised_pkl_to_csv.sh
```

脚本会遍历：

```text
/mnt/d/GMR_WORK/GMR/outputs/final results/pkl gmr optimised
```

并输出 csv 到：

```text
/mnt/d/GMR_WORK/GMR/outputs/final results/mjlab csv optimised
```

文件名只把 `.pkl` 改为 `.csv`。

## 9. 推荐完整运行流程

```bash
cd /mnt/d/GMR_WORK/GMR
conda activate gmr

python scripts/mjlab_tools/inspect_gmr_pkl.py \
  --input_pkl "/mnt/d/GMR_WORK/GMR/outputs/final results/pkl gmr/某个文件.pkl" \
  --output_json "/mnt/d/GMR_WORK/GMR/outputs/final results/gmr optimisation evaluation/pkl_structure_report.json"

python scripts/mjlab_tools/evaluate_gmr_executability.py \
  --input_pkl "/mnt/d/GMR_WORK/GMR/outputs/final results/pkl gmr/某个文件.pkl" \
  --xml_path "/mnt/d/GMR_WORK/GMR/assets/unitree_g1/g1_mocap_29dof.xml" \
  --output_json "/mnt/d/GMR_WORK/GMR/outputs/final results/gmr optimisation evaluation/example_raw_eval.json"

bash scripts/mjlab_tools/run_batch_gmr_optimisation.sh

python scripts/mjlab_tools/plot_gmr_optimisation_comparison.py \
  --summary_csv "/mnt/d/GMR_WORK/GMR/outputs/final results/gmr optimisation evaluation/gmr_raw_vs_optimised_summary.csv" \
  --output_dir "/mnt/d/GMR_WORK/GMR/outputs/final results/gmr optimisation evaluation/plots"

bash scripts/mjlab_tools/run_batch_optimised_pkl_to_csv.sh
```

## 10. 如何读 summary CSV

重点列：

- `optimisation_status`
  - `accepted`：存在安全可接受的优化候选。
  - `rollback_to_raw`：没有候选满足安全规则，最终保存 Raw 拷贝。
  - `failed`：该动作处理失败，需要看 JSON report 的 error。
- `composite_score_improvement_percent`
  - 正数越大越好。
  - accepted 一般应至少大于 5。
- `accepted_or_rollback`
  - 方便论文表格直接筛选。
- `best_candidate_rejected_reason`
  - rollback 动作的主要拒绝原因。

论文中建议报告：

- accepted 动作数量
- rollback 动作数量
- composite score 平均改善
- ground penetration、foot sliding、jerk 等核心指标改善
- rollback 的 failure case 分析

## 11. 常见问题

### 评估很慢

MuJoCo forward 会对每帧、每个 candidate 运行。正式实验默认 `--max_candidates 80` 比较稳妥；调试时可临时降低：

```bash
MAX_CANDIDATES=10 bash scripts/mjlab_tools/run_batch_gmr_optimisation.sh
```

### 没有 candidate 被接受

这是正常结果，不代表代码失败。说明该动作在当前保守规则下无法安全改善。最终 pkl 会 rollback 到 Raw GMR 拷贝，report 中会记录原因。

### foot body 无法识别

检查 XML 中 foot/ankle/toe/sole 命名。如果命名不包含这些关键词，评估器会 warning，并且 foot sliding 指标可能为 0 或不可靠。

### joint limit violation 无法对应

检查 pkl 的 qpos 维度是否与 XML 的 `model.nq` 一致。Unitree G1 当前标准应为：

```text
qpos = root free joint 7 + 29 dof = 36
```

### pkl 转 csv 失败

先用 `inspect_gmr_pkl.py` 确认 optimised pkl 是否包含 `qpos`，且 shape 是否为 `[T, 36]`。

## 12. 后续送入 mjlab RL tracking

完成：

```bash
bash scripts/mjlab_tools/run_batch_optimised_pkl_to_csv.sh
```

之后使用：

```text
/mnt/d/GMR_WORK/GMR/outputs/final results/mjlab csv optimised
```

中的 csv 作为 mjlab tracking 输入。论文中建议保持 Raw GMR 和 Optimised GMR 两组 tracking 实验路径独立，避免覆盖结果。

