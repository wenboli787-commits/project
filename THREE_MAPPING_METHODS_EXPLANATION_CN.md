# 三种动作映射方式效果差异与代码差异说明

本文解释三种 LAFAN1 BVH 到 MuJoCo 机器人动作映射方式为什么会产生不同效果，以及它们在代码实现上具体有什么不同。

三种方式分别是：

1. GMR 原方法
2. Direct mapping，直接映射
3. Basic IK retargeting，无限制简单 IK 重定向

对应代码：

```text
GMR 原方法:
GMR/scripts/bvh_to_robot.py
GMR/general_motion_retargeting/motion_retarget.py

Direct mapping:
GMR/direct mapping/run_direct_mapping.py

Basic IK retargeting:
GMR/Basic IK retargeting/run_basic_ik_retargeting.py
```

## 1. 一句话总结

```text
GMR:
用配置好的两阶段 IK + 机器人关节限制，把人体关键 body 的位置和姿态优化到机器人上。

Direct mapping:
不做 IK，直接把人体局部关节旋转变化投影到机器人 hinge joint 上。

Basic IK:
做 IK，但只做最基础的目标追踪；不使用关节限制、不使用速度限制，默认只用一张 IK task table。
```

所以它们效果不同，根本原因是：

```text
它们优化的目标不同、使用的约束不同、对人体和机器人骨架差异的处理能力不同。
```

## 2. 三者共同点

三者输入相同：

```text
D:\GMR_WORK\ubisoft-laforge-animation-dataset\lafan1\extracted
```

三者机器人模型来源相同：

```text
D:\GMR_WORK\GMR\assets
```

三者都依赖 GMR 的 LAFAN1 配置：

```text
GMR/general_motion_retargeting/ik_configs/bvh_lafan1_to_*.json
```

两个新 baseline 还额外保证第 0 帧和 GMR 一致：

```text
先调用 GMR 对第 0 帧求 initial_qpos；
Direct mapping 第 0 帧直接返回这个 initial_qpos；
Basic IK 先把 IK configuration 重置到这个 initial_qpos；
```

因此三种方法从同一个机器人初始姿态开始，后面的差异来自映射算法本身。

## 3. GMR 原方法为什么效果通常最好

GMR 的核心在：

```text
GMR/general_motion_retargeting/motion_retarget.py
```

它每帧做的事情是：

1. 读取人体 BVH frame
2. 按 IK config 缩放人体骨架
3. 给人体 body 加位置 offset 和旋转 offset，使人体坐标系更接近机器人坐标系
4. 创建机器人 body 的 IK task
5. 用 `mink.solve_ik` 求机器人 `qpos`
6. 使用 `mink.ConfigurationLimit(self.model)` 限制机器人关节范围
7. 按配置执行 `ik_match_table1` 和 `ik_match_table2` 两阶段 IK

GMR 的代码特点：

```python
self.ik_limits = [mink.ConfigurationLimit(self.model)]
```

这意味着 GMR 默认会考虑 MuJoCo XML 里的关节范围。

如果开启速度限制，还会加入：

```python
mink.VelocityLimit(...)
```

不过当前脚本默认没有开启速度限制。

GMR 还会使用两张 task table：

```text
ik_match_table1
ik_match_table2
```

代码中先求第一阶段，再求第二阶段：

```text
先 solve tasks1
再 solve tasks2
```

这很重要。它不是一次性把所有目标粗暴塞进 IK，而是按配置分阶段追踪。通常第一阶段更偏身体主姿态、根节点、主要链条，第二阶段再细化手脚、躯干等目标。

因此 GMR 的效果通常更好，原因是：

```text
它不是单纯复制人体角度；
它会在机器人自己的运动学结构里求一个更合理的 qpos；
它会遵守机器人关节范围；
它通过权重、offset、两阶段 task 降低人体骨架和机器人骨架不一致带来的问题。
```

