# 人类动作重定向评估工具：完整操作手册

## 1. 这个工具解决什么问题

本文件夹用于**评估已经生成的重定向结果**，而不是再次执行 Direct Mapping、Basic IK 或 GMR。它会把人类参考动作和三种机器人输出先读取为同一个 `CanonicalMotion` 数据结构，再计算一致的指标，因此不会把指标代码绑死在 MuJoCo 或 Isaac 上。

```text
BVH / AMASS / SMPL / HumanML3D / npy / npz / pkl / csv
                         │
                         ▼
                loaders + adapter
                         │
                         ▼
                 CanonicalMotion
                         │
                         ▼
             simulator-agnostic metrics
                         │
                         ▼
CSV + JSON + Markdown report + PNG plots
```

三个候选方法固定显示为：`Direct Mapping`、`Basic IK`、`GMR / Constrained IK`。它们的文件格式可以不同，只要每一个能被读取为本手册第 5 节的字段即可。

## 2. 目录说明

```text
GMR/evaluate/
├── evaluate_retargeting.py       # 命令行主入口
├── canonical_motion.py           # 统一数据格式与验证
├── loaders.py                    # npy/npz/pkl/csv/bvh 读取器
├── metrics.py                    # 通用动作、质量、可执行性指标
├── contact_metrics.py            # 接触、脚滑、穿透
├── plotting.py                   # matplotlib 图表
├── report.py                     # Markdown 报告
├── utils.py                      # 对齐、归一化、JSON 等公共函数
├── simulator_adapters/
│   ├── offline_adapter.py        # 不依赖仿真器的文件
│   ├── isaac_adapter.py          # Isaac Sim/Lab 离线导出日志
│   └── mujoco_adapter.py         # MJCF + qpos 的 FK/limits/effort
├── config/eval_mapping_template.yaml
├── examples/
│   ├── create_dummy_data.py
│   └── run_dummy_evaluation.py
├── requirements.txt
└── README.md
```

`metrics.py` 和 `contact_metrics.py` 不会调用 MuJoCo 或 Isaac API。新的仿真器、日志格式或 FK 实现应当放入 `simulator_adapters/`，这样现有指标无需重写。

## 3. 安装

### Ubuntu（推荐环境）

```bash
cd ~/GMR/evaluate  # 改成服务器上的实际项目路径，例如 /home/<用户名>/GMR/evaluate
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

基础依赖为 `numpy`、`pandas`、`matplotlib`、`PyYAML`。只有 MuJoCo 的模型 FK、关节范围读取和逆动力学 effort proxy 才需要额外安装：

```bash
python -m pip install mujoco
```

Isaac 模式读取已经导出的 `.npz/.pkl/.csv`，所以**不需要**在评估机器上安装 Isaac Sim 或 Isaac Lab。

## 4. 先跑最小示例

这一步不需要任何真实动作或机器人模型，是确认环境、CSV、报告和绘图是否正常的最快方式。

```bash
cd ~/GMR/evaluate
source .venv/bin/activate
python examples/run_dummy_evaluation.py
# 或者：bash examples/run_dummy_evaluation.sh
```

它依次执行：

1. `create_dummy_data.py` 生成 reference、Direct、Basic IK、GMR 四个 `.npz`；
2. 调用 `evaluate_retargeting.py --simulator offline`；
3. 在 `examples/dummy_evaluation_output/` 生成下列文件。

```text
summary_metrics.json
summary_metrics.csv
per_frame_metrics.csv
evaluation_report.md
warnings.txt
plots/method_comparison.png
plots/root_xy_trajectory.png
plots/per_frame_position_errors.png
```

示例刻意让 Direct Mapping 有较大噪声和一个关节越界，让 GMR 有更小误差并提供 target/actual tracking 数据。因此排序只用于验证流程，**不能解释为真实算法结论**。

## 5. CanonicalMotion 与输入文件格式

内部统一单位为米、秒、弧度，四元数统一为 **`wxyz`**。大多数 GMR/Isaac 导出文件使用 `xyzw`，默认 YAML 已配置 `input.quaternion_order: xyzw`，加载时会自动转换。若你的输入已经是 `wxyz`，必须改为：

```yaml
input:
  quaternion_order: "wxyz"
