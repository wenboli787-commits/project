# mjlab RL Tracking 操作手册：从 GMR/IK/Direct Mapping 参考动作到 RL Tracking

本文档面向当前工作区：

```text
D:\GMR_WORK
/mnt/d/GMR_WORK
```

目标链路是：

```text
GMR / Basic IK / Direct Mapping 生成的 kinematic reference PKL
-> 转成 mjlab 需要的 Unitree G1 motion CSV
-> 用 mjlab csv_to_npz 转成 motion.npz 并上传 WandB registry
-> 用 Mjlab-Tracking-Flat-Unitree-G1 训练 RL tracking policy
-> play / 保存视频
-> 和 PD tracking 结果做对比
```

当前已经调试通过的核心路线是 `08_05_gmr`：

```text
GMR PKL -> 08_05_gmr.csv -> WandB motions/08_05_gmr -> train 512 envs / 2000 iterations -> play
```

## 0. 关键原则

### 0.1 不要直接拿 `.pkl` 训练

mjlab tracking 任务不能直接读取 GMR / IK / direct mapping 的 `.pkl`。它需要先转成 CSV：

```text
每一帧一行，共 36 列：
root_x, root_y, root_z,
root_quat_x, root_quat_y, root_quat_z, root_quat_w,
29 个 Unitree G1 关节角
```

也就是：

```text
base position + base quaternion(xyzw) + joint angles
```

注意：MuJoCo `qpos` 通常是：

```text
root_pos(3) + root_quat(wxyz) + joint_qpos(29)
```

而 mjlab CSV 要求 quaternion 是 `xyzw`，所以从 MuJoCo/GMR `qpos` 转 CSV 时必须把 `wxyz` 改成 `xyzw`。

### 0.2 RL tracking 的 reference 不建议用 PD tracking 后的 PKL

推荐用这些 kinematic retargeting 结果做 reference：

```text
GMR pkl
Basic IK pkl
Direct mapping pkl
```

不建议用 PD tracking 后的 `.pkl` 做 RL reference，因为 PD tracking 结果已经混入了摔倒、滞后、抖动、脚滑、穿地等控制误差。拿它训练 RL，相当于让 RL 学这些错误。

正确区分：

```text
GMR / IK / Direct Mapping: 解决动作重定向质量
PD / RL Tracking: 解决控制器能否稳定跟踪参考动作
```

## 1. 当前工作区文件状态

原始人体动作：

```text
D:\GMR_WORK\final use mode
```

GMR final PKL：

```text
D:\GMR_WORK\GMR\outputs\final product\pkl
```

当前已有 9 个 GMR PKL：

```text
08_01_unitree_g1_gmr.pkl
08_04_unitree_g1_gmr.pkl
08_05_unitree_g1_gmr.pkl
09_01_unitree_g1_gmr.pkl
09_12_unitree_g1_gmr.pkl
10_01_unitree_g1_gmr.pkl
13_01_unitree_g1_gmr.pkl
13_11_unitree_g1_gmr.pkl
13_17_unitree_g1_gmr.pkl
```

mjlab CSV 输出目录：

```text
D:\GMR_WORK\GMR\outputs\final product\mjlab csv
```

当前已生成 9 个 GMR CSV：

```text
08_01_gmr.csv   shape=(68, 36)
08_04_gmr.csv   shape=(120, 36)
08_05_gmr.csv   shape=(73, 36)
09_01_gmr.csv   shape=(36, 36)
09_12_gmr.csv   shape=(478, 36)
10_01_gmr.csv   shape=(199, 36)
13_01_gmr.csv   shape=(577, 36)
13_11_gmr.csv   shape=(102, 36)
13_17_gmr.csv   shape=(1209, 36)
```

Basic IK 和 Direct Mapping 也可按同样方式转换，只要 PKL 里有 `qpos`，或有 `root_pos/root_quat/dof_pos`。

常见目录：

```text
D:\GMR_WORK\GMR\outputs\final product\pkl Basic IK
D:\GMR_WORK\GMR\outputs\final product\pkl direct
```

## 2. 安装和检查 mjlab

推荐训练环境：

```text
Linux / WSL Ubuntu + NVIDIA GPU
Python >= 3.10
CUDA 可用
uv
Weights & Biases 账号
```

