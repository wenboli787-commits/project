# PD Tracking 与 RL Tracking 调参训练说明

本文档用于回答两个核心问题：

```text
1. 做 PD tracking 仿真时，需要调节 PD 参数吗？
2. 做 RL tracking 时，应该怎样开始训练、怎样评估、怎样逐步扩大训练？
```

本文档默认你的工程路径为：

```bash
cd /mnt/d/GMR_WORK/GMR
```

如果你是在 Windows 中查看文件，工程路径对应为：

```text
D:\GMR_WORK\GMR
```

## 1. 先说结论

需要调 PD 参数。

PD tracking 的 `kp/kd` 不是随便给一个值就永远正确。不同动作速度、不同 root 轨迹、不同脚底接触、不同机器人模型，都会影响 PD tracking 是否稳定。

RL tracking 也不是跳过 PD。当前代码里的 RL 是 residual RL tracking：

```text
GMR reference motion
        |
        v
reference joint target
        |
        + policy residual action
        |
        v
PD torque controller
        |
        v
MuJoCo physics
```

也就是说，RL policy 学的是“在参考动作附近做补偿”，底层仍然依赖 PD controller。

所以正确流程是：

```text
1. 先检查 pkl 和 robot XML 是否匹配。
2. 先跑 kinematic PD，确认关节顺序和参考动作没错。
3. 调一组比较稳定的 PD 参数。
4. 用这组 PD 参数跑 free PD，观察是否能短时间稳定。
5. 用同一组 PD 参数跑 RL zero-action baseline。
6. 再开始 PPO 小训练。
7. 最后扩大训练步数和动作长度。
```

## 2. PD Tracking 是什么

PD tracking 使用 MuJoCo 做动力学仿真，不是直接播放 `qpos`。

控制律是：

```text
torque = kp * (q_ref - q) + kd * (dq_ref - dq)
```

其中：

```text
q_ref   参考关节角，来自 GMR pkl
q       当前 MuJoCo 仿真中的关节角
dq_ref  参考关节速度，由参考关节角差分得到
dq      当前 MuJoCo 仿真中的关节速度
kp      位置增益
kd      速度阻尼
```

`kp` 越大，机器人越努力贴近参考关节角，但也更容易抖动、撞力矩上限、导致接触不稳定。

`kd` 越大，阻尼越强，动作更稳，但太大时会让动作变钝，甚至拖慢跟踪。

## 3. Kinematic PD 和 Free PD 的区别

当前 PD tracking 支持两个模式：

```text
--root_mode kinematic
--root_mode free
```

### 3.1 kinematic 模式

`kinematic` 模式会把 root 位置和姿态固定到参考轨迹。

它适合做第一步检查：

```text
关节顺序是否正确
pkl 和 XML 是否匹配
PD 控制器是否能跟踪关节
动作数据是否大体正常
```

如果 kinematic 模式都不正常，不要开始 RL。

### 3.2 free 模式

`free` 模式下 root 不再被强制固定，机器人完全由 MuJoCo 动力学、接触和 PD torque 驱动。

它更接近真实仿真，但也更难。

如果 free 模式下机器人漂移、摔倒或高度下降，常见原因是：

```text
GMR 重定向动作没有动力学平衡约束
脚底接触状态和 root 轨迹不一致
动作太快
PD 力矩不够
kp/kd 不合适
初始姿态不稳定
```

所以 free 模式不稳定，不一定说明代码错。它更多说明这条重定向动作还没有动力学可行性。

## 4. PD 参数是否需要调

需要。

建议你把 PD 参数调成“稳定 baseline”，而不是只追求视觉上完全贴合。

判断 PD 参数是否合适，不要只看一个指标，要同时看：

```text
actuated_dof_rmse_mean
root_pos_error_mean
root_height_error_mean
torque_saturation_fraction_mean
target_joint_limit_clip_fraction_mean
ctrl_abs_max_max
```

### 4.1 指标含义

`actuated_dof_rmse_mean`

```text
受控关节角误差。
越小表示关节越贴近参考动作。
```

`root_pos_error_mean`

```text
root 位置误差。
kinematic 模式下应该接近 0。
free 模式下通常会变大。
```

`root_height_error_mean`

```text
root 高度误差。
如果高度误差快速增大，通常说明机器人在下沉、摔倒或弹飞。
```

`torque_saturation_fraction_mean`

```text
力矩饱和比例。
如果长期大于 0.5，说明很多电机经常撞力矩上限。
这时通常不适合直接训练 RL。
```

`target_joint_limit_clip_fraction_mean`

```text
目标关节角被关节限位裁剪的比例。
如果明显大于 0，说明参考动作或 RL residual 超出了机器人关节范围。
```

