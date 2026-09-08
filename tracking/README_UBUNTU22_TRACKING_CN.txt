# Ubuntu 22.04 下的 GMR PD Tracking 与 RL Tracking 操作手册

本文档只面向 **Ubuntu 22.04**。当前 tracking 文件夹已经按 Ubuntu 仿真流程重新整理。

## 0. 软件栈

本手册默认你在 Ubuntu 22.04 上使用：

```text
OS: Ubuntu 22.04
Python: python3.10
仿真: MuJoCo Python package
PD tracking: numpy + mujoco
RL tracking: gymnasium + stable-baselines3 + PyTorch
训练算法: PPO
输入数据: GMR 已经重定向生成的 *.pkl
```

tracking 代码不重新做 BVH/SMPL-X 重定向。它只读取 GMR 已生成的 pkl，然后做动力学 PD 跟踪或 RL residual 跟踪。

## 1. tracking 文件夹结构

所有新增文件都在：

```bash
GMR/tracking
```

结构：

```text
tracking/
  README_UBUNTU22_TRACKING_CN.md
  README_UBUNTU22_TRACKING_CN.txt
  requirements-pd.txt
  requirements-rl.txt
  requirements-tracking.txt
  .gitignore
  gmr_tracking/
    motion.py
    mujoco_pd.py
    quaternion.py
    paths.py
    rl_env.py
  scripts/
    setup_tracking_ubuntu22_04.sh
    smoke_test_ubuntu.sh
    check_tracking_env.py
    diagnose_tracking.py
    run_pd_tracking.py
    eval_rl_tracking.py
    train_rl_tracking.py
```

主要入口：

```text
setup_tracking_ubuntu22_04.sh  创建 Ubuntu venv 并安装依赖
check_tracking_env.py          检查 Python 包、机器人 XML、pkl 和 PD smoke test
diagnose_tracking.py           检查 pkl/XML 是否匹配，并短跑 kinematic/free PD
run_pd_tracking.py             运行 MuJoCo torque PD tracking
eval_rl_tracking.py            评估 zero-action baseline 或训练好的 policy
train_rl_tracking.py           训练 PPO residual policy
smoke_test_ubuntu.sh           一键跑环境检查、PD、RL eval、PPO 微型训练
```

## 2. 仓库位置

你的 GMR 文件在 Windows 下的位置是：

```text
D:\GMR_WORK\GMR
```

如果你是在 WSL/Ubuntu 22.04 中访问这个 Windows 盘，Ubuntu 下对应路径通常是：

```bash
/mnt/d/GMR_WORK/GMR
```

本文档后续命令统一使用 Ubuntu/WSL 路径：

```bash
cd /mnt/d/GMR_WORK/GMR
```

如果你不是 WSL，而是纯 Ubuntu 双系统或虚拟机，请先把 `D:\GMR_WORK\GMR` 这份工程复制或挂载到 Ubuntu 中，然后把文档里的 `/mnt/d/GMR_WORK/GMR` 替换为你的真实 Linux 路径。

## 3. Ubuntu 系统依赖

第一次在 Ubuntu 22.04 上配置时，建议先装系统依赖：

```bash
sudo apt-get update
sudo apt-get install -y \
  python3.10 \
  python3.10-venv \
  python3-pip \
  build-essential \
  git \
  ffmpeg \
  libgl1-mesa-glx \
  libglfw3 \
  libosmesa6 \
  libegl1 \
  mesa-utils
```

这些依赖用于：

```text
python3.10-venv   创建虚拟环境
build-essential   某些 Python 包需要编译时使用
ffmpeg            后续录制视频或处理视频时使用
libglfw3          MuJoCo viewer 桌面显示
libegl1           服务器/headless EGL 渲染
libosmesa6        EGL 不可用时的 headless 备选
mesa-utils        检查 OpenGL/EGL
```

也可以让安装脚本自动执行 apt 安装：

```bash
INSTALL_APT_DEPS=1 bash tracking/scripts/setup_tracking_ubuntu22_04.sh
```

## 4. 创建 tracking 虚拟环境

