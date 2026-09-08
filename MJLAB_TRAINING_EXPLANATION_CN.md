# mjlab RL Tracking 训练机制解释文档

本文档解释当前项目里 mjlab 是怎样训练 Unitree G1 motion tracking policy 的。它不是操作命令手册，而是解释训练时每个模块在做什么、数据怎样流动、policy 怎样被更新。

对应任务：

```text
Mjlab-Tracking-Flat-Unitree-G1
```

核心入口：

```text
D:\GMR_WORK\mjlab\src\mjlab\scripts\train.py
D:\GMR_WORK\mjlab\src\mjlab\tasks\tracking\tracking_env_cfg.py
D:\GMR_WORK\mjlab\src\mjlab\tasks\tracking\mdp\commands.py
D:\GMR_WORK\mjlab\src\mjlab\tasks\tracking\config\g1\env_cfgs.py
D:\GMR_WORK\mjlab\src\mjlab\tasks\tracking\config\g1\rl_cfg.py
```

## 1. 一句话概括

mjlab 的 RL tracking 训练不是“直接播放 GMR 动作”，而是：

```text
给 policy 一个目标参考动作和机器人当前状态，
让 policy 每一步输出关节位置控制目标，
MuJoCo 物理仿真执行这些动作，
环境根据机器人和参考动作的误差给奖励，
PPO 反复更新 policy，
最后得到能在物理仿真中稳定跟踪参考动作的神经网络策略。
```

## 2. 训练前数据是什么

GMR / IK / Direct Mapping 生成的是机器人参考轨迹，通常是 `.pkl`：

```text
qpos = root_pos(3) + root_quat(wxyz)(4) + joint_pos(29)
```

mjlab 不能直接用这个 `.pkl` 训练。你已经把它转成了 mjlab CSV：

```text
root_pos(3) + root_quat(xyzw)(4) + joint_pos(29)
```

然后 `mjlab.scripts.csv_to_npz` 会把 CSV 转成 mjlab 真正训练读取的 `motion.npz`。这个 NPZ 里不只是关节角，还包括 mjlab 用 MuJoCo 前向运动学算出的 body 状态：

```text
fps
joint_pos
joint_vel
body_pos_w
body_quat_w
body_lin_vel_w
body_ang_vel_w
```

这些数据就是训练时的 reference motion。

## 3. `train` 命令启动后发生什么

典型训练命令：

```bash
cd /mnt/d/GMR_WORK/mjlab

uv run train Mjlab-Tracking-Flat-Unitree-G1 \
  --registry-name wenboli787/motions/08_05_gmr \
  --env.scene.num-envs 512 \
  --agent.max-iterations 2000 \
  --video True
```

`train.py` 做这些事：

1. 根据 task name 加载环境配置和 PPO 配置。
2. 如果是 tracking 任务，找到 `commands["motion"]`。
3. 从 WandB registry 下载 `motion.npz`，或读取本地 `--env.commands.motion.motion-file`。
4. 选择 GPU / CPU。
5. 创建很多并行 MuJoCo 环境，例如 512 个机器人同时训练。
6. 把环境包装成 RSL-RL 能用的 vectorized env。
7. 创建 PPO runner。
8. 循环采样、计算奖励、更新神经网络。
9. 定期保存 checkpoint 和 ONNX。

训练输出目录一般是：

```text
D:\GMR_WORK\mjlab\logs\rsl_rl\g1_tracking\时间戳\
```

里面会有：

```text
params\env.yaml
params\agent.yaml
model_*.pt
videos\train\
<run_dir_name>.onnx
```

## 4. 环境里有什么

`Mjlab-Tracking-Flat-Unitree-G1` 环境包含：

```text
机器人：Unitree G1
地形：平地 plane
仿真：MuJoCo
控制方式：关节位置 action
参考动作：motion.npz
奖励：跟踪 root/body/速度，惩罚动作变化、关节限位、自碰撞
终止：时间结束、姿态偏差过大、末端高度偏差过大等
```

G1 专用配置在：

```text
mjlab/src/mjlab/tasks/tracking/config/g1/env_cfgs.py
```

这里设置了 tracking 的关键 body：

```text
anchor_body_name = torso_link
body_names =
  pelvis
  left_hip_roll_link
  left_knee_link
  left_ankle_roll_link
  right_hip_roll_link
  right_knee_link
  right_ankle_roll_link
  torso_link
  left_shoulder_roll_link
  left_elbow_link
  left_wrist_yaw_link
  right_shoulder_roll_link
  right_elbow_link
  right_wrist_yaw_link
```

