# LAFAN1 三种动作映射实验操作文档

本文档用于在同一份 LAFAN1 BVH 动作、同一套 GMR 机器人模型上对比三种方法：

1. GMR 原方法
2. Direct mapping：直接将人体局部旋转变化投影到机器人 hinge joint
3. Basic IK retargeting：不加关节限制、不加速度限制的简单 IK 重定向

我已经把正式代码放在 GMR 工程内部：

```text
D:\GMR_WORK\GMR\direct mapping
D:\GMR_WORK\GMR\Basic IK retargeting
```

机器人模型统一来自：

```text
D:\GMR_WORK\GMR\assets
```

LAFAN1 动作统一来自：

```text
D:\GMR_WORK\ubisoft-laforge-animation-dataset\lafan1\extracted
```

如果你在 Ubuntu 22.04 或 WSL Ubuntu 22.04 中运行，常见路径对应为：

```text
/mnt/d/GMR_WORK/GMR
/mnt/d/GMR_WORK/GMR/assets
/mnt/d/GMR_WORK/ubisoft-laforge-animation-dataset/lafan1/extracted
```

## 1. 文件结构

```text
GMR/
  direct mapping/
    run_direct_mapping.py
    setup_ubuntu22_04.sh
    README.md

  Basic IK retargeting/
    run_basic_ik_retargeting.py
    setup_ubuntu22_04.sh
    README.md

  scripts/
    bvh_to_robot.py
    vis_robot_motion.py

  general_motion_retargeting/
    motion_retarget.py
    params.py
    ik_configs/

  assets/
    unitree_g1/
    booster_t1_29dof/
    fourier_n1/
    ...
```

根目录下旧的错误副本已清理；请以后只运行 `D:\GMR_WORK\GMR` 里面的代码。

## 2. Ubuntu 22.04 环境配置

进入 GMR 工程：

```bash
cd /mnt/d/GMR_WORK/GMR
```

任选一个 baseline 的安装脚本即可，它们安装的是同一个 `gmr` 环境：

```bash
bash "direct mapping/setup_ubuntu22_04.sh"
conda activate gmr
```

或：

```bash
bash "Basic IK retargeting/setup_ubuntu22_04.sh"
conda activate gmr
```

脚本会执行：

```bash
conda create -n gmr python=3.10 -y
python -m pip install -e /mnt/d/GMR_WORK/GMR
python -m pip install "qpsolvers[daqp,proxqp]" daqp
conda install -c conda-forge libstdcxx-ng -y
```

如果你已经按 GMR 原 README 配好环境，可以只补装求解器：

```bash
conda activate gmr
python -m pip install "qpsolvers[daqp,proxqp]" daqp
```

## 3. 先检查路径

在 GMR 根目录运行：

```bash
python "direct mapping/run_direct_mapping.py" --check_paths_only
python "Basic IK retargeting/run_basic_ik_retargeting.py" --check_paths_only
```

正常输出应包含：

```text
assets exists: True
motion exists: True
```

如果 `motion exists` 是 `False`，说明 BVH 数据路径不对。默认动作是：

```text
dance1_subject2.bvh
```

## 4. 运行 GMR 原方法

GMR 原方法仍使用原始脚本：

```bash
python scripts/bvh_to_robot.py \
  --bvh_file /mnt/d/GMR_WORK/ubisoft-laforge-animation-dataset/lafan1/extracted/dance1_subject2.bvh \
  --format lafan1 \
  --robot unitree_g1 \
  --save_path outputs/gmr/dance1_subject2_unitree_g1_gmr.pkl \
  --rate_limit
```

如果只想生成 pkl，不打开 MuJoCo viewer，原脚本没有 `--no_visualize` 参数，建议直接使用窗口运行；或临时在远程/无显示环境中只跑我写的两个 baseline。

## 5. 运行 Direct Mapping

只生成 pkl：

```bash
python "direct mapping/run_direct_mapping.py" \
  --motion_name dance1_subject2.bvh \
  --robot unitree_g1 \
  --no_visualize
```

打开 MuJoCo viewer：

```bash
python "direct mapping/run_direct_mapping.py" \
  --motion_name dance1_subject2.bvh \
  --robot unitree_g1 \
  --rate_limit
```

快速测试前 100 帧：

```bash
python "direct mapping/run_direct_mapping.py" \
  --motion_name dance1_subject2.bvh \
  --robot unitree_g1 \
  --max_frames 100 \
  --no_visualize
```