### 4.1 只安装 PD tracking 环境

如果你只想先跑 PD tracking：

```bash
cd /mnt/d/GMR_WORK/GMR
bash tracking/scripts/setup_tracking_ubuntu22_04.sh
```

默认会创建：

```bash
tracking/.venv_tracking
```

这个脚本默认也会安装 `scripts/vis_robot_motion.py` 所需的轻量 viewer 依赖，例如 `scipy`、`rich`、`tqdm`、`imageio`、`loop_rate_limiters`。

如果你只想安装最小 PD 依赖，不安装 viewer 依赖：

```bash
INSTALL_VIEWER_DEPS=0 bash tracking/scripts/setup_tracking_ubuntu22_04.sh
```

### 4.2 安装 PD + RL tracking 环境

如果你要训练 RL policy：

```bash
cd /mnt/d/GMR_WORK/GMR
WITH_RL=1 bash tracking/scripts/setup_tracking_ubuntu22_04.sh
```

默认安装 CPU 版 PyTorch。

### 4.3 CUDA 版 PyTorch

如果你的 Ubuntu 机器有 NVIDIA GPU，并且 CUDA/驱动已经配置好，可以指定 PyTorch wheel：

```bash
WITH_RL=1 TORCH_DEVICE=cu121 bash tracking/scripts/setup_tracking_ubuntu22_04.sh
```

可选：

```text
TORCH_DEVICE=cpu
TORCH_DEVICE=cu118
TORCH_DEVICE=cu121
TORCH_DEVICE=cu124
```

如果你已经提前装好了 PyTorch，不想让脚本安装：

```bash
WITH_RL=1 INSTALL_TORCH=0 bash tracking/scripts/setup_tracking_ubuntu22_04.sh
```

### 4.4 激活环境

```bash
source tracking/.venv_tracking/bin/activate
```

不激活也可以，直接用：

```bash
tracking/.venv_tracking/bin/python tracking/scripts/check_tracking_env.py
```

## 5. MuJoCo 渲染环境变量

Ubuntu 桌面环境，有显示器或 X11：

```bash
export MUJOCO_GL=glfw
```

Ubuntu 服务器/headless：

```bash
export MUJOCO_GL=egl
```

如果 EGL 不可用，再尝试：

```bash
export MUJOCO_GL=osmesa
```

无界面 PD/RL 指标计算通常不需要设置 `MUJOCO_GL`。只有使用 `--render` 或 viewer 时才需要重点关注。

## 6. 检查环境

运行：

```bash
cd /mnt/d/GMR_WORK/GMR
tracking/.venv_tracking/bin/python tracking/scripts/check_tracking_env.py
```

理想输出包含：

```text
[env] numpy: OK
[env] mujoco: OK
[env] gymnasium: OK
[env] stable_baselines3: OK
[env] torch: OK
[env] pd_smoke_test: OK
```

如果你只安装了 PD 环境，没有 `WITH_RL=1`，那么下面几项可能是 MISSING，这是正常的：

```text
gymnasium
stable_baselines3
torch
```

但 PD tracking 必须至少满足：

```text
numpy: OK
mujoco: OK
pd_smoke_test: OK
```

## 7. 一键 smoke test

如果你已经安装了 RL 依赖：

```bash
cd /mnt/d/GMR_WORK/GMR
bash tracking/scripts/smoke_test_ubuntu.sh
```

这会依次运行：

```text
1. check_tracking_env.py
2. diagnose_tracking.py，20 帧 kinematic/free PD 诊断
3. run_pd_tracking.py，5 帧 kinematic PD
4. eval_rl_tracking.py，5 帧 zero-action RL eval
5. train_rl_tracking.py，32 timesteps PPO 微型训练
```

如果你的默认 motion 文件不是：

```text
outputs/dance1_subject2_unitree_g1.pkl
```

可以指定：

```bash
MOTION_PATH=outputs/your_motion.pkl ROBOT=unitree_g1 bash tracking/scripts/smoke_test_ubuntu.sh
```