进入 mjlab：

```bash
cd /mnt/d/GMR_WORK/mjlab
```

如果第一次配置：

```bash
uv sync
```

如果需要 CUDA 12.8 extra：

```bash
uv sync --extra cu128
```

验证：

```bash
uv run demo
uv run list-envs | grep Tracking
```

应能看到：

```text
Mjlab-Tracking-Flat-Unitree-G1
Mjlab-Tracking-Flat-Unitree-G1-No-State-Estimation
```

## 3. WandB 登录和 registry

mjlab motion imitation 使用 Weights & Biases registry 保存和加载 reference motion。

登录：

```bash
cd /mnt/d/GMR_WORK/mjlab
uv run wandb login
```

在 WandB 页面创建 registry：

```text
Registry name: motions
Artifact type: All Types
```

你的调试示例使用 entity：

```text
wenboli787
```

训练时 registry name 示例：

```text
wenboli787/motions/08_05_gmr
```

如果 WandB 页面复制出的路径略有差异，以 WandB registry 页面为准。

## 4. PKL 转 mjlab CSV

项目里已经有转换脚本，不需要重新创建：

```text
D:\GMR_WORK\GMR\scripts\mjlab_tools\pkl_to_mjlab_csv.py
```

脚本逻辑：

1. 优先读取 `qpos` / `robot_qpos` / `motion_qpos` / `q`。
2. 从 qpos 取 `root_pos = qpos[:, 0:3]`。
3. 从 qpos 取 `root_quat_wxyz = qpos[:, 3:7]`。
4. 转成 mjlab CSV 所需 `root_quat_xyzw = [x, y, z, w]`。
5. 取 `joint_pos = qpos[:, 7:36]`。
6. 保存 `[root_pos, root_quat_xyzw, joint_pos]`，共 36 列。

如果没有 qpos，则尝试读取：

```text
root_pos / root_quat / dof_pos
```

### 4.1 单个 GMR 动作转换

```bash
cd /mnt/d/GMR_WORK/GMR
conda activate gmr

mkdir -p "outputs/final product/mjlab csv"

python scripts/mjlab_tools/pkl_to_mjlab_csv.py \
  --input_pkl "outputs/final product/pkl/08_05_unitree_g1_gmr.pkl" \
  --output_csv "outputs/final product/mjlab csv/08_05_gmr.csv"
```

成功时应看到：

```text
CSV shape: (帧数, 36)
```

### 4.2 批量转换 GMR 动作

```bash
cd /mnt/d/GMR_WORK/GMR
mkdir -p "outputs/final product/mjlab csv"

for pkl in "outputs/final product/pkl"/*_unitree_g1_gmr.pkl; do
  stem=$(basename "$pkl" _unitree_g1_gmr.pkl)
  python scripts/mjlab_tools/pkl_to_mjlab_csv.py \
    --input_pkl "$pkl" \
    --output_csv "outputs/final product/mjlab csv/${stem}_gmr.csv"
done
```

### 4.3 转 Basic IK / Direct Mapping

按同样方法，只是目录和后缀改掉。示例：

```bash
cd /mnt/d/GMR_WORK/GMR
mkdir -p "outputs/final product/mjlab csv"

python scripts/mjlab_tools/pkl_to_mjlab_csv.py \
  --input_pkl "outputs/final product/pkl Basic IK/08_05_poses_unitree_g1_basic_ik_no_gmr_seed.pkl" \
  --output_csv "outputs/final product/mjlab csv/08_05_basic_ik.csv"

python scripts/mjlab_tools/pkl_to_mjlab_csv.py \
  --input_pkl "outputs/final product/pkl direct/08_05_unitree_g1_direct_mapping.pkl" \
  --output_csv "outputs/final product/mjlab csv/08_05_direct.csv"
```

实际文件名以目录里真实文件名为准。

### 4.4 检查 CSV

```bash
python -c "import numpy as np; x=np.loadtxt('/mnt/d/GMR_WORK/GMR/outputs/final product/mjlab csv/08_05_gmr.csv', delimiter=','); print(x.shape); print(x[:2])"
```

期望：

```text
(帧数, 36)
```

