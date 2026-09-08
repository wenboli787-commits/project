# 第二章 方法

本章介绍本项目采用的人体动作到 Unitree G1 类人机器人的动作重定向与仿真跟踪方法。整体方法由两个主要阶段组成：第一阶段使用 General Motion Retargeting（GMR）将人体动作转换为机器人可表达的运动参考轨迹；第二阶段使用 MJLab 在 MuJoCo 物理仿真中训练和评估机器人对该参考轨迹的跟踪能力。为了区分动作重定向质量与控制器执行能力，本文将 GMR、Basic IK 和 Direct Mapping 视为参考动作生成方法，将 PD tracking 和基于 Proximal Policy Optimisation（PPO）的 reinforcement learning tracking 视为后续控制方法。

## 2.1 方法总览

本项目的整体流程可表示为：

```text
人体动作数据
    -> GMR / Basic IK / Direct Mapping 动作重定向
    -> Unitree G1 机器人参考轨迹 qpos
    -> 标准 PKL 文件
    -> MJLab CSV / motion.npz
    -> MuJoCo 物理仿真
    -> PD tracking 或 PPO tracking
    -> 误差、稳定性和失败案例分析
```

其中，GMR 阶段的目标是生成机器人运动学参考轨迹，而 MJLab 阶段的目标是研究机器人在物理仿真中是否能够稳定执行该参考轨迹。二者解决的问题不同。GMR 关注的是人体动作如何映射到机器人结构上；MJLab tracking 关注的是具有质量、惯量、摩擦和接触约束的机器人是否能够跟踪该轨迹。

设人体动作序列共有 \(T\) 帧。第 \(t\) 帧人体动作可表示为一组人体关键 body 的位姿：

\[
\mathcal{H}_t = \{(p_i^h(t), q_i^h(t))\}_{i=1}^{N_h}
\]

其中，\(p_i^h(t) \in \mathbb{R}^3\) 表示人体第 \(i\) 个 body 在世界坐标系中的位置，\(q_i^h(t)\) 表示其姿态四元数。GMR 输出的机器人运动可写为 MuJoCo 的 generalized coordinate：

\[
q_t^r = [p_{\text{root}}(t), q_{\text{root}}(t), q_{\text{joint}}(t)]
\]

其中，\(p_{\text{root}} \in \mathbb{R}^3\)，\(q_{\text{root}} \in \mathbb{H}\)，\(q_{\text{joint}} \in \mathbb{R}^{29}\)。对于 Unitree G1，本项目使用 29 DoF 版本，关节包括双腿、腰部和双臂。GMR 的标准 PKL 文件中保存 `qpos`、`qvel`、`root_pos`、`root_quat`、`dof_pos`、`body_pos`、`body_quat`、`contacts`、`fall` 等字段，以便后续评价和 tracking 使用。

## 2.2 人体动作数据处理

本项目使用的人体动作主要为 AMASS/SMPL-X 风格的 `.npz` 文件。原始文件通常包含 `poses`、`trans`、`gender`、`mocap_framerate`、`betas` 和 `dmpls` 等字段。GMR 首先通过 SMPL-X/AMASS loader 将人体参数化动作转换为逐帧人体 body 位姿。为了使不同来源的动作能够进入同一重定向流程，动作处理阶段需要完成以下步骤：

1. 读取原始人体动作文件；
2. 根据目标帧率对动作进行时间对齐；
3. 从人体模型中提取 pelvis、spine、shoulder、elbow、wrist、hip、knee 和 foot 等 body 的全局位置与姿态；
4. 根据 GMR 的人体尺度表对人体动作进行比例缩放；
5. 根据人体到机器人 body 的对应关系加入位置和旋转 offset；
6. 将处理后的人体 body 位姿作为 IK 目标。

在 GMR 中，人体尺度处理并不是简单地整体缩放所有点，而是在人体 root 局部坐标系下进行分部缩放。设人体 root 为 \(r\)，人体第 \(i\) 个 body 的原始位置为 \(p_i^h\)，root 位置为 \(p_r^h\)，对应的缩放系数为 \(s_i\)。则缩放后的 root 和其他 body 位置可写为：

\[
\tilde{p}_r^h = s_r p_r^h
\]

\[
\tilde{p}_i^h = \tilde{p}_r^h + s_i (p_i^h - p_r^h), \quad i \neq r
\]