## 7.1 先用诊断脚本判断 tracking 是否“正确”

在正式跑长仿真之前，强烈建议先运行：

```bash
cd /mnt/d/GMR_WORK/GMR
tracking/.venv_tracking/bin/python tracking/scripts/diagnose_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --max_frames 120
```

这个脚本会做四件事：

```text
1. 检查 motion pkl 是否存在。
2. 检查 pkl 的 qpos_dim 是否等于 MuJoCo 模型 nq。
3. 打印 actuator 名称和 joint 名称，确认控制顺序。
4. 分别短跑 kinematic PD 和 free PD，并输出诊断建议。
```

你应该重点看这些字段：

```text
model_nq/model_nv/model_nu
motion_qpos_dim/dof_count
actuated_dof_count
tracking_sim_dt
steps_per_frame
actuated_dof_rmse_mean
root_pos_error_mean
torque_saturation_fraction_mean
target_joint_limit_clip_fraction_mean
```

判断标准：

```text
motion_qpos_dim 必须等于 model_nq。
unitree_g1 通常应为 model_nq=36, dof_count=29, actuated_dof_count=29。

kinematic_pd 的 root_pos_error_mean 应接近 0。
如果 kinematic_pd 的 actuated_dof_rmse_mean 很大，先不要训练 RL。

free_pd 的 root_pos_error_mean 会比 kinematic 大，这是正常的。
如果 free_pd 很快漂移或摔倒，说明这条重定向轨迹还没有动力学稳定性。

torque_saturation_fraction_mean 如果长期大于 0.5，说明 PD 经常撞力矩上限。
这时先调 PD 参数，不要急着训练 RL。

target_joint_limit_clip_fraction_mean 如果大于 0，说明参考动作或 RL residual 正在被关节限位裁剪。
裁剪少量可以接受；如果比例很高，说明动作超出机器人关节范围。
```

一个比较健康的排查顺序是：

```text
diagnose_tracking.py
  -> kinematic_pd 可接受
  -> free_pd 看 root 漂移和力矩饱和
  -> eval_rl_tracking.py zero-action baseline
  -> train_rl_tracking.py 小步数 smoke test
  -> 长时间 RL 训练
```

## 7.2 针对当前 `dance1_subject2_unitree_g1.pkl` 的审查结论

我已经用当前仓库里的 `outputs/dance1_subject2_unitree_g1.pkl` 做过短诊断。关键结果是：

```text
robot: unitree_g1
xml: assets/unitree_g1/g1_mocap_29dof.xml
motion_fps: 30
model_nq/model_nv/model_nu: 36/35/29
motion_qpos_dim/dof_count: 36/29
actuated_dof_count: 29
steps_per_frame: 17
tracking_sim_dt: 0.001961
target_joint_limit_clip_fraction_mean: 0
```

这说明：

```text
1. pkl 和 unitree_g1 MuJoCo XML 在维度上是匹配的。
2. 29 个 motor 和 29 个 motion dof 能对应上。
3. 目标关节角没有明显超出机器人关节限位。
4. timestep 已经自动对齐到动作 30 FPS，不会因为 0.002 秒 XML timestep 产生累计时间漂移。
```

但同一次诊断也显示：

```text
kinematic_pd actuated_dof_rmse_mean 偏高。
free_pd root_pos_error_mean 明显增大。
torque_saturation_fraction_mean 接近或超过 0.5。
```

这个结果的含义不是“代码路径错了”，而是：

```text
当前 dance 动作对 free-root 动力学 tracking 比较难。
PD 控制器经常撞力矩上限。
free 模式下 root 会因为接触、质心和平衡不匹配而漂移。
```

所以当前最稳妥的顺序是：

```text
1. 用 kinematic 确认关节顺序和动作本身没有错。
2. 用较低 kp/kd 降低力矩饱和。
3. 再跑 free，接受它一开始可能会漂移。
4. 只有当 PD baseline 能稳定跑完短片段后，再训练 RL residual。
```

对这条动作，不建议一开始就用高增益追求视觉上贴合。高增益可能让短时间关节误差变小，但会让力矩饱和、抖动和 free-root 失稳更严重。