也就是说，训练并不是只看脚或只看关节角，而是让机器人多个关键 body 一起跟参考动作对齐。

## 5. 每个环境每一步在做什么

每个仿真 step 可以理解为：

```text
1. MotionCommand 给出当前参考帧
2. 环境生成 observation
3. policy 根据 observation 输出 action
4. action 转成 G1 关节位置控制目标
5. MuJoCo 推进物理仿真
6. 环境计算 robot 和 reference 的误差
7. 根据误差给 reward
8. 判断是否 termination
9. 进入下一帧
```

其中 `MotionCommand` 是 tracking 任务的核心。它加载 `motion.npz`，并维护每个并行环境当前应该跟踪哪一帧：

```text
self.time_steps[env_id]
```

每个环境可以在不同参考帧上训练，所以 512 个环境不是做完全一样的事。它们会覆盖动作不同阶段，提高采样效率。

## 6. 参考动作怎样进入训练

`MotionLoader` 读取 `motion.npz` 后得到：

```text
reference joint_pos
reference joint_vel
reference body_pos_w
reference body_quat_w
reference body_lin_vel_w
reference body_ang_vel_w
```

训练时，`MotionCommand` 会根据当前 `time_steps` 取出这一帧的参考状态。

例如：

```text
reference 当前关节角
reference 当前关节速度
reference 当前 torso/pelvis/feet/arms 的世界位置和姿态
reference 当前 body 线速度和角速度
```

这些 reference 一部分作为 observation 给 policy，一部分用于 reward 计算。

## 7. Policy 看到什么 observation

Actor，也就是真正输出动作的 policy，看到的主要信息包括：

```text
command: 当前参考关节位置和速度
motion_anchor_pos_b: 参考 anchor 相对机器人 base 的位置
motion_anchor_ori_b: 参考 anchor 相对机器人 base 的姿态
base_lin_vel: 机器人当前 base 线速度
base_ang_vel: 机器人当前 base 角速度
joint_pos: 当前关节位置
joint_vel: 当前关节速度
actions: 上一步动作
```

训练时 actor observation 会加噪声，例如：

```text
motion_anchor_pos_b 噪声
motion_anchor_ori_b 噪声
base velocity 噪声
joint position / velocity 噪声
```

这样做是为了让 policy 不要只适应完美传感器数据，而是对误差和扰动更鲁棒。

Critic 看到的信息更多，包括 body position / orientation 等更完整状态。这样 actor 可以在较接近真实机器人的信息条件下决策，而 critic 在训练时用更完整信息帮助估值。

## 8. Policy 输出什么 action

这个任务的 action 是：

```text
JointPositionAction
```

也就是说，神经网络不是直接输出力矩，而是输出每个关节的目标位置偏移或目标关节位置。mjlab 再通过 G1 的 actuator / PD 模型把目标位置转成实际控制。

直观理解：

```text
policy 每一步都在说：
“下一小步，各个关节应该往哪个目标角度去。”
```

G1 的 action scale 来自 robot config：

```text
G1_ACTION_SCALE
```

这会限制每个关节 action 的实际影响，避免网络一开始输出过大动作导致仿真炸掉。

## 9. Reward 怎样计算

Reward 的目标是：机器人越像 reference，奖励越高；越不稳定、越不合理，奖励越低。

当前 tracking reward 主要包括：

```text
motion_global_root_pos
motion_global_root_ori
motion_body_pos
motion_body_ori
motion_body_lin_vel
motion_body_ang_vel
action_rate_l2
joint_limit
self_collisions
```

含义：

```text
motion_global_root_pos:
  anchor/root 位置越接近参考，奖励越高。

motion_global_root_ori:
  anchor/root 姿态越接近参考，奖励越高。

motion_body_pos:
  pelvis、膝盖、脚踝、torso、手臂等关键 body 的相对位置越接近参考，奖励越高。

motion_body_ori:
  关键 body 的姿态越接近参考，奖励越高。

motion_body_lin_vel:
  body 线速度越接近参考，奖励越高。

motion_body_ang_vel:
  body 角速度越接近参考，奖励越高。

action_rate_l2:
  惩罚动作变化太快，减少抖动。

joint_limit:
  惩罚超过或接近关节限位。

self_collisions:
  惩罚自碰撞。
```