这种处理方式保留了人体 body 相对于 pelvis 的局部结构，同时允许腿、躯干和手臂使用不同的尺度系数。对于 Unitree G1 的 SMPL-X 到机器人配置，本项目使用的 GMR 配置中人体身高假设为 1.8 m。当输入人体高度可用时，GMR 会根据实际人体高度与配置中假设高度的比值进一步调整 `human_scale_table`。

随后，GMR 对人体目标 body 加入局部位置 offset 和旋转 offset。设配置表中第 \(i\) 个人体 body 的位置 offset 为 \(o_i\)，旋转 offset 为 \(R_i^{off}\)，则目标姿态与目标位置可写为：

\[
\tilde{R}_i^h = R_i^h R_i^{off}
\]

\[
p_i^{target} = \tilde{p}_i^h + \tilde{R}_i^h o_i
\]

其中 \(R_i^h\) 是由人体姿态四元数转换得到的旋转矩阵。offset 的作用是补偿人体 body 坐标系与机器人 body 坐标系之间的定义差异。例如，人体脚部、肩部或手腕的局部坐标轴不一定与 Unitree G1 对应 link 的坐标轴一致，因此需要旋转 offset 来使两者的姿态误差具有可比性。

## 2.3 GMR 动作重定向原理

GMR 的核心是一个基于逆运动学的加权优化问题。它将人体关键 body 的目标位姿转换为机器人关键 body 的目标位姿，然后求解机器人 generalized coordinate \(q^r\)，使机器人 body 尽可能匹配这些目标。

### 2.3.1 人体与机器人 body 映射

对于 Unitree G1，本项目使用 `smplx_to_g1.json` 中定义的映射关系。该配置包含两个 IK match table。每一项定义一个机器人 body、对应的人体 body、位置权重、旋转权重、位置 offset 和旋转 offset。典型对应关系包括：

```text
pelvis              <- pelvis
left_hip_roll_link  <- left_hip
left_knee_link      <- left_knee
left_toe_link       <- left_foot
right_hip_roll_link <- right_hip
right_knee_link     <- right_knee
right_toe_link      <- right_foot
torso_link          <- spine3
left_shoulder_yaw_link  <- left_shoulder
left_elbow_link         <- left_elbow
left_wrist_yaw_link     <- left_wrist
right_shoulder_yaw_link <- right_shoulder
right_elbow_link        <- right_elbow
right_wrist_yaw_link    <- right_wrist
```

第一阶段 match table 更强调 root、脚端和关键 body 的姿态匹配。例如 pelvis 和 toe link 的位置权重较高。第二阶段 match table 会进一步加入 hip、knee、shoulder、elbow 和 wrist 的位置权重，使机器人姿态更贴近人体局部结构。这样做的目的是先得到稳定的整体姿态，再细化局部 body 的匹配。

### 2.3.2 加权 IK 目标函数

设第 \(k\) 个机器人 body 的正运动学位置和姿态分别为 \(p_k^r(q)\) 和 \(R_k^r(q)\)，其目标位置和姿态分别为 \(p_k^\ast\) 和 \(R_k^\ast\)。GMR 的优化目标可以概括为：

\[
\min_{\Delta q}
\sum_{k \in \mathcal{B}}
w_k^p \|p_k^r(q+\Delta q)-p_k^\ast\|_2^2
+
w_k^R \|\mathrm{Log}((R_k^\ast)^\top R_k^r(q+\Delta q))\|_2^2
+
\lambda \|\Delta q\|_2^2
\]

其中，\(\mathcal{B}\) 为参与匹配的机器人 body 集合，\(w_k^p\) 为位置权重，\(w_k^R\) 为姿态权重，\(\mathrm{Log}(\cdot)\) 表示从旋转矩阵到轴角误差向量的李代数映射，\(\lambda\) 是阻尼项。阻尼项用于提高数值稳定性，防止在奇异姿态或目标不可达时产生过大的关节更新。

该优化同时受到机器人关节限制约束：

\[
q_{\min} \le q \le q_{\max}
\]

如果启用速度限制，还可加入：

\[
|\dot{q}_j| \le \dot{q}_{j,\max}
\]