## 8. 输入数据要求

tracking 读取 GMR 生成的 pkl，例如：

```text
outputs/dance1_subject2_unitree_g1.pkl
```

pkl 必须包含：

```text
fps
root_pos
root_rot
dof_pos
```

对 `unitree_g1`，典型形状：

```text
root_pos: (T, 3)
root_rot: (T, 4)
dof_pos : (T, 29)
qpos    : (T, 36)
```

注意：

```text
GMR pkl 中 root_rot 是 xyzw。
tracking 内部会自动转成 MuJoCo qpos 需要的 wxyz。
```

## 9. 先确认 pkl 能正常运动学回放

这一步使用 GMR 原始 viewer，不是 PD tracking：

```bash
cd /mnt/d/GMR_WORK/GMR
tracking/.venv_tracking/bin/python scripts/vis_robot_motion.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl
```

如果这一步失败，先不要做 PD/RL tracking。先检查：

```text
pkl 是否存在
--robot 是否和 pkl 对应
MuJoCo viewer 是否能打开
```

如果你看到这个错误：

```text
ModuleNotFoundError: No module named 'general_motion_retargeting'
```

原因通常是：你用 `tracking/.venv_tracking` 运行了 GMR 原始脚本，但 Python 没有把仓库根目录加入模块搜索路径。

当前代码已经对 `scripts/vis_robot_motion.py` 做了修复，会自动加入仓库根目录。更新代码后重新运行：

```bash
cd /mnt/d/GMR_WORK/GMR
tracking/.venv_tracking/bin/python scripts/vis_robot_motion.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl
```

如果仍然报缺少 `scipy`、`rich`、`loop_rate_limiters`、`imageio` 或 `tqdm`，安装 viewer 依赖：

```bash
tracking/.venv_tracking/bin/python -m pip install -r tracking/requirements-viewer.txt
```

不要用下面这种方式运行 viewer，除非你确定系统默认 `python` 就是已经装好依赖的 GMR 环境：

```bash
python scripts/vis_robot_motion.py
```

## 10. PD Tracking 原理

PD tracking 是在 MuJoCo 中做动力学仿真，而不是直接设置 `qpos`。

控制律：

```text
torque = kp * (q_ref - q) + kd * (dq_ref - dq)
```

输出指标：

```text
dof_rmse
actuated_dof_rmse
root_pos_error
root_quat_error_rad
root_height
ctrl_abs_mean
ctrl_abs_max
torque_saturation_fraction
```

默认输出目录：

```text
outputs/pd_tracking/
```

默认文件名会包含 `root_mode/kp/kd`，例如：

```text
dance1_subject2_unitree_g1_unitree_g1_kinematic_kp20_kd2_pd_summary.json
dance1_subject2_unitree_g1_unitree_g1_free_kp20_kd2_pd_summary.json
```

这样你连续跑 kinematic 和 free，或者连续试不同 kp/kd 时，不会把上一组结果覆盖掉。如果你想指定自己的输出文件，可以使用：

```bash
--metrics_path outputs/pd_tracking/my_metrics.csv
--summary_path outputs/pd_tracking/my_summary.json
```

## 11. PD Tracking：最小测试

```bash
cd /mnt/d/GMR_WORK/GMR
tracking/.venv_tracking/bin/python tracking/scripts/run_pd_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --max_frames 5 \
  --root_mode kinematic \
  --print_every 1
```

如果能看到类似：

```text
[pd_tracking] summary: dof_rmse_mean=...
```

说明 PD tracking 跑通。

注意：当前 PD 控制器默认会让每个 motion frame 的仿真总时间严格等于 `1/fps`。例如 30 FPS 动作、Unitree G1 XML 原始 timestep 为 0.002 秒时，程序会自动使用 17 个小步，并把每步调整为约 0.001961 秒，避免长时间 tracking 时产生时间漂移。

如果你想严格保留 XML 里的 timestep，可以加：

```bash
--no_match_motion_dt
```

## 12. root_mode 选择