指定完整 BVH 路径：

```bash
python "direct mapping/run_direct_mapping.py" \
  --bvh_file /mnt/d/GMR_WORK/ubisoft-laforge-animation-dataset/lafan1/extracted/walk1_subject1.bvh \
  --robot unitree_g1 \
  --no_visualize
```

默认输出：

```text
GMR/outputs/direct_mapping/
```

常用参数：

```text
--direct_gain 1.0       直接映射角度增益
--clip_joint_limits     可选：裁剪到 MuJoCo XML 的 joint range
--max_frames 100        只跑前 100 帧
--save_path xxx.pkl     指定输出 pkl
--quiet                 减少打印
```

注意：为了保留“直接映射”的实验意义，默认不裁剪关节范围。

## 6. 运行 Basic IK Retargeting

只生成 pkl：

```bash
python "Basic IK retargeting/run_basic_ik_retargeting.py" \
  --motion_name dance1_subject2.bvh \
  --robot unitree_g1 \
  --no_visualize
```

打开 MuJoCo viewer：

```bash
python "Basic IK retargeting/run_basic_ik_retargeting.py" \
  --motion_name dance1_subject2.bvh \
  --robot unitree_g1 \
  --rate_limit
```

快速测试前 100 帧：

```bash
python "Basic IK retargeting/run_basic_ik_retargeting.py" \
  --motion_name dance1_subject2.bvh \
  --robot unitree_g1 \
  --max_frames 100 \
  --no_visualize
```

默认输出：

```text
GMR/outputs/basic_ik_retargeting/
```

常用参数：

```text
--task_table ik_match_table2  默认只使用 GMR 第二阶段任务表
--max_iter 10                每帧 IK 最大迭代次数
--damping 0.5                IK 阻尼
--solver daqp                mink/qpsolvers 求解器
--max_frames 100             只跑前 100 帧
--save_path xxx.pkl          指定输出 pkl
--quiet                      减少打印
```

## 7. 播放生成的 pkl

Direct mapping：

```bash
python scripts/vis_robot_motion.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/direct_mapping/dance1_subject2_unitree_g1_direct_mapping.pkl
```

Basic IK：

```bash
python scripts/vis_robot_motion.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/basic_ik_retargeting/dance1_subject2_unitree_g1_basic_ik.pkl
```

GMR 原方法：

```bash
python scripts/vis_robot_motion.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/gmr/dance1_subject2_unitree_g1_gmr.pkl
```

## 8. 三种方法如何保证初始动作一致

两个新 baseline 都会先对 BVH 第 0 帧调用 GMR：

```text
initial_qpos = GMR(...).retarget(frames[0])
```

然后：

1. Direct mapping 第 0 帧直接返回这个 `initial_qpos`
2. Basic IK 先把 mink configuration 重置到这个 `initial_qpos`，第 0 帧也直接返回它
3. GMR 原方法本身第 0 帧就是这个 retarget 结果

因此三种方法的第 0 帧机器人姿态一致，方便你对比后续动作质量。

生成的 pkl 里额外保存了 `metadata` 字段，记录方法名、源 BVH、机器人、第一帧种子来源等信息。`scripts/vis_robot_motion.py` 会忽略额外字段，所以仍然可以正常播放。

## 9. Direct Mapping 代码解释

代码文件：

```text
GMR/direct mapping/run_direct_mapping.py
```

核心思路是“不给优化器，直接把人体关节旋转变化塞给机器人关节”。

主要流程：

1. 从 LAFAN1 BVH 读取每一帧人体骨骼全局位置和全局旋转
2. 创建一个 GMR retargeter，只用它读取机器人 XML、IK 配置、人体缩放和旋转 offset
3. 用 GMR 对第 0 帧求出 `initial_qpos`
4. 根据 GMR 的 `ik_match_table1/2` 找到机器人 body 和人体 body 的对应关系
5. 对每个 MuJoCo hinge joint，寻找它所在 body 子树里最近的已匹配机器人 body
6. 对人体 body 计算局部旋转：

```text
local_rotation = inverse(parent_global_rotation) * body_global_rotation
```

7. 当前帧局部旋转减去第 0 帧局部旋转，得到人体该部位的相对旋转变化
8. 把这个旋转变化投影到机器人 hinge joint 的 axis 上：

```text
joint_angle = initial_joint_angle + dot(delta_rotation_vector, robot_joint_axis)
```