本地 GMR 实现中，求解器使用 `mink.solve_ik`，默认 solver 为 `daqp`，阻尼系数为 `0.5`，每帧最多迭代 10 次。当当前误差与下一次迭代误差的下降量小于 0.001 时，迭代提前停止。该策略使每一帧的 IK 求解在保持效率的同时尽量减小关键 body 的位姿误差。

### 2.3.3 两阶段求解

GMR 中的 `ik_match_table1` 和 `ik_match_table2` 分别对应两个任务集合。对于每一帧，系统先根据第一阶段任务求解机器人姿态，然后在此基础上使用第二阶段任务继续优化。可写为：

\[
q_t^{(1)} = \mathrm{IK}_1(q_{t-1}, \mathcal{T}_1(t))
\]

\[
q_t^{(2)} = \mathrm{IK}_2(q_t^{(1)}, \mathcal{T}_2(t))
\]

最终输出：

\[
q_t^r = q_t^{(2)}
\]

其中 \(\mathcal{T}_1(t)\) 和 \(\mathcal{T}_2(t)\) 分别表示第 \(t\) 帧第一阶段和第二阶段的目标 body 位姿集合。由于每一帧的求解以当前配置为初值，并随着时间逐帧推进，GMR 输出的机器人动作通常具有一定时间连续性。

### 2.3.4 GMR 输出

GMR 每一帧输出机器人 MuJoCo `qpos`。对于 Unitree G1，`qpos` 的主要结构为：

\[
qpos_t = [x, y, z, q_w, q_x, q_y, q_z, q_1, q_2, \ldots, q_{29}]
\]

其中 root quaternion 在 GMR/MuJoCo 中使用 `wxyz` 顺序。标准 PKL 不额外加入高度修正、root 对齐、平滑或人为优化，因此更适合用于公平比较。后续将 `qpos` 转换到 MJLab 时，需要将 root quaternion 从 `wxyz` 转为 `xyzw`，并导出为 36 列 CSV：

\[
\mathrm{CSV}_t =
[x, y, z, q_x, q_y, q_z, q_w, q_1, \ldots, q_{29}]
\]

## 2.4 Direct Mapping、Basic IK 与 GMR 的区别

本文将 Direct Mapping、Basic IK 和 GMR 作为三种参考动作生成方法进行比较。

Direct Mapping 是最简单的基线方法。它直接将人体 root 或关键关节信息映射到机器人对应关节或 body 上。该方法实现简单，但对机器人结构、关节限制和 body 坐标系差异考虑较少，容易出现关节不自然、脚部接触错误或 body 姿态不合理等问题。

Basic IK 使用与 GMR 相同或相近的人体动作预处理流程，将人体关键点转换为 IK target，然后通过逆运动学求解机器人姿态。与 GMR 相比，Basic IK 不使用 GMR 的完整 retargeting seed 和调优策略，也不一定使用相同的两阶段权重设计。因此，Basic IK 可以作为比 Direct Mapping 更强但仍相对基础的几何基线。

GMR 则使用针对机器人和人体动作格式配置好的 match table、位置/旋转权重、尺度表和 offset。它更强调机器人 body 与人体 body 的结构对应关系，并通过两阶段 IK 求解得到更适合 Unitree G1 的参考轨迹。因此，理论上 GMR 应在 body 匹配、脚端位置、整体姿态和关节可行性方面优于更简单的基线方法，但最终仍需要通过定量指标和物理仿真验证。

## 2.5 从 GMR 参考轨迹到 MJLab 训练数据

MJLab tracking 任务不能直接读取 GMR、Basic IK 或 Direct Mapping 的 `.pkl` 文件。它需要使用特定格式的 `motion.npz` 作为 reference motion。因此，本项目采用以下转换流程：

```text
GMR / IK / Direct PKL
    -> 36 列 MJLab CSV
    -> csv_to_npz
    -> motion.npz / WandB motions artifact
```

PKL 到 CSV 的转换从 `qpos` 中读取：

\[
root\_pos = qpos[:,0:3]
\]

\[
root\_quat_{wxyz} = qpos[:,3:7]
\]

\[
dof\_pos = qpos[:,7:36]
\]

随后将四元数顺序变为 MJLab 所需的 `xyzw`：

\[
[q_x,q_y,q_z,q_w] = [qpos_4,qpos_5,qpos_6,qpos_3]
\]

最终每一帧 CSV 共有 36 列。之后，MJLab 的 `csv_to_npz` 会在 MuJoCo 中播放该轨迹，并通过前向运动学计算每个 body 的状态，输出：