所以训练出来的 policy 不只是“摆对姿态”，还要尽量：

```text
速度像参考
动作平滑
少撞自己
不超关节限位
不摔倒
```

## 10. Episode 怎样开始和结束

一个 episode 是一次从某个参考动作帧开始的跟踪尝试。

训练时不是所有环境都从第 0 帧开始。默认 `sampling_mode="adaptive"`，会根据失败位置调整采样：

```text
哪些动作片段容易失败，就更常从那些片段开始训练。
```

这叫 adaptive sampling。它的目的不是让 policy 只看简单片段，而是重点补弱项。

每次 reset 时，环境还会加一些随机扰动：

```text
root 位置扰动
root 姿态扰动
root 速度扰动
关节位置扰动
```

这样 policy 学到的是“从有偏差的状态追回参考动作”，而不是只会在完美初始状态下播放动作。

Episode 终止条件包括：

```text
time_out:
  正常时间结束。

anchor_pos:
  torso/root 高度或位置偏差太大。

anchor_ori:
  姿态偏差太大。

ee_body_pos:
  脚踝、手腕等末端 body 高度偏差太大。
```

如果太早 termination，常见原因是：

```text
reference root 高度太低
动作本身难度太高
训练还没开始收敛
CSV quaternion 或关节顺序有问题
```

## 11. Domain Randomization 在做什么

训练时还有一些随机化事件：

```text
push_robot:
  训练中随机给机器人速度扰动。

base_com:
  随机改变 torso 附近质心。

encoder_bias:
  随机加入关节编码器偏差。

foot_friction:
  随机改变脚底摩擦。
```

这些不是为了让视频更好看，而是为了让策略更稳健。没有随机化时，policy 可能只适应一个非常理想的仿真条件；加随机化后，它更可能在扰动下仍然跟踪动作。

## 12. PPO 怎样更新 policy

mjlab 使用 RSL-RL 的 PPO。当前 G1 tracking 的 PPO 配置是：

```text
actor hidden dims: 512, 256, 128
critic hidden dims: 512, 256, 128
activation: elu
obs_normalization: True
init_std: 1.0
learning_rate: 1e-3
schedule: adaptive
gamma: 0.99
lambda: 0.95
entropy_coef: 0.005
clip_param: 0.2
num_learning_epochs: 5
num_mini_batches: 4
num_steps_per_env: 24
max_iterations: 默认 30000
save_interval: 500
```

一次 PPO iteration 大致是：

```text
1. 让当前 policy 在所有并行环境里运行 24 步
2. 收集 observation、action、reward、done、value
3. 用 GAE 估计 advantage
4. 用 PPO clipping 更新 actor
5. 用 value loss 更新 critic
6. 记录训练指标
7. 到 save_interval 时保存 checkpoint
```

如果 `num_envs=512`，每个 iteration 收集：

```text
512 * 24 = 12288 个 transition
```

如果 `num_envs=4096`，每个 iteration 收集：

```text
4096 * 24 = 98304 个 transition
```

所以 `num_envs` 越大，采样越快，但显存占用也越大。

## 13. 为什么训练初期会摔倒

训练刚开始时，policy 是随机的。它输出的关节目标基本没有意义，所以机器人很容易：

```text
摔倒
偏离 reference
动作抖动
提前 termination
```

这是正常现象。PPO 需要通过大量 episode 慢慢学到：

```text
当前状态离 reference 多远
下一步关节该怎么动
怎样既跟上动作又不摔
怎样在扰动后回到参考轨迹
```

如果训练几百 iteration 后仍完全不动或姿态乱飞，要优先排查数据，而不是盲目加训练步数。

## 14. 训练中最重要的几个参数

### 14.1 `--registry-name`

指定 reference motion artifact：

```bash
--registry-name wenboli787/motions/08_05_gmr
```

如果不写，tracking task 不知道训练哪个动作。

### 14.2 `--env.scene.num-envs`

并行环境数量。

建议：

```text
烟测：128
初始可用效果：512
更快正式训练：1024 / 2048 / 4096
```

显存不够时先降这个。

### 14.3 `--agent.max-iterations`

PPO 更新次数。

建议：

```text
烟测：100
初步效果：2000
更稳定：5000 / 10000+
默认完整：30000
```

### 14.4 `--video True`

训练过程中定期录制视频，输出到：