GMR 的代价是：

```text
更依赖精心调好的 IK config；
如果 task 权重或 offset 不合适，结果也会偏；
它仍然主要是运动学重定向，不等于已经解决动力学平衡、接触稳定、真实控制问题。
```

## 4. Direct mapping 为什么最容易出问题

Direct mapping 的核心在：

```text
GMR/direct mapping/run_direct_mapping.py
```

它不是求 IK，而是做一个很直接的计算：

```text
人体某个 body 当前局部旋转
- 人体这个 body 第 0 帧局部旋转
= 人体局部旋转变化

然后把这个旋转变化投影到机器人 hinge joint 的轴上。
```

代码里的关键逻辑是：

```python
local_rot = self._local_rotation(human, human_body)
delta_rot = local_rot * self.initial_local_rots[human_body].inv()
angle = dot(delta_rot.as_rotvec(), axis)
qpos[qpos_addr] = initial_qpos[qpos_addr] + direct_gain * angle
```

它的根节点也用相对变化：

```text
机器人 root 位置 = 第 0 帧机器人 root 位置 + 人体 root 相对位移
机器人 root 姿态 = 人体 root 相对旋转 * 第 0 帧机器人 root 姿态
```

这种方法为什么会和 GMR 差很多？

第一，人体关节和机器人关节不是一一对应。

人体 BVH 的骨骼结构通常是：

```text
Hips -> LeftUpLeg -> LeftLeg -> LeftFoot
```

机器人可能是：

```text
hip_yaw -> hip_roll -> hip_pitch -> knee -> ankle_pitch -> ankle_roll
```

一个人体 bone 的旋转变化不一定能对应一个机器人 hinge joint。Direct mapping 只能把旋转向量投影到机器人某根轴上，这个投影很粗糙。

第二，它不追踪手脚的空间位置。

例如人体脚尖在 BVH 里抬到某个位置，Direct mapping 并不会问：

```text
机器人脚底有没有到达这个位置？
机器人脚底有没有保持合理朝向？
```

它只是在改关节角。所以脚的位置可能明显不准。

第三，它默认不处理 joint limit。

代码里虽然有：

```text
--clip_joint_limits
```

但默认不开。这样做是为了让 direct baseline 更纯粹，但结果可能会关节超限。

第四，它不做任务权重分配。

GMR 可以说：

```text
骨盆位置很重要，权重大；
某些肢体姿态次要，权重小；
某些方向只追旋转，不追位置；
```

Direct mapping 没有这些概念。它只有关节角投影。

因此 Direct mapping 常见现象是：

```text
动作有大致趋势，但手脚不到位；
姿态可能很僵硬；
局部关节方向可能错；
机器人骨架和人体骨架差异越大，效果越差；
没有 IK 帮它修正末端位置。
```

Direct mapping 的价值是：

```text
它是最朴素、最容易理解的 baseline；
它能清楚暴露“直接复制人体旋转”为什么不适合复杂机器人；
它运行逻辑简单，方便作为对照组。
```

## 5. Basic IK 为什么比 Direct mapping 好，但可能比 GMR 更不稳定

Basic IK 的核心在：

```text
GMR/Basic IK retargeting/run_basic_ik_retargeting.py
```

它和 Direct mapping 最大不同是：

```text
Basic IK 会用 mink.solve_ik 追踪 body 的空间位置和姿态；
Direct mapping 不求 IK，只改 joint angle。
```

Basic IK 创建的是 `mink.FrameTask`：

```python
task = mink.FrameTask(
    frame_name=frame_name,
    frame_type="body",
    position_cost=pos_weight,
    orientation_cost=rot_weight,
    lm_damping=1,
)
```

然后每帧设置目标：

```python
target = mink.SE3.from_rotation_and_translation(mink.SO3(rot), pos)
task.set_target(target)
```

最后求解：