```text
fps
joint_pos
joint_vel
body_pos_w
body_quat_w
body_lin_vel_w
body_ang_vel_w
```

这一转换非常重要，因为 MJLab 的 reward 和 observation 并不只使用关节角，而是大量使用 robot body 的位置、姿态和速度。如果 body ordering 或 quaternion 顺序错误，训练目标会与机器人 body 对错，导致策略无法收敛。

本项目中，GMR final PKL 按 30 FPS 使用，而 MJLab tracking 默认控制步长为 0.02 s，即 50 Hz。因此 CSV 到 NPZ 阶段使用输入 30 FPS、输出 50 FPS 的重采样设置，使 reference motion 与 MJLab policy step 对齐。

## 2.6 MJLab 物理仿真环境

MJLab 是基于 MuJoCo / MuJoCo Warp 的机器人学习框架。本文使用的任务为：

```text
Mjlab-Tracking-Flat-Unitree-G1
```

该环境由以下部分组成：

```text
机器人：Unitree G1
地形：平地 plane
仿真器：MuJoCo
控制方式：JointPositionAction
参考动作：motion.npz
训练算法：RSL-RL PPO
```

MJLab 仿真 timestep 为 0.005 s，decimation 为 4。因此，底层 MuJoCo 每 0.005 s 推进一步，而策略每 4 个仿真步输出一次 action：

\[
\Delta t_{policy} = 0.005 \times 4 = 0.02 \text{ s}
\]

即 policy 频率为 50 Hz。环境 episode 默认长度为 10 s。

### 2.6.1 跟踪 body 与 anchor

在 Unitree G1 tracking 配置中，`torso_link` 被设置为 anchor body。环境跟踪的关键 body 包括：