```text
logs/rsl_rl/g1_tracking/时间戳/videos/train/
```

这对观察“学得怎么样”很有用，但会增加训练开销。

### 14.5 `--enable-nan-guard True`

如果仿真出现 NaN，用它抓错误状态：

```bash
--enable-nan-guard True
```

## 15. 训练结果怎么用

训练过程中会保存：

```text
model_500.pt
model_1000.pt
model_1500.pt
...
```

这些是 PyTorch checkpoint。可以用 `play` 加载：

```bash
uv run play Mjlab-Tracking-Flat-Unitree-G1 \
  --wandb-run-path wenboli787/mjlab/你的run-id \
  --viewer native
```

如果用本地 checkpoint，需要同时给 motion file：

```bash
uv run play Mjlab-Tracking-Flat-Unitree-G1 \
  --checkpoint-file logs/rsl_rl/g1_tracking/你的时间戳/model_2000.pt \
  --motion-file "/mnt/d/GMR_WORK/mjlab/motions/08_05_gmr.npz" \
  --viewer native
```

tracking runner 还会导出 ONNX。这个 ONNX 不只包含 policy，还会把 reference motion 数据打包进去：

```text
joint_pos
joint_vel
body_pos_w
body_quat_w
body_lin_vel_w
body_ang_vel_w
```

这方便后续部署或复现实验。

## 16. 和 PD Tracking 的本质区别

PD tracking：

```text
输入：reference qpos
输出：每个关节的 PD 控制
特点：规则固定，不需要训练
问题：遇到动态难动作容易摔、滞后、脚滑
```

RL tracking：

```text
输入：reference motion + 当前机器人状态
输出：神经网络 policy 给出的动作
特点：需要训练，但能学会提前调整、恢复平衡、抗扰动
问题：训练成本高，对 reference 数据质量敏感
```

所以论文里不要把两者写成同一个阶段。更合理的结构是：

```text
Retargeting 阶段：
  GMR vs Basic IK vs Direct Mapping

Tracking 控制阶段：
  PD tracking vs RL tracking
```

## 17. 怎样判断训练是否正常

正常现象：

```text
前期容易摔倒
reward 逐渐上升
episode length 逐渐变长
tracking error 逐渐下降
视频里从乱动变成能跟参考动作
```

异常现象：

```text
一开始 reference ghost 就乱飞
机器人姿态完全不对
CSV 是 35 列或 37 列
quaternion 顺序错
root z 明显太低
训练一直 NaN
所有 checkpoint 播放都同样乱
```

排查顺序：

```text
1. 检查 CSV shape 是否 (T, 36)
2. 检查 root quaternion 是否 xyzw
3. 检查 joint order 是否和 G1 一致
4. 用 csv_to_npz --render True 看 reference 视频
5. 用 play --agent zero 看 reference ghost
6. 降低 num-envs 做 100 iteration 烟测
7. 再逐步增加训练量
```

## 18. 当前项目建议的训练路线

先不要全部动作一起训练。按这个顺序：

```text
第一步：08_05_gmr，512 envs，2000 iterations
目的：跑通并得到初步可见效果。

第二步：08_04_gmr / 10_01_gmr
目的：验证不同动作也能收敛。

第三步：13_17_gmr 这类长动作或难动作
目的：测试失败边界和论文展示。
```

推荐命令：

```bash
cd /mnt/d/GMR_WORK/mjlab

uv run train Mjlab-Tracking-Flat-Unitree-G1 \
  --registry-name wenboli787/motions/08_05_gmr \
  --env.scene.num-envs 512 \
  --agent.max-iterations 2000 \
  --video True
```

如果效果不够稳定：

```text
先加 max-iterations 到 5000 或 10000
再考虑 num-envs 到 1024 / 2048
最后才考虑改 reward 或环境配置
```

## 19. 训练闭环图

```text
GMR/IK/Direct PKL
        |
        v
36 列 mjlab CSV
        |
        v
csv_to_npz: MuJoCo FK 预处理
        |
        v
motion.npz / WandB motions artifact
        |
        v
MotionCommand 逐帧提供 reference
        |
        v
Actor policy 观察当前状态和 reference
        |
        v
输出关节位置 action
        |
        v
MuJoCo 推进机器人动力学
        |
        v
奖励函数比较 robot 和 reference
        |
        v
PPO 更新 actor / critic
        |
        v
保存 checkpoint / ONNX / 视频
```