```python
velocity = mink.solve_ik(
    self.configuration,
    self.basic_tasks,
    dt,
    self.solver,
    self.damping,
    self.ik_limits,
)
self.configuration.integrate_inplace(velocity, dt)
```

所以它比 Direct mapping 更像真正的重定向，因为它会问：

```text
机器人某个 body 能不能移动到人体目标 body 的位置和姿态？
```

这就是为什么 Basic IK 通常会比 Direct mapping 更能让手、脚、躯干接近人体动作。

但是 Basic IK 和 GMR 有几个关键差异。

第一，Basic IK 明确不使用关节限制。

代码里写的是：

```python
self.ik_limits = []
```

这表示它不使用：

```text
mink.ConfigurationLimit
mink.VelocityLimit
```

因此 IK 为了追目标，可能把机器人关节转到物理上不合理的位置。

第二，Basic IK 默认只用一张 task table。

默认参数是：

```text
--task_table ik_match_table2
```

而 GMR 会根据 config 使用两阶段：

```text
ik_match_table1
ik_match_table2
```

这会导致 Basic IK 的目标组织方式更粗糙。它没有 GMR 那种“先稳定主姿态，再追细节”的流程。

第三，Basic IK 没有 GMR 完整的分阶段误差控制。

GMR 对 table1 和 table2 分别计算误差、分别迭代。Basic IK 则把选中的 task table 放到一个任务列表里一起求。

第四，Basic IK 没有速度限制。

相邻两帧如果目标变化大，IK 可以给出很大的关节变化。这样 viewer 里可能看到：

```text
关节突然跳；
手脚抽动；
身体姿态突然翻转；
```

因此 Basic IK 常见现象是：

```text
末端位置比 Direct mapping 更像人体；
但关节更可能超限；
动作连续性可能差；
某些 frame 可能为了追目标做出奇怪姿态；
脚底接触和平衡仍然没有保证。
```

## 6. 代码结构上的核心差异

### 6.1 GMR 原方法

入口：

```text
GMR/scripts/bvh_to_robot.py
```

每帧调用：

```python
qpos = retargeter.retarget(smplx_data)
```

真正逻辑在：

```text
GMR/general_motion_retargeting/motion_retarget.py
```

核心对象：

```python
GeneralMotionRetargeting
```

核心特点：

```text
使用 GMR IK config
使用 human_scale_table
使用 pos_offset / rot_offset
使用 ik_match_table1 和 ik_match_table2
使用 mink.FrameTask
使用 mink.solve_ik
使用 mink.ConfigurationLimit
可选 mink.VelocityLimit
```

### 6.2 Direct mapping

入口：

```text
GMR/direct mapping/run_direct_mapping.py
```

核心对象：

```python
DirectMapper
```

核心特点：

```text
先用 GMR 求第 0 帧 initial_qpos
使用 GMR 的人体缩放和 offset 结果
根据 GMR IK table 找 robot body 到 human body 的对应关系
遍历 MuJoCo hinge joint
计算人体局部旋转变化
投影到机器人 hinge joint axis
不调用 mink.solve_ik
默认不使用 joint limit
```

最关键差异：

```text
Direct mapping 的输出 qpos 是直接计算出来的，不是优化出来的。
```

### 6.3 Basic IK retargeting

入口：

```text
GMR/Basic IK retargeting/run_basic_ik_retargeting.py
```

核心对象：

```python
BasicIKRetargeter
```

它继承：

```python
GeneralMotionRetargeting
```

但重写了：

```text
setup_retarget_configuration
update_targets
retarget
```

核心特点：

```text
先用 GMR 求第 0 帧 initial_qpos
使用 GMR 的人体缩放和 offset 逻辑
使用 mink.FrameTask
使用 mink.solve_ik
默认只用 ik_match_table2
不使用 mink.ConfigurationLimit
不使用 mink.VelocityLimit
```

最关键差异：

```text
Basic IK 是优化出来的 qpos，但这个优化没有任何机器人关节限制。
```