如果是 35 列、37 列，或者 quaternion 顺序不是 `xyzw`，不要进入下一步。

## 5. CSV 转 mjlab motion NPZ 并上传 WandB

进入 mjlab：

```bash
cd /mnt/d/GMR_WORK/mjlab
```

转换并上传：

```bash
MUJOCO_GL=egl uv run -m mjlab.scripts.csv_to_npz \
  --input-file "/mnt/d/GMR_WORK/GMR/outputs/final product/mjlab csv/08_05_gmr.csv" \
  --output-name "08_05_gmr" \
  --input-fps 30 \
  --output-fps 50 \
  --render True
```

说明：

- `--input-fps 30`：当前 GMR final PKL 按 30 FPS 使用。
- `--output-fps 50`：mjlab tracking 默认策略步长是 0.02 s，即 50 Hz。
- `--render True`：会生成并上传动作视频，方便检查 reference 是否正常。
- `--output-name` 是 WandB artifact 名，不是本地输出文件名。

成功后 WandB registry 里会出现：

```text
wenboli787/motions/08_05_gmr
```

或者：

```text
motions/08_05_gmr
```

以 WandB 页面复制的完整路径为准。

### 5.1 批量上传 CSV

批量时建议先关掉 render：

```bash
cd /mnt/d/GMR_WORK/mjlab

for csv in "/mnt/d/GMR_WORK/GMR/outputs/final product/mjlab csv"/*_gmr.csv; do
  name=$(basename "$csv" .csv)
  MUJOCO_GL=egl uv run -m mjlab.scripts.csv_to_npz \
    --input-file "$csv" \
    --output-name "$name" \
    --input-fps 30 \
    --output-fps 50 \
    --render False
done
```

### 5.2 为什么必须用 mjlab 自己的 converter

`csv_to_npz` 会在 mjlab/MuJoCo 里播放动作，计算每个 body 的 FK，并保存：

```text
fps
joint_pos
joint_vel
body_pos_w
body_quat_w
body_lin_vel_w
body_ang_vel_w
```

不要用其他框架生成的 NPZ 代替。不同物理引擎 body ordering 不同，body index 错了会导致 tracking target 对错 body，训练不收敛。

## 6. 训练 RL tracking policy

不要一上来就 4096 envs。你已经调试通过的建议起步命令是：

```bash
cd /mnt/d/GMR_WORK/mjlab

uv run train Mjlab-Tracking-Flat-Unitree-G1 \
  --registry-name wenboli787/motions/08_05_gmr \
  --env.scene.num-envs 512 \
  --agent.max-iterations 2000 \
  --video True
```

如果显存够，再逐步提高：

```bash
--env.scene.num-envs 1024
--env.scene.num-envs 2048
--env.scene.num-envs 4096
```

训练输出目录：

```text
/mnt/d/GMR_WORK/mjlab/logs/rsl_rl/g1_tracking/时间戳/
D:\GMR_WORK\mjlab\logs\rsl_rl\g1_tracking\时间戳\
```

里面通常有：

```text
model_*.pt
params/env.yaml
params/agent.yaml
videos/train/
<run_dir_name>.onnx
```

### 6.1 更短烟测

只确认链路是否能跑通：

```bash
cd /mnt/d/GMR_WORK/mjlab

uv run train Mjlab-Tracking-Flat-Unitree-G1 \
  --registry-name wenboli787/motions/08_05_gmr \
  --env.scene.num-envs 128 \
  --agent.max-iterations 100 \
  --agent.save-interval 50 \
  --agent.run-name smoke_08_05_gmr
```

### 6.2 正式训练模板

```bash
cd /mnt/d/GMR_WORK/mjlab

uv run train Mjlab-Tracking-Flat-Unitree-G1 \
  --registry-name wenboli787/motions/08_05_gmr \
  --env.scene.num-envs 4096 \
  --agent.run-name 08_05_gmr
```

如果显存不够，优先降低 `--env.scene.num-envs`。

### 6.3 批量训练多个动作

```bash
cd /mnt/d/GMR_WORK/mjlab

for name in 08_01_gmr 08_04_gmr 08_05_gmr 09_01_gmr 09_12_gmr 10_01_gmr 13_01_gmr 13_11_gmr 13_17_gmr; do
  uv run train Mjlab-Tracking-Flat-Unitree-G1 \
    --registry-name "wenboli787/motions/${name}" \
    --env.scene.num-envs 512 \
    --agent.max-iterations 2000 \
    --agent.run-name "$name" \
    --video True
done
```