### 12.1 kinematic

```bash
tracking/.venv_tracking/bin/python tracking/scripts/run_pd_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --max_frames 300 \
  --root_mode kinematic \
  --print_every 30
```

含义：

```text
每一帧把 floating base 固定到参考 root_pos/root_quat。
```

用途：

```text
检查 pkl 和 robot 是否匹配
检查关节顺序
检查 actuator 映射
检查 PD 参数
```

限制：

```text
不是完整动力学可行性测试，因为 root 被外部固定。
```

### 12.2 free

```bash
tracking/.venv_tracking/bin/python tracking/scripts/run_pd_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --max_frames 300 \
  --root_mode free \
  --print_every 30
```

含义：

```text
只在 reset 设置初始 root，之后 floating base 完全交给 MuJoCo 动力学。
```

用途：

```text
检查机器人是否会摔倒、漂移、打滑
检查动作是否真的动力学可跟踪
```

建议顺序：

```text
先跑 kinematic。
kinematic 正常后再跑 free。
```

## 13. 带 viewer 的 PD Tracking

桌面 Ubuntu：

```bash
export MUJOCO_GL=glfw

tracking/.venv_tracking/bin/python tracking/scripts/run_pd_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --max_frames 300 \
  --root_mode free \
  --render \
  --rate_limit
```

服务器/headless 不建议开 viewer。先做无界面指标评估。

## 14. PD 参数调节

默认：

```text
kp = 80
kd = 4
control_limit_mode = auto
```

示例：

```bash
tracking/.venv_tracking/bin/python tracking/scripts/run_pd_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --root_mode free \
  --kp 120 \
  --kd 6 \
  --max_torque 120 \
  --max_frames 500
```

参数解释：

```text
--kp
  位置增益。越大越贴参考，但更容易抖动或力矩饱和。

--kd
  速度阻尼。越大越稳，但太大动作会发钝。

--max_torque
  人工覆盖 actuator 力矩上限，只建议调试使用。

--control_limit_mode auto
  如果 XML motor ctrlrange 像 [-1, 1]，自动使用 joint actuator force range。

--control_limit_mode model
  严格使用 XML motor ctrlrange。

--control_limit_mode joint
  强制使用 joint actuator force range。

--control_limit_mode none
  不裁剪力矩，只用于排查问题。
```

优先看这些指标：

```text
actuated_dof_rmse
root_pos_error
torque_saturation_fraction
root_height
```

### 14.1 Unitree G1 的推荐调参顺序

如果你看到 `torque_saturation_fraction_mean` 很高，例如 0.5 以上，不要马上认为代码错了。对舞蹈、快速转身这类动作，G1 的 PD tracking 很容易撞力矩上限。

建议这样试：

第一组，保守低增益，先看力矩是否明显下降：

```bash
tracking/.venv_tracking/bin/python tracking/scripts/diagnose_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --max_frames 120 \
  --kp 20 \
  --kd 2
```

第二组，中等增益，观察关节误差和力矩饱和的折中：

```bash
tracking/.venv_tracking/bin/python tracking/scripts/diagnose_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --max_frames 120 \
  --kp 30 \
  --kd 3
```

第三组，增加阻尼，尝试减小 free-root 抖动：

```bash
tracking/.venv_tracking/bin/python tracking/scripts/diagnose_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --max_frames 120 \
  --kp 30 \
  --kd 5 \
  --max_torque 80
```

看结果时不要只追求 `actuated_dof_rmse_mean` 最小，还要同时看：

```text
torque_saturation_fraction_mean 是否下降
free_pd 的 root_pos_error_mean 是否可接受
root_height 是否没有快速塌掉
target_joint_limit_clip_fraction_mean 是否接近 0
```

如果第一组 `kp=20,kd=2` 的 kinematic 误差可以接受，并且力矩饱和明显低于高增益组，就优先使用第一组作为后续 RL 的 baseline。RL residual 更适合在稳定、不过度饱和的 PD baseline 上学习。

### 14.2 kinematic 正常但 free 不正常怎么办