## 5. 推荐 PD 调参流程

第一步，先跑诊断：

```bash
cd /mnt/d/GMR_WORK/GMR
tracking/.venv_tracking/bin/python tracking/scripts/diagnose_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --max_frames 120 \
  --kp 20 \
  --kd 2
```

如果输出中看到：

```text
kinematic_pd root_pos_error_mean 接近 0
target_joint_limit_clip_fraction_mean 接近 0
torque_saturation_fraction_mean 不太高
```

说明这组参数可以作为第一组 baseline。

第二步，跑 kinematic PD：

```bash
tracking/.venv_tracking/bin/python tracking/scripts/run_pd_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --max_frames 300 \
  --root_mode kinematic \
  --kp 20 \
  --kd 2
```

第三步，跑 free PD：

```bash
tracking/.venv_tracking/bin/python tracking/scripts/run_pd_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --max_frames 300 \
  --root_mode free \
  --kp 20 \
  --kd 2
```

## 6. PD 参数怎么调

推荐从低增益开始。

### 6.1 第一组：保守稳定

```bash
tracking/.venv_tracking/bin/python tracking/scripts/diagnose_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --max_frames 120 \
  --kp 20 \
  --kd 2
```

适合：

```text
第一次测试
dance 动作
free 模式容易摔倒
力矩饱和较高
准备作为 RL baseline
```

### 6.2 第二组：中等跟踪

```bash
tracking/.venv_tracking/bin/python tracking/scripts/diagnose_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --max_frames 120 \
  --kp 30 \
  --kd 3
```

适合：

```text
第一组太软
关节误差偏大
力矩饱和还能接受
```

### 6.3 第三组：增加阻尼

```bash
tracking/.venv_tracking/bin/python tracking/scripts/diagnose_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --max_frames 120 \
  --kp 30 \
  --kd 5 \
  --max_torque 80
```

适合：

```text
动作抖动明显
需要增加阻尼
想限制最大 torque
```

不要一开始就用很大的 `kp`。高 `kp` 可能让 kinematic 下看起来更贴参考，但 free 模式会更容易接触不稳定。

## 7. 什么时候可以开始 RL

满足下面条件后，再开始 RL：

```text
diagnose_tracking.py 可以正常跑完。
kinematic_pd 没有明显错误。
target_joint_limit_clip_fraction_mean 接近 0。
free_pd 虽然可能漂移，但没有数值发散。
torque_saturation_fraction_mean 不要长期过高。
```

注意：RL 不是用来修复所有错误的。如果 PD baseline 已经完全不合理，RL 训练通常会更乱。

## 8. RL Tracking 是什么

当前 RL tracking 是 PPO residual tracking。

policy 输出：

```text
action in [-1, 1]
```

代码会把它转换成：

```text
action_offset = action_scale * action
```

再加到参考关节角上：

```text
target_dof = reference_dof + action_offset
```

最后仍然交给 PD controller 产生 torque。

所以 RL 学的是：

```text
在 GMR 参考动作附近，如何微调关节目标，让机器人在 MuJoCo 动力学里更稳定。
```

## 9. RL 训练前先装依赖

在 Ubuntu 22.04 里执行：

```bash
cd /mnt/d/GMR_WORK/GMR
WITH_RL=1 TORCH_DEVICE=cpu bash tracking/scripts/setup_tracking_ubuntu22_04.sh
```

如果你有 NVIDIA GPU，并且确认 CUDA 版本适配，可以使用：

```bash
WITH_RL=1 TORCH_DEVICE=cu121 bash tracking/scripts/setup_tracking_ubuntu22_04.sh
```

安装后检查：

```bash
tracking/.venv_tracking/bin/python tracking/scripts/check_tracking_env.py
```

你需要看到：

```text
gymnasium: OK
stable_baselines3: OK
torch: OK
```

## 10. RL 第一步：zero-action baseline

训练前先跑不带 policy 的 baseline。

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

这一步等价于：

```text
policy action = 0
target_dof = reference_dof
```

作用是给 RL 一个对照组。后面训练出来的 policy，必须至少比 zero-action baseline 更好，才说明训练有意义。

## 11. RL 第二步：微型训练 smoke test

先跑极小训练，确认训练管线可以启动、可以保存模型。

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
  --kp 20 \
  --kd 2 \
  --action_scale 0.10 \
  --save_path outputs/rl_tracking/smoke_test_ppo.zip