```

常用的 `.npz` 或 `.pkl` 字段如下。数组第一维总是帧 `T`。

| 字段 | 形状 | 含义 | 是否必需 |
|---|---|---|---|
| `fps` | 标量 | 帧率 | 强烈建议 |
| `root_pos` | `[T, 3]` | 根节点世界位置 | 根轨迹/稳定性/任务成功 |
| `root_quat` 或 GMR 的 `root_rot` | `[T, 4]` | 根方向 | 根姿态、heading |
| `dof_pos` | `[T, D]` | 关节角/关节位置 | limits、平滑度 |
| `dof_vel` | `[T, D]` | 关节速度 | 能量；缺失时部分指标由位置差分 |
| `body_positions` | `{body: [T,3]}` | 机器人各 body 世界位置 | 末端、接触、穿透 |
| `body_quats` | `{body: [T,4]}` | 机器人各 body 姿态 | body rotation、跌倒 |
| `foot_contacts` | `{foot: [T]}` | 布尔接触标签 | contact accuracy |
| `contact_forces` | `{foot: [T,3]}` 或 `[T]` | 足端接触力 | contact 判定 |
| `torques` / `ctrl` | `[T,D]` | 力矩/控制输入 | effort、energy |
| `torque_limits_lower`, `torque_limits_upper` | `[D]` | 可选力矩范围 | torque-limit violation |
| `target_dof_pos`, `actual_dof_pos` | `[T,D]` | 控制目标/真实执行轨迹 | tracking error |
| `target_root_pos`, `actual_root_pos` | `[T,3]` | 可选根目标/真实轨迹 | root tracking |
| `target_body_positions`, `actual_body_positions` | `{body: [T,3]}` | 可选 body 目标/真实轨迹 | body tracking |
| `joint_positions_ref` | `[T,J,3]` | 人体关键点世界位置 | reference 末端误差 |
| `joint_names_ref` | `[J]` | 对应关键点名 | reference 映射 |

字典字段可直接保存到 NPZ：

```python
np.savez(
    "robot_result.npz",
    fps=30.0,
    root_pos=root_pos,
    root_quat=root_quat_xyzw,
    dof_pos=dof_pos,
    body_positions={"pelvis": pelvis_xyz, "left_foot": left_foot_xyz},
    foot_contacts={"left_foot": left_contact, "right_foot": right_contact},
)
```

`pickle` 可以直接保存同样结构的 `dict`。CSV 是宽表：根位置使用 `root_pos_x, root_pos_y, root_pos_z`，关节可用 `dof_pos_0, dof_pos_1, ...`；其他复杂的 named body 字典建议使用 NPZ/PKL。

### 已有 GMR 脚本输出

本工程现有的 `direct mapping/run_direct_mapping.py` 与 `Basic IK retargeting/run_basic_ik_retargeting.py` 输出 PKL 中包含：

```python
{"fps", "root_pos", "root_rot", "dof_pos", "local_body_pos", "link_body_list", "metadata"}
```

其中 `root_rot` 为 `xyzw`，已被默认配置兼容。它们没有 body 世界坐标时：

- 在 `--simulator offline` 下，关节、根轨迹、平滑度等仍可评估；末端位置、足部接触等 FK 依赖指标会显示 `unavailable`；
- 在 `--simulator mujoco --robot_model <xml>` 下，工具可以把 root + dof 重建为 MuJoCo `qpos`，运行 `mj_forward` 自动得到 `body_positions/body_quats`，从而计算更多指标。

## 6. reference 动作如何准备

### 推荐：canonical NPZ

为了可控、可复用，最推荐将 AMASS、SMPL、HumanML3D、FBX 或任意动作源先导出成：

```text
源动作
  → 人体 FK / skeleton conversion
  → joint_positions_ref [T,J,3] + joint_names_ref [J]
  → canonical_reference.npz
  → evaluate
```

不要假设人类骨架和机器人骨架完全相同。评估只比较 YAML 显式指定的 landmarks，例如人体 `left_wrist` 对机器人 `left_hand`。

### BVH

工具提供基础 BVH 读取：它会读取 hierarchy、offset、channels，做前向展开后得到关节世界坐标和 FPS。由于各 BVH 的关节名与坐标轴差异很大，必须在 YAML 的 `reference` 部分填写实际 BVH joint 名称。对于高保真旋转指标，建议用你的动作处理管线导出 canonical NPZ 中的 `joint_rotations_ref`。

### AMASS / SMPL / HumanML3D

它们通常只含参数，不一定直接含世界坐标；评估工具不会擅自下载人体模型或猜测骨架。请先用你已有的 SMPL/SMPL-X FK 导出 `joint_positions_ref`、`joint_names_ref`，必要时加上 root pose 和四元数。这样可避免因为 gender、body shape、joint regressor、坐标系不同而比较失真。

## 7. 最重要的配置：mapping YAML

先复制模板，避免直接改模板：

```bash
cp config/eval_mapping_template.yaml config/g1_my_motion.yaml
```

然后逐项替换为你的真实名称：

```yaml
robot:
  root_body: "pelvis"
  torso_body: "torso_link"
  left_hand_body: "left_wrist_roll_link"
  right_hand_body: "right_wrist_roll_link"
  left_foot_body: "left_ankle_roll_link"
  right_foot_body: "right_ankle_roll_link"