这是最常见的情况。它说明：

```text
动作在运动学上可回放。
但在动力学上，脚底接触、质心、root 速度和平衡不一定成立。
```

处理顺序：

```text
1. 换走路、慢跑、站立动作先测试，不要先用舞蹈或跳跃。
2. 降低 kp，增加 kd，减少抖动。
3. 截短动作，只测前 120-300 帧。
4. 看 torque_saturation_fraction 是否长期过高。
5. 确认 PD baseline 后，再训练 RL residual policy。
```

## 15. RL Tracking 原理

RL tracking 学的是 residual，不是从零生成动作：

```text
policy action in [-1, 1]
        |
        v
target_dof = reference_dof + action_scale * action
        |
        v
PD torque controller
        |
        v
MuJoCo physics
```

这样做的意义：

```text
GMR 提供动作先验。
PD 提供底层跟踪。
RL 学习动力学、接触和平衡补偿。
```

重要：RL tracking 不是用来替代 PD 的第一步。RL 的输入是 PD tracking 环境，如果 PD 的 kinematic 阶段已经明显不对，RL 会在错误环境上学习，结果通常更乱。

推荐开始 RL 前至少满足：

```text
diagnose_tracking.py 可以正常完成。
kinematic_pd 的 actuated_dof_rmse_mean 不要离谱。
target_joint_limit_clip_fraction_mean 接近 0。
free_pd 虽然可能漂移，但不要一开始就数值发散。
```

## 16. RL Zero-action Baseline

先跑不带 policy 的 baseline：

```bash
tracking/.venv_tracking/bin/python tracking/scripts/eval_rl_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --max_frames 300 \
  --root_mode free \
  --kp 20 \
  --kd 2 \
  --action_scale 0.10
```

这等价于：

```text
action = 0
target_dof = reference_dof
```

输出目录：

```text
outputs/rl_tracking/
```

默认 RL eval 文件名会包含 `root_mode/kp/kd/action_scale/policy_tag`，例如：

```text
dance1_subject2_unitree_g1_unitree_g1_free_kp20_kd2_as0p1_zero_action_eval_summary.json
```

这样你用不同 PD 参数或不同 residual 幅度做 baseline 时，不会互相覆盖。

## 17. PPO 训练 smoke test

先跑极小训练，确认流程能保存模型：

```bash
tracking/.venv_tracking/bin/python tracking/scripts/train_rl_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --root_mode kinematic \
  --max_frames 10 \
  --total_timesteps 32 \
  --n_envs 1 \
  --n_steps 8 \
  --batch_size 8 \
  --save_path outputs/rl_tracking/smoke_test_ppo.zip
```

注意：

```text
32 timesteps 只用于验证训练管线，不代表训练出了可用 policy。
```

## 18. 正式 PPO 训练

先从小片段开始：

```bash
tracking/.venv_tracking/bin/python tracking/scripts/train_rl_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --root_mode free \
  --max_frames 500 \
  --total_timesteps 20000 \
  --n_envs 1 \
  --n_steps 512 \
  --batch_size 128 \
  --kp 20 \
  --kd 2 \
  --action_scale 0.10 \
  --save_path outputs/rl_tracking/dance1_subject2_unitree_g1_ppo_20k_safe.zip
```

确认能训练后，再扩大：

```bash
tracking/.venv_tracking/bin/python tracking/scripts/train_rl_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --root_mode free \
  --total_timesteps 1000000 \
  --n_envs 1 \
  --n_steps 1024 \
  --batch_size 256 \
  --kp 20 \
  --kd 2 \
  --action_scale 0.10 \
  --tensorboard_log outputs/rl_tracking/tb \
  --save_path outputs/rl_tracking/dance1_subject2_unitree_g1_ppo_1m.zip
```

Ubuntu 上先用：

```text
--n_envs 1
```

单环境稳定后，再考虑多进程并行。

### 18.1 RL 训练参数怎么选

`--action_scale` 很关键。它表示 policy 可以在参考关节角附近偏移多少。