```

这一步只验证流程，不代表训练出好 policy。

如果这一步失败，先解决依赖和路径问题，不要直接跑长训练。

## 12. RL 第三步：小规模训练

确认 smoke test 通过后，跑 20k timesteps：

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

训练结束后评估：

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

评估时必须保持：

```text
root_mode 一致
kp 一致
kd 一致
action_scale 一致
motion 文件一致
```

否则你无法判断 policy 是否真的有效。

## 13. RL 第四步：扩大训练

20k 只是小规模测试。如果 policy 有改善，可以扩大到 100k：

```bash
tracking/.venv_tracking/bin/python tracking/scripts/train_rl_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --root_mode free \
  --max_frames 500 \
  --total_timesteps 100000 \
  --n_envs 1 \
  --n_steps 1024 \
  --batch_size 256 \
  --kp 20 \
  --kd 2 \
  --action_scale 0.10 \
  --tensorboard_log outputs/rl_tracking/tb \
  --save_path outputs/rl_tracking/dance1_subject2_unitree_g1_ppo_100k.zip
```

如果 100k 有明显改善，再扩大到 1M：

```bash
tracking/.venv_tracking/bin/python tracking/scripts/train_rl_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --root_mode free \
  --max_frames 1000 \
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

## 14. RL 训练时重点看什么

训练时不要只看 reward。

评估结果里重点看：

```text
reward_mean
actuated_dof_rmse_mean
root_pos_error_mean
root_height_error_mean
torque_saturation_fraction_mean
target_joint_limit_clip_fraction_mean
```

理想情况是：

```text
reward_mean 上升
root_pos_error_mean 下降
root_height_error_mean 下降
actuated_dof_rmse_mean 不明显变差
torque_saturation_fraction_mean 不明显上升
target_joint_limit_clip_fraction_mean 接近 0
```

如果 reward 上升，但 root 更容易摔倒，说明 reward 设计或 action_scale 需要调整。

## 15. action_scale 怎么选

`action_scale` 控制 policy 可以偏离参考动作多少。

推荐：

```text
0.10  保守，第一次训练推荐
0.20  中等，baseline 稳定后尝试
0.25  默认值，适合较好的 PD baseline
0.40  偏大，容易抖动或撞关节限位
```

如果你看到：

```text
target_joint_limit_clip_fraction_mean > 0
```

说明 residual 可能太大，应降低 `action_scale`。

## 16. 常见问题

### 16.1 PD kinematic 正常，但 free 不正常

这是最常见情况。

含义：

```text
动作在运动学上可以播放。
但在动力学上，接触、质心和平衡不一定成立。
```

处理：

```text
先接受 free 会漂移。
用短片段训练 RL。
降低 kp。
使用较小 action_scale。
尽量先选择慢动作或走路动作。
```

### 16.2 RL 训练后更差

可能原因：

```text
训练步数太少
action_scale 太大
PD baseline 不稳定
reward 还没有学到稳定策略
free 模式动作本身太难
```

处理：

```text
先评估 zero-action baseline。
把 action_scale 降到 0.10。
缩短 max_frames 到 300 或 500。
先训练 20k，再训练 100k。
确认评估参数和训练参数完全一致。
```

### 16.3 policy 保存了，但评估报错

检查：

```text
--policy_path 是否正确
是否使用 WITH_RL=1 安装了 stable_baselines3
训练和评估是否使用同一个 venv
```

### 16.4 什么时候需要重新调 PD

下面情况需要重新调：

```text
换了 motion pkl
换了 robot
换了 XML
换了 root_mode
free 模式明显摔倒
torque_saturation_fraction_mean 长期过高
RL 怎么训练都没有改善
```

## 17. 推荐总流程

最推荐你按下面顺序做：

```bash
cd /mnt/d/GMR_WORK/GMR

WITH_RL=1 TORCH_DEVICE=cpu bash tracking/scripts/setup_tracking_ubuntu22_04.sh

tracking/.venv_tracking/bin/python tracking/scripts/check_tracking_env.py

tracking/.venv_tracking/bin/python tracking/scripts/diagnose_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --max_frames 120 \
  --kp 20 \
  --kd 2

tracking/.venv_tracking/bin/python tracking/scripts/run_pd_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --max_frames 300 \
  --root_mode kinematic \
  --kp 20 \
  --kd 2

tracking/.venv_tracking/bin/python tracking/scripts/run_pd_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --max_frames 300 \
  --root_mode free \
  --kp 20 \
  --kd 2

tracking/.venv_tracking/bin/python tracking/scripts/eval_rl_tracking.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/dance1_subject2_unitree_g1.pkl \
  --max_frames 300 \
  --root_mode free \
  --kp 20 \
  --kd 2 \
  --action_scale 0.10

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

## 18. 最重要的一句话

PD 参数要调，但不要为了视觉贴合盲目调高 `kp`。

先找一组稳定、不过度饱和的 PD baseline，再用 RL residual 去学习动力学补偿。这样训练出来的 policy 才更有可能在 MuJoCo free-root 仿真里稳定。