reference:
  root_joint: "Hips"
  left_hand_joint: "LeftHand"
  right_hand_joint: "RightHand"
  left_foot_joint: "LeftFoot"
  right_foot_joint: "RightFoot"
```

名称必须与数据中 `body_positions` 的 key、MuJoCo body name、Isaac `body_names` 或 reference `joint_names_ref` **逐字一致**（区分大小写）。名称填错时相应指标会是 `unavailable`，不会把错误映射为 0。

### 修改日志字段名

如果你的文件叫 `joint_angles` 而不是 `dof_pos`，只修改相应 section：

```yaml
offline:
  expected_keys:
    dof_pos: "joint_angles"
    dof_vel: "joint_speeds"
    body_positions: "link_world_pos"
```

Isaac 同理修改 `isaac.expected_keys`；MuJoCo 原始日志修改 `mujoco.expected_keys.qpos/qvel/ctrl`。字段名的可配置性是为了处理不同记录脚本，不是改变 CanonicalMotion 的名字。

### 调整阈值

`thresholds` 的单位均为米、秒、牛顿或角度：

- `ground_height`：地面 Z；场景地面不是零时必须修改；
- `foot_contact_height` 与 `foot_contact_velocity`：无力传感器时的接触估计规则；
- `fall_base_height`：根高度低于它会判为跌倒；
- `fall_torso_tilt_deg`：躯干竖直轴倾角超过它会判为跌倒；
- `min_forward_displacement`：locomotion success 最小 XY 位移。

阈值不是通用真理。应按机器人尺寸、动作类型和地面坐标进行校准；静态挥手动作尤其不应使用“前进位移”判成功。

## 8. 运行命令

在 Ubuntu 的 `~/GMR/evaluate`（或你的实际项目目录）中运行。所有路径由 `pathlib` 处理，建议在命令行中始终使用 Linux 绝对路径，例如 `/home/<用户名>/GMR/...` 或数据盘路径 `/data/...`。

### Offline（最常用）

```bash
python evaluate_retargeting.py \
  --simulator offline \
  --ref_motion /data/motions/reference_motion.npz \
  --direct_motion /data/results/direct_mapping_result.pkl \
  --ik_motion /data/results/basic_ik_result.pkl \
  --gmr_motion /data/results/gmr_result.pkl \
  --mapping config/g1_my_motion.yaml \
  --out_dir /data/results/evaluation_offline
```

### MuJoCo（建议用于现有 GMR PKL）

```bash
python evaluate_retargeting.py \
  --simulator mujoco \
  --robot_model ~/GMR/assets/unitree_g1/g1_mocap_29dof.xml \
  --ref_motion /data/motions/reference_motion.npz \
  --direct_motion /data/results/direct_mapping_result.pkl \
  --ik_motion /data/results/basic_ik_result.pkl \
  --gmr_motion /data/results/gmr_result.pkl \
  --mapping config/g1_my_motion.yaml \
  --out_dir /data/results/evaluation_mujoco
```

MuJoCo 模式会尽力完成：读取 `model.jnt_range`、识别并跳过 free joint 的 7 维 `qpos`、执行 FK 获取 body world pose；没有记录 torque 时，若 qpos/qvel 可完整重建，会尝试 `qfrc_inverse` 作为 effort proxy。若任何前提不满足，报告会写 unavailable/warning，不会伪造力矩。

### Isaac Sim / Isaac Lab 离线日志

```bash
python evaluate_retargeting.py \
  --simulator isaac \
  --robot_model /opt/isaac/projects/unitree_g1.usd \
  --ref_motion /data/motions/reference_motion.npz \
  --direct_motion /data/isaac_logs/direct_mapping_result.npz \
  --ik_motion /data/isaac_logs/basic_ik_result.npz \
  --gmr_motion /data/isaac_logs/gmr_result.npz \
  --mapping config/g1_my_motion.yaml \
  --out_dir /data/results/evaluation_isaac