9. 根节点位置和朝向使用人体 root 相对第 0 帧的平移、旋转变化
10. 保存为和 GMR 一样格式的 pkl

这个方法的优点：

```text
逻辑最简单、速度快、最适合作为粗糙 baseline。
```

这个方法的缺点：

```text
没有 IK 优化，不关心手脚目标是否真的到位；
人体骨架和机器人骨架轴向不完全一致时，误差会很明显；
默认不处理接触、平衡、关节速度、动力学稳定性。
```

## 10. Basic IK Retargeting 代码解释

代码文件：

```text
GMR/Basic IK retargeting/run_basic_ik_retargeting.py
```

核心思路是“只保留最基础的 IK 目标追踪，不加任何限制项”。

它继承 GMR 的读取配置、缩放人体、offset 人体目标等逻辑，但重写 IK 配置部分：

```text
self.ik_limits = []
```

也就是说它不使用：

```text
mink.ConfigurationLimit
mink.VelocityLimit
```

主要流程：

1. 读取同一个 LAFAN1 BVH
2. 读取同一个 GMR 机器人 XML 和 LAFAN1 IK config
3. 用 GMR 对第 0 帧求 `initial_qpos`
4. 创建 Basic IK retargeter
5. 把 mink configuration 重置到 `initial_qpos`
6. 默认只使用 `ik_match_table2` 创建 `mink.FrameTask`
7. 每帧把人体目标 body 的位置和姿态设置给对应机器人 body task
8. 调用 `mink.solve_ik`
9. 不做 joint limit、不做 velocity limit、不做额外动力学约束
10. 保存为同样格式的 pkl

这个方法的优点：

```text
比 direct mapping 更能追踪手、脚、骨盆、躯干等空间目标；
结构简单，可以单独观察“纯 IK 追目标”的效果。
```

这个方法的缺点：

```text
因为没有关节限制，可能出现关节超限；
因为没有速度限制，可能出现突然跳变；
因为没有接触和平衡约束，脚底可能滑动、穿地，身体可能不稳定；
IK 目标本身冲突时，结果可能很怪。
```

## 11. 当前支持的 LAFAN1 机器人

两个新 baseline 读取的是：

```text
IK_CONFIG_DICT["bvh_lafan1"]
```

当前支持：

```text
unitree_g1
unitree_g1_with_hands
booster_t1_29dof
fourier_n1
stanford_toddy
engineai_pm01
pal_talos
```

如果传入不支持的机器人，脚本会打印支持列表并报错。

## 12. 建议的对比实验方式

建议先固定：

```text
motion: dance1_subject2.bvh
robot : unitree_g1
fps   : 30
```

先跑短片段：

```bash
python "direct mapping/run_direct_mapping.py" --motion_name dance1_subject2.bvh --robot unitree_g1 --max_frames 100 --no_visualize
python "Basic IK retargeting/run_basic_ik_retargeting.py" --motion_name dance1_subject2.bvh --robot unitree_g1 --max_frames 100 --no_visualize
```

确认能生成 pkl 后，再跑完整动作并打开 viewer 对比：

```bash
python "direct mapping/run_direct_mapping.py" --motion_name dance1_subject2.bvh --robot unitree_g1 --rate_limit
python "Basic IK retargeting/run_basic_ik_retargeting.py" --motion_name dance1_subject2.bvh --robot unitree_g1 --rate_limit
```

观察重点：

```text
手腕和脚踝是否到位
脚底是否滑动或穿地
躯干是否保持合理朝向
关节是否超限或抽动
动作是否连续
初始姿态是否完全一致
```

## 13. 常见问题

如果报 `ModuleNotFoundError: mujoco` 或 `ModuleNotFoundError: mink`：

```bash
cd /mnt/d/GMR_WORK/GMR
bash "direct mapping/setup_ubuntu22_04.sh"
conda activate gmr
```

如果报 `Solver daqp is not installed`：

```bash
python -m pip install "qpsolvers[daqp]" daqp
```

如果 MuJoCo viewer 打不开：

```text
先用 --no_visualize 生成 pkl；
确认你是在 Ubuntu 桌面或 WSLg 图形环境中运行；
远程服务器通常需要额外配置 DISPLAY/EGL。
```

如果路径找不到：

```bash
python "direct mapping/run_direct_mapping.py" --check_paths_only
python "Basic IK retargeting/run_basic_ik_retargeting.py" --check_paths_only
```