注意：当前 mjlab 的 `MotionCommand` 默认一次只吃一个 motion artifact。不要把多个 CSV 简单拼成一个长 CSV，因为动作切换处会有跳变，污染 reference。

## 7. 播放训练好的 policy

### 7.1 从 WandB run 播放

训练完成后，在 WandB 里找到 run path：

```text
wenboli787/mjlab/你的run-id
```

播放：

```bash
cd /mnt/d/GMR_WORK/mjlab

uv run play Mjlab-Tracking-Flat-Unitree-G1 \
  --wandb-run-path wenboli787/mjlab/你的run-id \
  --viewer native
```

也可以用浏览器 viewer：

```bash
uv run play Mjlab-Tracking-Flat-Unitree-G1 \
  --wandb-run-path wenboli787/mjlab/你的run-id \
  --viewer viser
```

说明：如果训练 run 正确记录了 motion artifact，`play --wandb-run-path` 会从该 run 使用过的 motion artifact 自动解析 reference motion。

### 7.2 从本地 checkpoint 播放

当前仓库的 `play.py` 在本地 checkpoint 模式下需要同时给 `--motion-file`，因为没有 WandB run 时它不能自动知道 reference motion。推荐先用 WandB run 播放；如果要本地 checkpoint 播放，先保存一个本地 motion NPZ。

本地 motion NPZ 可以从 `/tmp/motion.npz` 复制，或者从 WandB artifact cache 找到后复制到稳定路径：

```text
/mnt/d/GMR_WORK/mjlab/motions/08_05_gmr.npz
```

播放命令：

```bash
cd /mnt/d/GMR_WORK/mjlab

uv run play Mjlab-Tracking-Flat-Unitree-G1 \
  --checkpoint-file logs/rsl_rl/g1_tracking/你的时间戳/model_2000.pt \
  --motion-file "/mnt/d/GMR_WORK/mjlab/motions/08_05_gmr.npz" \
  --viewer native
```

如果你的调试分支已经改过 `play.py`，支持本地 checkpoint 直接用 `--registry-name`，也可以用：

```bash
uv run play Mjlab-Tracking-Flat-Unitree-G1 \
  --checkpoint-file logs/rsl_rl/g1_tracking/你的时间戳/model_2000.pt \
  --registry-name wenboli787/motions/08_05_gmr \
  --viewer native
```

但以当前仓库代码为准，原版更稳的是 `--motion-file`。

### 7.3 保存播放视频

从 WandB run 保存：

```bash
uv run play Mjlab-Tracking-Flat-Unitree-G1 \
  --wandb-run-path wenboli787/mjlab/你的run-id \
  --video True \
  --video-length 500
```

从本地 checkpoint 保存：

```bash
uv run play Mjlab-Tracking-Flat-Unitree-G1 \
  --checkpoint-file logs/rsl_rl/g1_tracking/你的时间戳/model_2000.pt \
  --motion-file "/mnt/d/GMR_WORK/mjlab/motions/08_05_gmr.npz" \
  --video True \
  --video-length 500
```

## 8. 论文实验推荐对比方式

建议分两层，不要把 retargeting 和 tracking 控制混成一个结论。

### 8.1 第一层：Retargeting Reference 对比

比较：

```text
Direct Mapping PKL
Basic IK PKL
GMR PKL
```

关注指标：

```text
root 误差
body 位置误差
脚滑
穿地
关节突变
平滑度
自碰撞
```

这一层回答：哪种 retargeting 方法产生的参考动作质量更好。

### 8.2 第二层：Tracking Controller 对比

对同一个 reference，例如：

```text
08_05_gmr.pkl
```

比较：

```text
PD tracking 结果
RL tracking 结果
```

关注指标：

```text
tracking error
fall rate / success rate
foot slip
contact 稳定性
动作平滑度
torque / action smoothness
视频主观质量
```

这一层回答：同一条参考动作下，PD 控制器和 RL 策略哪个更能稳定跟踪。