```text
action_scale=0.10   更保守，更稳，适合刚开始。
action_scale=0.25   默认值，适合已有较好 PD baseline。
action_scale=0.40   偏激进，容易学出抖动或撞限位。
```

建议第一轮训练：

```bash
tracking/.venv_tracking/bin/python tracking/scripts/train_rl_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --root_mode free \
  --max_frames 500 \
  --total_timesteps 20000 \
  --n_envs 1 \
  --n_steps 512 \
  --batch_size 128 \
  --kp 20 \
  --kd 2 \
  --action_scale 0.10 \
  --save_path outputs/rl_tracking/dance1_subject2_unitree_g1_ppo_20k_safe.zip
```

如果评估时动作太保守，再提高：

```text
action_scale 0.10 -> 0.20 -> 0.25
```

不建议一开始就用很大的 action residual。

### 18.2 RL 评估要和训练参数一致

评估时的 `kp/kd/action_scale/root_mode` 应尽量和训练时一致。例如训练用了 `kp=20,kd=2,action_scale=0.10`，评估也这样写：

```bash
tracking/.venv_tracking/bin/python tracking/scripts/eval_rl_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --policy_path outputs/rl_tracking/dance1_subject2_unitree_g1_ppo_20k_safe.zip \
  --root_mode free \
  --max_frames 500 \
  --kp 20 \
  --kd 2 \
  --action_scale 0.10
```

如果训练和评估的 PD 参数不同，policy 看到的动力学环境也不同，评估结果会不稳定。

## 19. 评估训练好的 policy

```bash
tracking/.venv_tracking/bin/python tracking/scripts/eval_rl_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --policy_path outputs/rl_tracking/dance1_subject2_unitree_g1_ppo_20k.zip \
  --root_mode free \
  --max_frames 500
```

桌面 viewer：

```bash
export MUJOCO_GL=glfw

tracking/.venv_tracking/bin/python tracking/scripts/eval_rl_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --policy_path outputs/rl_tracking/dance1_subject2_unitree_g1_ppo_20k.zip \
  --root_mode free \
  --max_frames 500 \
  --render
```

## 20. TensorBoard

如果训练时指定：

```text
--tensorboard_log outputs/rl_tracking/tb
```

启动：

```bash
tracking/.venv_tracking/bin/tensorboard --logdir outputs/rl_tracking/tb --host 0.0.0.0 --port 6006
```

本机浏览器打开：

```text
http://127.0.0.1:6006
```

如果是服务器，使用 SSH 端口转发：

```bash
ssh -L 6006:127.0.0.1:6006 user@server_ip
```

## 21. 换动作

只换 `--robot_motion_path`：

```bash
tracking/.venv_tracking/bin/python tracking/scripts/run_pd_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/walk1_subject1_unitree_g1.pkl \
  --max_frames 300 \
  --root_mode free
```

如果 pkl 不是 `unitree_g1` 生成的，必须同步修改 `--robot`。

## 22. 换机器人

前提：

```text
GMR 已经为该机器人生成对应 pkl。
general_motion_retargeting/params.py 里注册了机器人 XML。
pkl 的 dof 数和机器人 XML 的 nq 必须匹配。
```

示例：

```bash
tracking/.venv_tracking/bin/python tracking/scripts/run_pd_tracking.py \
  --robot booster_t1_29dof \
  --robot_motion_path outputs/your_motion_booster_t1_29dof.pkl \
  --max_frames 300 \
  --root_mode kinematic
```

## 23. 常见问题

### 23.1 `python3.10: command not found`

安装：

```bash
sudo apt-get update
sudo apt-get install -y python3.10 python3.10-venv python3-pip
```

或指定你的 Python：

```bash
PYTHON_BIN=python3 bash tracking/scripts/setup_tracking_ubuntu22_04.sh
```

### 23.2 `gymnasium: MISSING` 或 `stable_baselines3: MISSING`

你只装了 PD 环境。安装 RL 依赖：

```bash
WITH_RL=1 bash tracking/scripts/setup_tracking_ubuntu22_04.sh
```

### 23.3 viewer 打不开

