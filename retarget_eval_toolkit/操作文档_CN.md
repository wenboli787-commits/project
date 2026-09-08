# retarget_eval_toolkit 操作文档

## 1. 项目位置

代码已经创建在：

```text
D:\GMR_WORK\retarget_eval_toolkit
```

主入口：

```text
D:\GMR_WORK\retarget_eval_toolkit\eval_retargeting.py
```

默认配置：

```text
D:\GMR_WORK\retarget_eval_toolkit\configs\eval_config.yaml
```

## 2. 项目能评估什么

输入：

- 原始动作：`.bvh`、`.npz`、`.npy`
- 重定向结果：`.pkl`
- 可选 MuJoCo XML：用于从 `qpos` 计算机器人关键点、读取 joint limit、检查静态自碰撞

输出六大类指标：

- Motion Similarity：MPJPE、末端误差、root 轨迹、姿态误差、轨迹形状
- Kinematic Feasibility：关节限位、速度、加速度、关节范围使用率
- Physical Feasibility：torque/control/action 或 qvel/qacc proxy
- Contact Quality：脚穿地、脚滑、接触时序、离地高度
- Stability and Balance：root 高度、身体倾斜、COM 可用项、完成率/跌倒判断
- Smoothness and Simulation Performance：joint/keypoint jerk、异常跳变、自碰撞、播放 FPS 可用项

## 3. 安装环境

推荐在 Ubuntu 22.04 / WSL / Conda 中运行：

```bash
cd /mnt/d/GMR_WORK/retarget_eval_toolkit
conda create -n retarget_eval python=3.10 -y
conda activate retarget_eval
pip install -r requirements.txt
```

如果你希望通过 MuJoCo XML 从 PKL 的 `root_pos/root_rot/dof_pos` 计算机器人关键点：

```bash
pip install mujoco
```

如果你希望从 AMASS/SMPL-X NPZ 直接计算完整人体关键点：

```bash
pip install smplx torch
```

同时需要把 SMPL-X body model 路径写入 `configs/eval_config.yaml` 的：

```yaml
smplx_body_model_path: "/path/to/body_models"
```

如果不提供 SMPL-X 模型，程序不会假装计算人体全身关键点，而是把缺失关键点指标写成 `NaN/not_available`。

## 4. 直接运行评估

默认配置已经指向：

```text
original_motion_root = D:/GMR_WORK/final use mode
gmr pkl_root          = D:/GMR_WORK/GMR/outputs/final product/pkl
robot XML            = D:/GMR_WORK/GMR/assets/unitree_g1/g1_mocap_29dof.xml
```

运行：

```bash
cd /mnt/d/GMR_WORK/retarget_eval_toolkit
conda activate retarget_eval
python eval_retargeting.py --config configs/eval_config.yaml
```

运行结束终端会显示：

```text
Evaluation finished.
Matched motions: X
Missing files: Y
Best method by overall score: XXX
Report saved to: outputs/report/RETARGETING_QUALITY_REPORT.md
```

## 5. 推荐的完整运行命令

当你已经生成 Direct Mapping、Basic IK、GMR 三种方法的 final-use PKL 后，推荐这样运行：

```bash
cd /mnt/d/GMR_WORK/retarget_eval_toolkit
conda activate retarget_eval

python eval_retargeting.py \
  --original_root "/mnt/d/GMR_WORK/final use mode" \
  --direct_pkl_root "/mnt/d/GMR_WORK/GMR/outputs/direct_mapping_final/pkl" \
  --ik_pkl_root "/mnt/d/GMR_WORK/GMR/outputs/basic_ik_final/pkl" \
  --gmr_pkl_root "/mnt/d/GMR_WORK/GMR/outputs/final product/pkl" \
  --robot_xml "/mnt/d/GMR_WORK/GMR/assets/unitree_g1/g1_mocap_29dof.xml" \
  --output_dir "/mnt/d/GMR_WORK/retarget_eval_toolkit/outputs/final_eval"
```

## 6. 先生成 Direct Mapping / Basic IK final-use PKL

你现在点名的两个方法脚本在：

```text
D:\GMR_WORK\GMR\direct mapping
D:\GMR_WORK\GMR\Basic IK retargeting
```

如果要为 `final use mode` 中的动作生成对应 PKL，可在 GMR 工程目录运行类似命令：

```bash
cd /mnt/d/GMR_WORK/GMR
conda activate gmr

python "direct mapping/run_direct_mapping.py" \
  --motion_file "/mnt/d/GMR_WORK/final use mode/08_01_poses.npz" \
  --motion_format auto \
  --robot unitree_g1 \
  --no_visualize \
  --save_path "/mnt/d/GMR_WORK/GMR/outputs/direct_mapping_final/pkl/08_01_unitree_g1_direct_mapping.pkl"
```

Basic IK：

```bash
python "Basic IK retargeting/run_basic_ik_retargeting.py" \
  --motion_file "/mnt/d/GMR_WORK/final use mode/08_01_poses.npz" \
  --motion_format auto \
  --robot unitree_g1 \
  --no_visualize \
  --save_path "/mnt/d/GMR_WORK/GMR/outputs/basic_ik_final/pkl/08_01_unitree_g1_basic_ik.pkl"
```

对其他动作把 `08_01_poses.npz` 和输出文件名换成对应编号即可。

## 7. 文件名匹配规则

程序会自动模糊匹配，例如：

```text
08_01_poses.npz
08_01_walk_easy_unitree_g1.pkl
08_01_unitree_g1_direct_mapping.pkl
08_01_unitree_g1_basic_ik.pkl
```

都会归一化为同一动作编号 `08_01`。如果匹配不到，会写入：

```text
outputs/csv/missing_files.csv
```

不会让程序崩溃。

## 8. 输出怎么看

主要看：

```text
outputs/report/RETARGETING_QUALITY_REPORT.md
outputs/csv/quality_per_method.csv
outputs/csv/quality_per_motion.csv
outputs/csv/frame_metrics_all.csv
outputs/csv/missing_files.csv
```

`quality_per_method.csv`：每种方法的平均结果和综合分。

`quality_per_motion.csv`：每个动作、每种方法的详细指标。

`frame_metrics_all.csv`：逐帧曲线数据。

`missing_files.csv`：哪些动作缺少 Direct/Basic/GMR PKL。

## 9. 当前工作区数据状态

我已确认：

- `D:\GMR_WORK\final use mode` 里有 10 个原始 `.npz` 动作。
- 这些 `.npz` 是 AMASS/SMPL-style 参数文件，包含 `trans`、`poses`、`mocap_framerate`、`betas` 等字段。
- `D:\GMR_WORK\GMR\outputs\final product\pkl` 里已有部分 GMR final PKL。
- Direct Mapping / Basic IK 目前默认批量输出目录主要是 `walk1_subject1_*`，和 final-use 动作编号不一致；要完整比较三种方法，需要先按第 6 节生成 final-use Direct/Basic PKL。

## 10. 安全说明

`.pkl` 文件由 Python pickle 读取，只应加载你自己生成、可信任的本地 PKL。不要加载来源不明的 PKL。