```text
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

这意味着策略并不是只跟踪 root 或脚部，而是同时使 pelvis、腿部、躯干和手臂等多个关键 body 与 reference 对齐。这样可以更完整地评价 whole-body motion tracking 的质量。

### 2.6.2 MotionCommand

MJLab 中的 `MotionCommand` 负责加载 `motion.npz` 并为每个并行环境维护当前参考帧索引：

\[
\tau_e \in \{0,1,\ldots,T-1\}
\]

其中 \(e\) 表示第 \(e\) 个并行环境。每一步，环境根据 \(\tau_e\) 读取当前参考关节角、关节速度、body 位置、body 姿态、body 线速度和角速度。随后 \(\tau_e\) 加 1。当参考动作播放到末尾或 episode reset 时，环境重新采样起始帧。

训练时使用 adaptive sampling。其核心思想是：如果某些动作片段更容易失败，则增加从这些片段开始训练的概率。设第 \(b\) 个时间 bin 的历史失败计数为 \(C_b\)，当前迭代中该 bin 的失败计数为 \(\hat{C}_b\)，则失败统计可近似表示为指数滑动更新：

\[
C_b \leftarrow \alpha \hat{C}_b + (1-\alpha)C_b
\]

采样概率则由失败计数和均匀项共同决定：

\[
P(b) =
\frac{C_b + \epsilon}{\sum_j (C_j + \epsilon)}
\]

其中 \(\epsilon\) 对应配置中的 uniform ratio，用于避免完全忽略低失败率片段。adaptive sampling 的作用是让 PPO 更频繁地训练困难片段，而不是只在容易片段上获得较高 reward。

### 2.6.3 Reset 随机化与 domain randomization

每次 reset 时，MJLab 会在参考 root 状态上加入扰动，包括 root 位置、root 姿态、root 速度和关节位置扰动。其目的不是改变参考动作，而是训练策略从有偏差的状态恢复到参考轨迹。简化表示为：

\[
\tilde{x}_0 = x_0^{ref} + \epsilon_x
\]

其中 \(\epsilon_x\) 是来自配置范围的均匀随机扰动。

此外，环境还使用 domain randomization，包括随机外力或速度扰动、base center of mass 偏移、encoder bias 和脚底摩擦系数变化。这些随机化使策略不只适应理想仿真条件，而是对状态误差、传感器偏差和接触变化更鲁棒。

## 2.7 Observation 与 Action

### 2.7.1 Actor observation

PPO 的 actor policy 接收当前机器人状态和参考动作信息。主要 observation 包括：

```text
command                  当前参考 joint_pos 和 joint_vel
motion_anchor_pos_b       参考 anchor 相对机器人 anchor 的位置
motion_anchor_ori_b       参考 anchor 相对机器人 anchor 的姿态
base_lin_vel              IMU 线速度
base_ang_vel              IMU 角速度
joint_pos                 当前关节位置相对默认关节位置
joint_vel                 当前关节速度相对默认关节速度
actions                   上一步 action
```

其中 anchor 相对位置可表示为：

\[
p_{a,b}^{ref} =
(R_a^{robot})^\top (p_a^{ref} - p_a^{robot})
\]

姿态误差则通过相对旋转表示：

\[
R_{a,b}^{ref} =
(R_a^{robot})^\top R_a^{ref}
\]

源码中将该相对姿态转换为旋转矩阵，并取前两列作为 observation。这种方式避免了四元数符号不唯一的问题。

Actor observation 在训练时加入噪声，例如 anchor position noise、anchor orientation noise、base velocity noise、joint position noise 和 joint velocity noise。这样可以提高策略对观测误差的鲁棒性。

### 2.7.2 Critic observation

Critic 使用的信息比 actor 更完整。除 actor 信息外，critic 还包含 robot body position 和 body orientation 等完整状态。这样设计的原因是 actor 更接近真实机器人可获得的观测，而 critic 在训练阶段可使用更丰富状态来提高 value estimation 的准确性。

### 2.7.3 Action 到关节目标

本任务使用 `JointPositionAction`。策略输出原始 action：

\[
a_t \in \mathbb{R}^{29}
\]

MJLab 将 action 经过 scale 和 offset 转换为关节位置目标：

\[
q_t^{des} = q^{default} + S \odot a_t
\]

其中 \(S\) 是 G1 action scale，\(q^{default}\) 是机器人默认关节位置。考虑 encoder bias 后，实际写入 actuator 的目标为：

\[
q_t^{target} = q_t^{des} - b_{enc}
\]

其中 \(b_{enc}\) 是训练中随机加入的 encoder bias。策略因此不是直接输出力矩，而是输出每个关节下一步希望到达的目标角度。

## 2.8 PD actuator 原理

MJLab 中的 position action 最终通过 actuator 转换为机器人关节力矩。对于理想 PD actuator，其控制公式为：

\[
\tau_t =
K_p(q_t^{target} - q_t)
+
K_d(\dot{q}_t^{target} - \dot{q}_t)
+
\tau_t^{ff}
\]

其中，\(K_p\) 为 stiffness，\(K_d\) 为 damping，\(\tau_t^{ff}\) 为 feed-forward effort。计算出的力矩会被限制在最大力矩范围内：

\[
\tau_t^{clip} = \mathrm{clip}(\tau_t, -\tau_{\max}, \tau_{\max})
\]

该公式说明，RL policy 并不是直接学习每个关节的最终力矩，而是学习关节位置目标。PD actuator 负责根据目标角度与当前角度之间的误差产生控制力矩。这种设计降低了学习难度，因为神经网络只需学习“下一步关节应该朝哪个目标位置运动”，而不需要直接学习底层力矩控制。

在论文中，PD tracking 和 RL tracking 应分开讨论。PD tracking 使用固定控制律直接跟踪参考轨迹；RL tracking 使用 PPO 学习一个状态反馈策略，由策略根据当前状态和参考动作动态输出关节位置目标。二者的本质区别在于，PD 是固定规则控制，而 PPO policy 可以通过训练学习提前调整、恢复平衡和抵抗扰动。

## 2.9 Reward 设计

MJLab tracking reward 的目标是使机器人执行动作尽量接近 reference，同时惩罚不平滑、不稳定和不可行的行为。总奖励可写为：

\[
r_t =
\sum_i w_i r_i(t)
\]

其中 \(r_i\) 为不同奖励项或惩罚项，\(w_i\) 为对应权重。本项目使用的主要 reward 项如下。

### 2.9.1 Root 位置奖励

Root 或 anchor 位置奖励计算参考 anchor 与机器人 anchor 的世界坐标误差：

\[
e_p =
\|p_a^{ref} - p_a^{robot}\|_2^2
\]

\[
r_{root,pos} =
\exp\left(-\frac{e_p}{\sigma_p^2}\right)
\]

在配置中，该项 \(\sigma_p=0.3\)，权重为 0.5。

### 2.9.2 Root 姿态奖励

Root 姿态误差使用四元数距离表示。设 \(d_q(q^{ref},q^{robot})\) 为两个四元数之间的旋转误差，则：

\[
r_{root,ori} =
\exp\left(-\frac{d_q(q_a^{ref},q_a^{robot})^2}{\sigma_R^2}\right)
\]

配置中 \(\sigma_R=0.4\)，权重为 0.5。

### 2.9.3 Body 位置奖励

为了避免只跟踪 root 而忽略四肢，本任务对多个关键 body 的相对位置进行奖励。设跟踪 body 数量为 \(N_b\)，则：

\[
e_{body,pos} =
\frac{1}{N_b}
\sum_{k=1}^{N_b}
\|p_k^{ref,rel} - p_k^{robot}\|_2^2
\]

\[
r_{body,pos} =
\exp\left(-\frac{e_{body,pos}}{\sigma_{bp}^2}\right)
\]

其中 \(p_k^{ref,rel}\) 是经过机器人当前 anchor 平移和 heading 对齐后的参考 body 位置。该项使用 \(\sigma_{bp}=0.3\)，权重为 1.0。

### 2.9.4 Body 姿态奖励

Body 姿态奖励对多个关键 body 的旋转误差求平均：

\[
e_{body,ori} =
\frac{1}{N_b}
\sum_{k=1}^{N_b}
d_q(q_k^{ref,rel}, q_k^{robot})^2
\]

\[
r_{body,ori} =
\exp\left(-\frac{e_{body,ori}}{\sigma_{bR}^2}\right)
\]

配置中 \(\sigma_{bR}=0.4\)，权重为 1.0。

### 2.9.5 Body 速度奖励

线速度和角速度奖励分别为：

\[
e_{lin} =
\frac{1}{N_b}
\sum_{k=1}^{N_b}
\|v_k^{ref} - v_k^{robot}\|_2^2
\]

\[
r_{lin} =
\exp\left(-\frac{e_{lin}}{\sigma_v^2}\right)
\]

\[
e_{ang} =
\frac{1}{N_b}
\sum_{k=1}^{N_b}
\|\omega_k^{ref} - \omega_k^{robot}\|_2^2
\]

\[
r_{ang} =
\exp\left(-\frac{e_{ang}}{\sigma_\omega^2}\right)
\]

其中 \(\sigma_v=1.0\)，\(\sigma_\omega=3.14\)，两个项权重均为 1.0。速度奖励使机器人不仅姿态接近 reference，而且运动节奏和动态变化也接近 reference。

### 2.9.6 动作平滑惩罚

动作变化率惩罚用于降低策略输出抖动：

\[
c_{action} =
\|a_t - a_{t-1}\|_2^2
\]

该项在配置中权重为 \(-0.1\)。由于该项作用于 raw policy action，它直接鼓励神经网络输出更平滑的动作序列。

### 2.9.7 关节限位惩罚

若关节超过 soft joint limits，环境会计算越界量：

\[
c_{limit} =
\sum_j
\max(q_{j,\min}-q_j,0)
+
\max(q_j-q_{j,\max},0)
\]

该项权重为 \(-10.0\)。它防止 policy 通过不合理的关节角来追踪 reference。

### 2.9.8 自碰撞惩罚

环境使用 contact sensor 监测 pelvis subtree 内的自碰撞。如果接触力超过阈值，则累计碰撞次数：

\[
c_{collision} =
\sum_h \mathbf{1}(\|f_h\| > f_{th})
\]

其中 \(f_{th}=10.0\)。该项权重为 \(-10.0\)。自碰撞惩罚可以减少手臂、腿部或躯干之间不合理穿插。

## 2.10 Episode 终止条件

MJLab tracking 环境包含多个 termination 条件。除正常 time-out 外，主要失败条件包括：

1. anchor 高度偏差过大；
2. anchor 姿态偏差过大；
3. 手腕或脚踝等末端 body 的高度偏差过大。

Anchor 高度终止可写为：

\[
|z_a^{ref} - z_a^{robot}| > 0.25
\]

末端 body 高度终止为：

\[
\exists k \in \mathcal{E}, \quad
|z_k^{ref,rel} - z_k^{robot}| > 0.25
\]

其中 \(\mathcal{E}\) 包括左右脚踝和左右手腕。姿态终止通过比较参考 anchor 和机器人 anchor 坐标系下的 projected gravity 完成。当姿态偏差超过阈值 0.8 时，episode 提前结束。提前终止通常意味着机器人已明显偏离 reference 或失去稳定性。

## 2.11 PPO 策略训练

本项目使用 MJLab 中基于 RSL-RL 的 PPO 训练 Unitree G1 tracking policy。PPO 属于 on-policy 强化学习算法。其目标是在保持策略更新幅度受限的前提下，提高期望累计回报。

### 2.11.1 MDP 表示

Tracking 任务可表示为马尔可夫决策过程：

\[
(\mathcal{S}, \mathcal{A}, P, r, \gamma)
\]

其中，\(s_t \in \mathcal{S}\) 为 observation，包含机器人当前状态和 reference motion 信息；\(a_t \in \mathcal{A}\) 为策略输出的关节位置 action；\(P\) 为 MuJoCo 动力学和环境随机化共同决定的状态转移；\(r_t\) 为 tracking reward；\(\gamma\) 为折扣因子。

策略为高斯分布：

\[
a_t \sim \pi_\theta(a_t|s_t)
\]

Actor 网络输出动作分布，critic 网络估计状态价值：

\[
V_\phi(s_t) \approx \mathbb{E}\left[\sum_{k=0}^{\infty}\gamma^k r_{t+k}\right]
\]

### 2.11.2 Advantage estimation

PPO 使用 generalized advantage estimation（GAE）估计 advantage。首先计算 TD residual：

\[
\delta_t =
r_t + \gamma V_\phi(s_{t+1}) - V_\phi(s_t)
\]

随后 advantage 为：

\[
\hat{A}_t =
\sum_{l=0}^{\infty}
(\gamma \lambda)^l \delta_{t+l}
\]

其中，本项目配置为：

\[
\gamma = 0.99, \quad \lambda = 0.95
\]

\(\gamma\) 控制未来奖励的重要性，\(\lambda\) 控制 bias-variance trade-off。

### 2.11.3 PPO clipping objective

设旧策略为 \(\pi_{\theta_{old}}\)，新策略为 \(\pi_\theta\)。PPO 使用概率比：

\[
\rho_t(\theta) =
\frac{\pi_\theta(a_t|s_t)}
{\pi_{\theta_{old}}(a_t|s_t)}
\]

策略目标函数为：

\[
L^{CLIP}(\theta) =
\mathbb{E}_t
\left[
\min
\left(
\rho_t(\theta)\hat{A}_t,
\mathrm{clip}(\rho_t(\theta), 1-\epsilon, 1+\epsilon)\hat{A}_t
\right)
\right]
\]

其中 \(\epsilon=0.2\)。当新策略相对旧策略改变过大时，clip 项会限制更新幅度，从而避免训练不稳定。

### 2.11.4 Value loss 与 entropy bonus

Critic 使用 value loss 更新：

\[
L^V(\phi) =
\mathbb{E}_t
\left[
(V_\phi(s_t) - \hat{R}_t)^2
\right]
\]

其中 \(\hat{R}_t\) 是估计回报。Entropy bonus 用于鼓励策略探索：

\[
H(\pi_\theta(\cdot|s_t))
\]

综合损失可写为：

\[
L(\theta,\phi) =
-L^{CLIP}(\theta)
+
c_v L^V(\phi)
-
c_H H(\pi_\theta)
\]

本项目配置中：

```text
value_loss_coef = 1.0
entropy_coef = 0.005
clip_param = 0.2
desired_kl = 0.01
max_grad_norm = 1.0
```

其中 desired KL 用于 adaptive learning rate schedule。当策略更新导致 KL divergence 过大时，学习率会被调低，以保持训练稳定。

### 2.11.5 网络结构与训练参数

Unitree G1 tracking 的 actor 和 critic 均使用多层感知机：

```text
hidden dimensions: 512, 256, 128
activation: ELU
observation normalization: True
actor distribution: Gaussian
initial std: 1.0
learning rate: 1e-3
```

PPO 每次 iteration 在所有并行环境中采样 24 个 policy step：

```text
num_steps_per_env = 24
num_learning_epochs = 5
num_mini_batches = 4
save_interval = 500
max_iterations = 30000
```

若使用 512 个并行环境，每次 iteration 收集：

\[
512 \times 24 = 12288
\]

个 transition。若使用 4096 个并行环境，则每次 iteration 收集：

\[
4096 \times 24 = 98304
\]

个 transition。并行环境越多，采样效率越高，但显存占用也越大。因此，本项目通常先使用 128 或 512 个环境进行 smoke test 和初始训练，再根据显存情况增加到 1024、2048 或 4096。

## 2.12 评价方法

本项目评价分为两个层次：第一层评价 GMR、Basic IK 和 Direct Mapping 生成的 reference motion 质量；第二层评价 PD tracking 和 RL tracking 对同一 reference motion 的物理执行能力。

### 2.12.1 Reference motion 质量评价

Reference motion 质量评价使用统一的 retargeting evaluation toolkit。该工具读取原始人体动作和三种方法生成的机器人 PKL，计算以下指标：

```text
success_rate
raw_global_error_mm
aligned_global_error_mm
root_relative_error_mm
bone_orientation_error_deg
total_foot_sliding_m
max_ground_penetration_m
self_collision_count
sudden_jump_count
overall_score
```

Mean per-keybody position error 可表示为：

\[
MPKPE =
\frac{1}{N}
\sum_{i=1}^{N}
\|p_i^{ref} - p_i^{robot}\|_2
\]

Root-relative MPKPE 去除了全局平移和 heading drift，更关注机器人身体局部结构是否与 reference 一致：

\[
R\text{-}MPKPE =
\frac{1}{N}
\sum_{i=1}^{N}
\|p_i^{ref,rel} - p_i^{robot}\|_2
\]

脚滑指标用于衡量脚在接触地面时的水平移动量。设脚部高度低于接触阈值 \(h_c\)，且水平速度超过阈值 \(v_c\) 时认为发生滑动，则总脚滑可近似写为：

\[
D_{slip} =
\sum_{t}
\mathbf{1}(z_{foot}(t)<h_c)
\left\|
p_{foot}^{xy}(t+1)-p_{foot}^{xy}(t)
\right\|_2
\]

在配置中，脚接触高度阈值为 0.04 m，脚滑速度阈值为 0.10 m/s。穿地指标计算脚或 body 低于地面的最大深度；突变指标统计关节速度超过自适应阈值或绝对阈值的帧数；自碰撞指标基于 MuJoCo contact 统计非相邻 body 的碰撞。

综合评分只用于辅助排序，不替代原始指标。其权重包括：

```text
success: 0.25
root_relative_error: 0.20
global_error: 0.15
foot_sliding: 0.15
ground_penetration: 0.10
sudden_jumps: 0.10
self_collision: 0.05
```

因此，论文分析中应优先使用原始指标说明具体问题，再用 overall score 做整体比较。

### 2.12.2 Tracking 执行评价

Tracking 评价关注机器人在物理仿真中是否真正跟上 reference。主要指标包括：

```text
episode reward
episode length
tracking error
MPKPE
R-MPKPE
joint velocity error
end-effector position error
end-effector orientation error
fall rate / success rate
action smoothness
joint limit penalty
self-collision penalty
```

其中，MPKPE 衡量全局 body 跟踪误差，R-MPKPE 衡量去除全局漂移后的局部姿态误差，末端误差重点关注左右脚踝和左右手腕。若 RL tracking 相比 PD tracking 具有更低的 R-MPKPE、更长的 episode length 和更低的 fall rate，则说明 RL policy 更能够在动力学约束下稳定执行参考动作。

## 2.13 本章小结

本章介绍了从人体动作到类人机器人仿真执行的完整方法。GMR 阶段通过人体尺度处理、body offset 和加权 IK 优化，将人体动作转换为 Unitree G1 的运动学参考轨迹。MJLab 阶段将该参考轨迹转换为 `motion.npz`，并在 MuJoCo 物理仿真中训练 PPO tracking policy。策略以参考动作和机器人当前状态作为输入，输出关节位置 action，并通过 PD actuator 作用于机器人。奖励函数同时考虑 root、body、速度、动作平滑性、关节限制和自碰撞。最终，通过 reference motion 质量评价和 tracking 执行评价，可以分别分析动作重定向方法本身的质量，以及控制器在物理仿真中的执行能力。