桌面：

```bash
export MUJOCO_GL=glfw
```

服务器：

```bash
export MUJOCO_GL=egl
```

如果仍失败，先跑无界面指标，不加 `--render`。

### 23.4 `Model nq does not match motion qpos_dim`

原因：

```text
--robot 和 --robot_motion_path 不匹配。
```

例如用 `unitree_g1` 去读 `booster_t1_29dof` 的 pkl 就会报错。

### 23.5 free 模式马上摔倒

常见原因：

```text
重定向轨迹没有动力学平衡约束。
脚底接触状态和 root 轨迹不一致。
动作太快，PD 力矩不够。
初始姿态不稳定。
```

建议：

```text
1. 先跑 kinematic。
2. 换走路类动作。
3. 用 --max_frames 300 截短。
4. 调 kp/kd。
5. 再进入 RL training。
```

### 23.6 力矩饱和比例很高

看：

```text
torque_saturation_fraction
```

处理顺序：

```text
1. 降低 kp。
2. 适当提高 kd。
3. 确认 control_limit_mode=auto。
4. 最后再尝试 max_torque。
```

## 24. 推荐执行顺序

第一次完整实验建议：

```text
1. bash tracking/scripts/setup_tracking_ubuntu22_04.sh
2. WITH_RL=1 bash tracking/scripts/setup_tracking_ubuntu22_04.sh
3. tracking/.venv_tracking/bin/python tracking/scripts/check_tracking_env.py
4. tracking/.venv_tracking/bin/python tracking/scripts/diagnose_tracking.py --max_frames 120 ...
5. tracking/.venv_tracking/bin/python tracking/scripts/run_pd_tracking.py --root_mode kinematic --max_frames 300 ...
6. tracking/.venv_tracking/bin/python tracking/scripts/run_pd_tracking.py --root_mode free --max_frames 300 ...
7. tracking/.venv_tracking/bin/python tracking/scripts/eval_rl_tracking.py，不带 policy，得到 zero-action baseline
8. tracking/.venv_tracking/bin/python tracking/scripts/train_rl_tracking.py --total_timesteps 32，确认训练管线
9. tracking/.venv_tracking/bin/python tracking/scripts/train_rl_tracking.py --total_timesteps 20000，小规模训练
10. tracking/.venv_tracking/bin/python tracking/scripts/eval_rl_tracking.py --policy_path ...，评估 policy
```

## 25. 最短可用命令

安装完整 PD + RL 环境：

```bash
cd /mnt/d/GMR_WORK/GMR
WITH_RL=1 TORCH_DEVICE=cpu bash tracking/scripts/setup_tracking_ubuntu22_04.sh
```

检查：

```bash
tracking/.venv_tracking/bin/python tracking/scripts/check_tracking_env.py
```

诊断：

```bash
tracking/.venv_tracking/bin/python tracking/scripts/diagnose_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --max_frames 120
```

跑 PD：

```bash
tracking/.venv_tracking/bin/python tracking/scripts/run_pd_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --max_frames 300 \
  --root_mode kinematic \
  --kp 20 \
  --kd 2
```

kinematic 能正常跑完后，再跑 free：

```bash
tracking/.venv_tracking/bin/python tracking/scripts/run_pd_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --max_frames 300 \
  --root_mode free \
  --kp 20 \
  --kd 2
```

跑 RL zero-action baseline：

```bash
tracking/.venv_tracking/bin/python tracking/scripts/eval_rl_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --max_frames 300 \
  --root_mode free \
  --kp 20 \
  --kd 2 \
  --action_scale 0.10
```

跑 RL 小训练：

```bash
tracking/.venv_tracking/bin/python tracking/scripts/train_rl_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --root_mode free \
  --max_frames 500 \
  --total_timesteps 20000 \
  --n_envs 1 \
  --n_steps 512 \
  --batch_size 128 \
  --kp 20 \
  --kd 2 \
  --action_scale 0.10 \
  --save_path outputs/rl_tracking/dance1_subject2_unitree_g1_ppo_20k_safe.zip
```