## 7. 为什么同一个动作会看起来不一样

假设 BVH 里人体做一个抬腿动作。

### GMR 的处理方式

GMR 会把目标理解为：

```text
骨盆、腿、脚这些机器人 body 应该尽量靠近人体对应 body 的位置和姿态；
但是机器人关节不能超过 MuJoCo XML 里的范围；
不同 body 目标按配置权重处理；
先处理第一阶段，再处理第二阶段。
```

所以结果通常比较折中：

```text
脚可能不是完全贴合人体目标；
但机器人姿态更合理；
关节不容易超限；
整体更稳定。
```

### Direct mapping 的处理方式

Direct mapping 会把目标理解为：

```text
人体大腿局部转了多少，就把这个旋转变化投影到机器人相关 joint 上。
```

它不会检查机器人脚最终到了哪里。

所以结果可能是：

```text
腿大概抬了；
但脚的位置不对；
膝盖方向不对；
髋关节 yaw/roll/pitch 的分配不合理。
```

### Basic IK 的处理方式

Basic IK 会把目标理解为：

```text
机器人相关 body 尽量追到人体目标 body 的位置和姿态。
```

但它不管关节限制。

所以结果可能是：

```text
脚的位置比 Direct mapping 准；
但为了追脚的位置，髋关节或膝关节可能转得过大；
某些帧可能出现不自然姿态。
```

## 8. 对比表

| 项目 | GMR 原方法 | Direct mapping | Basic IK |
|---|---|---|---|
| 是否使用 IK | 是 | 否 | 是 |
| 是否追踪 body 空间位置 | 是 | 否 | 是 |
| 是否追踪 body 姿态 | 是 | 间接投影局部旋转 | 是 |
| 是否使用关节限制 | 是，`ConfigurationLimit` | 默认否，可选裁剪 | 否 |
| 是否使用速度限制 | 当前默认否，可选 | 否 | 否 |
| 是否使用两阶段 task | 是 | 否 | 默认否，只用一张表 |
| 是否依赖 GMR 配置 | 是 | 是 | 是 |
| 第 0 帧是否和 GMR 一致 | 是 | 是 | 是 |
| 最可能的问题 | 配置不佳时会偏 | 末端不到位、轴向错 | 关节超限、跳变 |
| 实验意义 | 主方法 | 最粗糙 baseline | 无限制 IK baseline |

## 9. 实验观察时应该看什么

建议你对同一个 BVH 动作、同一个机器人观察以下点：

```text
1. 第 0 帧是否一致
2. 手腕是否到达人体手部目标附近
3. 脚底是否到位、是否滑动或穿地
4. 膝盖和肘部弯曲方向是否自然
5. 髋、肩、腰是否出现异常扭转
6. 动作是否连续，有没有突然跳变
7. 关节是否明显超出机器人可实现范围
8. 躯干是否保持合理朝向
```

通常你会看到：

```text
Direct mapping:
可以看到动作大意，但末端和关节方向容易不准。

Basic IK:
手脚追踪会更像，但可能出现关节过度扭曲或突然跳变。

GMR:
更像一个经过约束和调参后的折中结果，通常更适合作为机器人动作数据。
```

## 10. 这三种方法的实验意义

Direct mapping 用来回答：

```text
如果不做 IK，只把人体旋转直接塞给机器人，会差在哪里？
```

Basic IK 用来回答：

```text
如果只做 IK 目标追踪，但不给机器人任何限制，会出现什么问题？
```

GMR 用来回答：

```text
在有配置、有权重、有 offset、有机器人关节限制的情况下，重定向效果能改善多少？
```

所以三者不是互相替代，而是形成一组很清楚的对照实验：

```text
Direct mapping 暴露骨架和关节轴不匹配的问题；
Basic IK 暴露无限制 IK 的问题；
GMR 展示加入配置和约束后的改进。
```