```

Isaac 日志优先识别 `root_state[T,13]`（position、quaternion、linear velocity、angular velocity）、`dof_pos`、`dof_vel`、`rigid_body_state[T,B,13]`、`body_names`、`contact_forces`、`torques`、`actions`。四元数顺序依 YAML 的 `input.quaternion_order`；请确认导出脚本的真实约定。

### FPS 不一致

默认规则是裁剪到三者与 reference 的最短帧数。想按时间轴将候选动作线性重采样到 reference FPS：

```bash
python evaluate_retargeting.py ... --resample
```

或在 YAML 中设置 `temporal.resample_to_reference_fps: true`。报告的“时间对齐与归一化”段会记录是否发生重采样与裁剪。

## 9. 归一化与对齐的含义

当 `normalization.enable_scale_normalization: true` 时，工具按每帧 head-to-foot 高度的中位数，缩放 reference 到候选机器人尺寸；这避免将行走距离误当作身高。之后可选地：

1. 将 reference 的第 0 帧 root 平移到 robot 的第 0 帧 root；
2. 将 reference 的第 0 帧 heading 绕 Z 轴旋转到 robot heading；
3. 在对齐后的坐标中比较位置和速度。

这适合评价“相对动作是否像”。如果你的实验需要绝对世界坐标误差（例如任务点到达），应关闭或局部关闭：

```yaml
normalization:
  enable_scale_normalization: false
  align_root_at_first_frame: false
  align_heading_at_first_frame: false