推荐写法：

```text
GMR / IK / Direct Mapping 解决的是动作重定向质量；
PD / RL Tracking 解决的是控制器能不能在物理仿真中稳定跟踪该参考动作。
```

## 9. 最小可执行路线

先只跑 `08_05_gmr`，不要一开始全部动作一起跑：

```bash
# 1. pkl -> csv
cd /mnt/d/GMR_WORK/GMR
conda activate gmr

python scripts/mjlab_tools/pkl_to_mjlab_csv.py \
  --input_pkl "outputs/final product/pkl/08_05_unitree_g1_gmr.pkl" \
  --output_csv "outputs/final product/mjlab csv/08_05_gmr.csv"

# 2. csv -> mjlab motion registry
cd /mnt/d/GMR_WORK/mjlab

MUJOCO_GL=egl uv run -m mjlab.scripts.csv_to_npz \
  --input-file "/mnt/d/GMR_WORK/GMR/outputs/final product/mjlab csv/08_05_gmr.csv" \
  --output-name "08_05_gmr" \
  --input-fps 30 \
  --output-fps 50 \
  --render True

# 3. train
uv run train Mjlab-Tracking-Flat-Unitree-G1 \
  --registry-name wenboli787/motions/08_05_gmr \
  --env.scene.num-envs 512 \
  --agent.max-iterations 2000 \
  --video True

# 4. play from WandB run
uv run play Mjlab-Tracking-Flat-Unitree-G1 \
  --wandb-run-path wenboli787/mjlab/你的run-id \
  --viewer native
```

实验推进顺序：

```text
第 1 个动作：08_05_gmr
目的：确认 pkl -> csv -> npz -> registry -> train -> play 整条链路跑通。

第 2 组动作：走路 / 转身 / 简单上肢动作
目的：验证 RL tracking 是否比 PD 更稳定。

第 3 组动作：踢腿 / 大幅弯腰 / 快速转身
目的：展示 RL tracking 的优势和失败边界。
```

## 10. 常见错误判断

| 错误现象 | 最可能原因 | 解决方法 |
| --- | --- | --- |
| CSV 转换后机器人姿态很怪 | quaternion 顺序错了 | 检查是否从 `wxyz` 正确转成 `xyzw` |
| 训练不收敛 | CSV 关节顺序和 mjlab G1 不一致 | 确认 `.pkl` 的 29 个 joint 顺序和 mjlab G1 顺序一致 |
| 一开始就摔倒 | root 高度太低、参考动作穿地 | 转 CSV 前给 root z 加 offset，例如 `+0.03` 到 `+0.08` |
| 显存爆了 | `num-envs` 太大 | 从 256 / 512 开始 |
| W&B 找不到 motion | registry 路径写错 | 到 WandB registry 页面复制完整路径 |
| viewer 打不开 | WSL/远程显示问题 | 用 `--viewer viser` 或 `--video True` |
| 训练中 NaN | 仿真状态爆炸 | 加 `--enable-nan-guard True` |

NaN guard 示例：

```bash
uv run train Mjlab-Tracking-Flat-Unitree-G1 \
  --registry-name wenboli787/motions/08_05_gmr \
  --env.scene.num-envs 512 \
  --agent.max-iterations 2000 \
  --enable-nan-guard True
```

## 11. 参考链接

- [mjlab Motion Imitation](https://mujocolab.github.io/mjlab/main/source/training/motion_imitation.html)
- [mjlab Installation Guide](https://mujocolab.github.io/mjlab/main/source/installation.html)
- [mjlab GitHub](https://github.com/mujocolab/mjlab)
- [mjlab Training with RSL-RL](https://mujocolab.github.io/mjlab/main/source/training/rsl_rl.html)
- [mjlab Viewers](https://mujocolab.github.io/mjlab/main/source/viewers.html)
- [mjlab FAQ](https://mujocolab.github.io/mjlab/main/source/faq.html)

最关键的一句话：

```text
现在不是直接“把 GMR 放进 mjlab 跑”，而是先把 GMR/IK/Direct Mapping 的机器人参考轨迹整理成 mjlab 的 Unitree G1 motion CSV，然后让 RL policy 学会在物理仿真中稳定跟踪这条轨迹。
```