```

## 10. 输出内容与如何解读

### `summary_metrics.json`

完整、嵌套、机器可读。包含运行输入、每种方法的时间对齐记录、warnings 和所有指标。`unavailable` 是显式字符串，方便下游程序区分“没有数据”和数值 0。

### `summary_metrics.csv`

一行一个方法，嵌套字段展平为 `root_trajectory_error.position.mean` 这类列，适合 Excel/Pandas 排序或画总览图。

### `per_frame_metrics.csv`

一行是“方法 × 帧”，包含 `end_effector_error.*`、`root_error.*`、contact mismatch、sliding speed、penetration depth、joint-limit max violation、stability 等时间序列。推荐用它定位某个峰值到底发生在哪一帧。

### 指标分组

| 目标 | 指标 |
|---|---|
| 动作相似 | 手/脚/head/root 末端位置误差、root XY/height/orientation/velocity、旋转误差（rad/deg）、关键点速度误差 |
| 接触质量 | left/right contact accuracy、precision、recall、F1、mismatch、脚滑速度/比例、地面穿透 |
| 可执行性 | 关节范围越界、torque/effort、energy proxy、根高度/躯干倾角的跌倒检测 |
| 平滑性 | DOF 与末端速度、加速度、jerk 的均值与峰值 |
| 跟踪 | target 与 actual 同时存在时的 dof position/velocity tracking error |
| 移动任务 | XY 位移、路径长度、平均速度、heading error、是否前进/跌倒/成功 |

`energy_proxy = sum(abs(torque * dof_vel)) * dt`。它用于同一机器人/同一记录定义下的相对比较，不能直接当成电池真实消耗。

## 11. 常见问题与排查顺序

### 报 `Motion file was not found`

检查输入路径是否真的存在、Bash 续行反斜杠 `\` 后是否还有多余字符、文件名是否是 `.pkl` 而不是 `.pickle`。建议先给每个参数完整加引号。

### 大量指标是 `unavailable`

先查看输出目录的 `warnings.txt`，然后按下面顺序确认：

1. `body_positions` 是否是世界坐标，而非 local pose；
2. YAML 中 body/joint 名称是否和文件 key 完全一致；
3. reference 是否有 `joint_positions_ref + joint_names_ref`；
4. 需 tracking 时是否同时有 `target_*` 和 `actual_*`；
5. 需 MuJoCo FK 时 `--robot_model` 是否正确、`mujoco` 是否安装、dof 维度是否吻合。

### 误差非常大，但可视化看来动作相似

优先检查三件事：坐标轴（Y-up/Z-up）、位置单位（mm/cm/m）、四元数顺序（xyzw/wxyz）。然后检查 YAML landmark 是否配对。也要确认是否需要开启 root/heading/scale 对齐；报告会显示每种方法最终采用的 scale。

### MuJoCo FK 被跳过

检查日志 `dof_pos` 的维度是否等于模型中除 free joint 外的 articulated qpos 维度。GMR 的 PKL 必须有 `root_pos` 和 `root_rot`；模型可能还有 ball joint 或不同关节排列，遇到这种情况应导出原始 `qpos/qvel`，或在适配器里按机器人补充转换规则。

### contact F1 低或脚滑异常

如果有真实接触力/接触标签，优先保存 `contact_forces`/`foot_contacts`。没有时工具依照“足高接近地面且足速较小”估计接触，快速踢腿、台阶、非零地面都会影响结果。请校准 `ground_height`、contact height/velocity 阈值，并确认 foot body 名称。

### `tracking_error` 是 unavailable

这是正常的：重定向输出 `dof_pos` 只是**目标轨迹**，不等于机器人仿真后的真实执行轨迹。只有在 PD/RL tracking 后保存 `target_dof_pos` 与 `actual_dof_pos`（可选速度）时，tracking error 才可计算。

## 12. 扩展与复现实验建议

1. 每个 robot/action 建立一份版本管理的 mapping YAML；不要临时改模板后忘记保存。
2. 将每次评估用的三条原始轨迹、模型版本、YAML、输出目录放在同一实验目录。
3. 对每条动作分别评估，再使用 `summary_metrics.csv` 汇总均值/中位数；不要只挑一段 walk 得出总体结论。
4. 新增指标时，在 `metrics.py` 写成独立函数，输入只使用 `CanonicalMotion`；再从 `evaluate_all_metrics()` 注册它。新仿真器只需实现 `SimulatorAdapter`。
5. 任何 unavailable 都应保留在论文/报告的附录里；缺少数据不应被替换成 0 或“通过”。

## 13. 最小复现实验清单

- [ ] 已运行 `python examples/run_dummy_evaluation.py` 并看到报告和三张 PNG；
- [ ] 已复制、命名并提交自己的 mapping YAML；
- [ ] 已确认四元数顺序、单位、世界坐标轴；
- [ ] 已用一个动作检查 `warnings.txt`；
- [ ] 已在 MuJoCo 模式检查 body names 与 FK；
- [ ] 已确认各方法输入对应同一个 reference 动作、同一帧区间；
- [ ] 已在最终比较时保留所有 `summary_metrics.json` 与原始数据版本。

## 14. 附录：PowerShell 与 Ubuntu/Bash 命令写法差异

你的仿真与评估应以 Ubuntu/Bash 命令为准；本附录仅用于从 Windows 主机迁移命令时查阅，**不要将 PowerShell 语法复制到 Ubuntu 终端**。

| 任务 | Ubuntu / Bash（应使用） | Windows PowerShell（仅作对照） |
|---|---|---|
| 进入目录 | `cd ~/GMR/evaluate` | `cd D:\GMR_WORK\GMR\evaluate` |
| 建虚拟环境 | `python3 -m venv .venv` | `python -m venv .venv` |
| 激活环境 | `source .venv/bin/activate` | `.\.venv\Scripts\Activate.ps1` |
| 复制模板 | `cp config/eval_mapping_template.yaml config/g1_my_motion.yaml` | `Copy-Item config\eval_mapping_template.yaml config\g1_my_motion.yaml` |
| 路径分隔符 | `/`，如 `/data/results/run` | `\`，如 `D:\results\run` |
| 多行续行 | 行尾 `\` | 行尾反引号 `` ` `` |
| 运行示例 | `python examples/run_dummy_evaluation.py` | `python examples\run_dummy_evaluation.py` |

同一条评估命令的关键区别如下：

```bash
# Ubuntu / Bash
python evaluate_retargeting.py \
  --simulator offline \
  --ref_motion /data/motions/reference.npz \
  --direct_motion /data/results/direct.pkl \
  --ik_motion /data/results/basic_ik.pkl \
  --gmr_motion /data/results/gmr.pkl \
  --mapping config/g1_my_motion.yaml \
  --out_dir /data/results/evaluation
```

```powershell
# Windows PowerShell：仅对照，不在 Ubuntu 中使用
python evaluate_retargeting.py `
  --simulator offline `
  --ref_motion D:\motions\reference.npz `
  --direct_motion D:\results\direct.pkl `
  --ik_motion D:\results\basic_ik.pkl `
  --gmr_motion D:\results\gmr.pkl `
  --mapping config\g1_my_motion.yaml `
  --out_dir D:\results\evaluation
```
