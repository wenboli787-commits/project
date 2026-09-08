# NPZ 动作文件接入三种映射方法的可行性文档

本文说明如何让 `npz` 动作文件使用三种动作映射方法：

1. GMR 原方法
2. Direct mapping，直接映射
3. Basic IK retargeting，无限制简单 IK 重定向

结论先说：

```text
可行。

GMR 原方法已经基本支持 SMPL-X npz；
Basic IK 改动较小，主要是把 BVH loader 换成 SMPL-X npz loader；
Direct mapping 改动中等，主要是把 LAFAN1 的骨架父子关系换成 SMPL-X 的骨架父子关系。
```

但这里的 `npz` 需要先明确：最推荐支持的是 **SMPL-X/AMASS stageii 风格的 npz**，不是任意结构的 npz。

## 1. 当前项目对 npz 的已有支持

GMR 已经有 SMPL-X npz 入口：

```text
GMR/scripts/smplx_to_robot.py
```

它调用：

```text
GMR/general_motion_retargeting/utils/smpl.py
```

关键函数：

```python
load_smplx_file(...)
get_smplx_data_offline_fast(...)
```

`load_smplx_file` 当前期望 npz 中至少包含：

```text
pose_body
root_orient
trans
betas
gender
mocap_frame_rate
```

其中：

```text
pose_body       人体身体关节旋转，通常 shape 为 [N, 63]
root_orient     根节点朝向，shape 为 [N, 3]
trans           根节点平移，shape 为 [N, 3]
betas           体型参数
gender          SMPL-X body model 性别
mocap_frame_rate 原始动作帧率
```

`get_smplx_data_offline_fast` 会把 SMPL-X body model 输出转换成 GMR 统一使用的人体 frame 字典：

```python
{
    "pelvis": (position, orientation),
    "left_hip": (position, orientation),
    "right_hip": (position, orientation),
    ...
}
```

这个结构和 BVH loader 输出的结构本质一样，都是：

```text
body_name -> 位置 + 姿态
```

所以从架构上看，三种方法都可以接入 npz。

## 2. 必要外部资源

SMPL-X npz 不像 BVH 那样只靠文件本身就能得到完整人体关节位置。它需要 SMPL-X body model。

当前代码默认读取：

```text
GMR/assets/body_models
```

推荐目录结构：

```text
GMR/assets/body_models/smplx/
  SMPLX_NEUTRAL.pkl
  SMPLX_FEMALE.pkl
  SMPLX_MALE.pkl
```

如果没有 body model，GMR 无法从 `pose_body/root_orient/trans/betas` 正确恢复人体关节位置。

## 3. 三种方法接入 npz 的可行性评级

| 方法 | 可行性 | 改动量 | 主要原因 |
|---|---:|---:|---|
| GMR 原方法 | 高 | 低 | 已有 `smplx_to_robot.py` 和 `smplx` IK config |
| Basic IK | 高 | 中低 | 复用 SMPL-X loader，把 `src_human` 从 `bvh_lafan1` 换成 `smplx` |
| Direct mapping | 中高 | 中 | 需要 SMPL-X parent map，替换当前写死的 LAFAN1 parent map |

## 4. 方案核心：做一个统一动作读取层

当前 BVH baseline 脚本里有比较明显的 BVH 假设：

```text
Direct mapping:
默认 motion_dir 指向 LAFAN1 BVH
src_human 写死为 bvh_lafan1
父子关系 LAFAN_PARENT 写死为 LAFAN1 骨架

Basic IK:
默认 motion_dir 指向 LAFAN1 BVH
src_human 写死为 bvh_lafan1
使用 bvh_lafan1 的 IK config
```

推荐增加一个统一动作读取层，例如：

```text
GMR/scripts/motion_source_loader.py
```

它提供统一接口：

```python
frames, actual_human_height, motion_fps, src_human, parent_map = load_motion_source(
    motion_file=...,
    motion_format="lafan1_bvh" 或 "smplx_npz",
    smplx_body_model_path=...,
    target_fps=30,
)
```

这样三种方法不直接关心输入是 BVH 还是 NPZ，只关心：

```text
frames: 每一帧人体 body 的位置和姿态
actual_human_height: 人体身高
motion_fps: 对齐后的帧率
src_human: GMR 配置名，比如 bvh_lafan1 或 smplx
parent_map: 人体骨架父子关系
```

这是最干净、最可维护的方案。

## 5. GMR 原方法如何支持 npz

GMR 原方法已经基本支持。

入口：

```text
GMR/scripts/smplx_to_robot.py
```

核心流程：

```python
smplx_data, body_model, smplx_output, actual_human_height = load_smplx_file(
    args.smplx_file,
    SMPLX_FOLDER,
)

smplx_data_frames, aligned_fps = get_smplx_data_offline_fast(
    smplx_data,
    body_model,
    smplx_output,
    tgt_fps=30,
)

retarget = GMR(
    actual_human_height=actual_human_height,
    src_human="smplx",
    tgt_robot=args.robot,
)
```

GMR 会使用：

```text
IK_CONFIG_DICT["smplx"][robot]
```

也就是这些配置：

```text
GMR/general_motion_retargeting/ik_configs/smplx_to_g1.json
GMR/general_motion_retargeting/ik_configs/smplx_to_h1.json
GMR/general_motion_retargeting/ik_configs/smplx_to_t1_29dof.json
...
```

所以 GMR 原方法对 npz 的改动建议不是重写算法，而是补强脚本体验：

```text
1. 增加 --no_visualize
2. 增加 --max_frames
3. 修正当前循环从 i=1 开始的问题，保证第 0 帧也被保存和显示
4. 保存 metadata
5. 输出路径按 outputs/gmr_npz 组织
```

可行性判断：

```text
非常可行。核心能力已经存在。
```

## 6. Basic IK 如何支持 npz

当前 Basic IK 脚本：

```text
GMR/Basic IK retargeting/run_basic_ik_retargeting.py
```

现在写死了：

```python
src_human = "bvh_lafan1"
frames, actual_human_height = load_bvh_file(...)
```

要支持 npz，需要改成根据参数选择 loader。

新增参数建议：

```text
--motion_format bvh_lafan1 或 smplx_npz
--smplx_file xxx.npz
--smplx_body_model_dir assets/body_models
--target_fps 30
```

当 `motion_format=smplx_npz` 时：

```python
smplx_data, body_model, smplx_output, actual_human_height = load_smplx_file(
    args.smplx_file,
    args.smplx_body_model_dir,
)

frames, aligned_fps = get_smplx_data_offline_fast(
    smplx_data,
    body_model,
    smplx_output,
    tgt_fps=args.target_fps,
)

src_human = "smplx"
```

然后 Basic IK 继续使用：

```python
IK_CONFIG_DICT[src_human][args.robot]
```

也就是：

```text
IK_CONFIG_DICT["smplx"][robot]
```

Basic IK 的 IK 逻辑本身不需要大改。因为它已经是：

```text
读取 GMR 的 ik_match_table
创建 mink.FrameTask
设置目标
调用 mink.solve_ik
不使用限制
```

SMPL-X frame 的 body name 正好能和 `smplx_to_*.json` 对上，比如：

```text
pelvis
left_hip
right_hip
left_knee
right_knee
left_foot
right_foot
spine3
left_shoulder
right_shoulder
left_elbow
right_elbow
left_wrist
right_wrist
```

可行性判断：

```text
高。主要工作是输入层适配，不是 IK 算法重写。
```

## 7. Direct mapping 如何支持 npz

Direct mapping 当前依赖 LAFAN1 的父子关系：

```python
LAFAN_PARENT = {
    "Hips": None,
    "LeftUpLeg": "Hips",
    "LeftLeg": "LeftUpLeg",
    ...
}
```

它用这个 parent map 计算局部旋转：

```python
local_rotation = inverse(parent_global_rotation) * body_global_rotation
```

SMPL-X npz 的 body name 和 LAFAN1 不同。SMPL-X 使用：

```text
pelvis
left_hip
right_hip
spine1
left_knee
right_knee
spine2
left_ankle
right_ankle
spine3
left_foot
right_foot
neck
left_collar
right_collar
head
left_shoulder
right_shoulder
left_elbow
right_elbow
left_wrist
right_wrist
...
```

所以 Direct mapping 支持 npz 的关键是构建：

```python
SMPLX_PARENT = {
    "pelvis": None,
    "left_hip": "pelvis",
    "right_hip": "pelvis",
    "spine1": "pelvis",
    "left_knee": "left_hip",
    "right_knee": "right_hip",
    "spine2": "spine1",
    "left_ankle": "left_knee",
    "right_ankle": "right_knee",
    "spine3": "spine2",
    "left_foot": "left_ankle",
    "right_foot": "right_ankle",
    "neck": "spine3",
    "left_collar": "spine3",
    "right_collar": "spine3",
    "head": "neck",
    "left_shoulder": "left_collar",
    "right_shoulder": "right_collar",
    "left_elbow": "left_shoulder",
    "right_elbow": "right_shoulder",
    "left_wrist": "left_elbow",
    "right_wrist": "right_elbow",
}
```

更稳妥的做法不是手写，而是从 SMPL-X body model 获取：

```python
joint_names = JOINT_NAMES[: len(body_model.parents)]
parents = body_model.parents
parent_map = {
    joint_names[i]: None if parents[i] < 0 else joint_names[parents[i]]
    for i in range(len(joint_names))
}
```

这样可以避免名字或 parent index 写错。

Direct mapping 还需要把：

```python
src_human = "bvh_lafan1"
```

改成：

```python
src_human = "smplx"
```

这样 `_collect_robot_body_matches()` 才会读取：

```text
smplx_to_*.json
```

而不是：

```text
bvh_lafan1_to_*.json
```

Direct mapping 的核心计算逻辑可以保留：

```python
local_rot = self._local_rotation(human, human_body)
delta_rot = local_rot * self.initial_local_rots[human_body].inv()
angle = dot(delta_rot.as_rotvec(), robot_joint_axis)
qpos[qpos_addr] = initial_qpos[qpos_addr] + direct_gain * angle
```

但是 `_available_parent()` 必须改成使用传入的 `parent_map`：

```python
def _available_parent(self, human, body_name):
    parent = self.parent_map.get(body_name)
    while parent is not None:
        if parent in human:
            return parent
        parent = self.parent_map.get(parent)
    return None
```

可行性判断：

```text
中高。算法不用重写，但必须把 LAFAN1 骨架假设抽出来。
```

## 8. 推荐最终脚本结构

最推荐不要复制三份 npz 脚本，而是把当前两个 baseline 脚本参数化。

推荐结构：

```text
GMR/scripts/motion_source_loader.py
GMR/direct mapping/run_direct_mapping.py
GMR/Basic IK retargeting/run_basic_ik_retargeting.py
GMR/scripts/smplx_to_robot.py
```

### 8.1 motion_source_loader.py

职责：

```text
统一读取 BVH 或 NPZ；
返回 frames、height、fps、src_human、parent_map。
```

伪代码：

```python
def load_motion_source(args):
    if args.motion_format == "bvh_lafan1":
        frames, height = load_bvh_file(args.bvh_file, format="lafan1")
        return frames, height, args.motion_fps, "bvh_lafan1", LAFAN_PARENT

    if args.motion_format == "smplx_npz":
        smplx_data, body_model, smplx_output, height = load_smplx_file(
            args.smplx_file,
            args.smplx_body_model_dir,
        )
        frames, fps = get_smplx_data_offline_fast(
            smplx_data,
            body_model,
            smplx_output,
            tgt_fps=args.target_fps,
        )
        parent_map = build_smplx_parent_map(body_model)
        return frames, height, fps, "smplx", parent_map
```

### 8.2 GMR 原方法

可以保留 `scripts/smplx_to_robot.py`，也可以统一成：

```text
scripts/motion_to_robot.py
```

参数：

```text
--motion_format smplx_npz
--smplx_file xxx.npz
--robot unitree_g1
--save_path outputs/gmr_npz/xxx.pkl
--no_visualize
```

### 8.3 Direct mapping

新增参数：

```text
--motion_format smplx_npz
--smplx_file xxx.npz
--smplx_body_model_dir assets/body_models
--target_fps 30
```

内部变化：

```text
从 load_motion_source 获取 src_human 和 parent_map；
DirectMapper 初始化时接收 parent_map；
src_human 不再写死。
```

### 8.4 Basic IK

新增参数同上。

内部变化：

```text
从 load_motion_source 获取 src_human；
BasicIKRetargeter 使用 src_human="smplx"；
其它 IK 求解逻辑不变。
```

## 9. 三种方法使用 npz 后的初始动作一致性

为了三种方法可比，仍然沿用现在 baseline 的策略：

```text
先用 GMR 对 npz 第 0 帧求 initial_qpos；
Direct mapping 第 0 帧直接返回 initial_qpos；
Basic IK reset 到 initial_qpos，第 0 帧直接返回；
GMR 原方法第 0 帧本身就是 initial_qpos。
```

对应伪代码：

```python
seed_gmr = GMR(
    src_human="smplx",
    tgt_robot=args.robot,
    actual_human_height=actual_human_height,
)

initial_qpos = seed_gmr.retarget(copy.deepcopy(frames[0]))
```

这样 BVH 实验和 NPZ 实验都能保持同样的对比原则。

## 10. NPZ 格式兼容风险

这里需要特别注意：不是所有 `.npz` 都是同一种结构。

### 10.1 推荐直接支持的 npz

推荐优先支持 SMPL-X stageii 风格 npz：

```text
pose_body
root_orient
trans
betas
gender
mocap_frame_rate
```

这类文件和当前 `load_smplx_file` 匹配。

### 10.2 需要转换的 npz

有些 AMASS 文件可能是 SMPL-H 或 SMPL 格式，字段可能是：

```text
poses
trans
betas
gender
mocap_framerate
```

这种不能直接喂给当前 `load_smplx_file`，需要先转换成当前 SMPL-X loader 需要的字段。

可能的转换逻辑：

```text
root_orient = poses[:, 0:3]
pose_body = poses[:, 3:66]
mocap_frame_rate = mocap_framerate
```

但这只适合关节定义兼容的情况。更严谨的做法是先转换到 SMPL-X 参数。

### 10.3 不可直接支持的 npz

如果 npz 只是任意数组，比如：

```text
qpos
joint_positions
xyz
rotations
```

那它不一定是人体模型参数。必须先写专门 adapter，把它转换成：

```text
body_name -> position + orientation
```

否则三种方法都不知道每个人体 body 的位置和姿态。

## 11. 预期效果差异

NPZ 接入后三种方法的差异仍然和 BVH 实验类似。

### GMR 原方法

预期：

```text
最稳定；
最符合机器人关节限制；
更适合作为主结果。
```

原因：

```text
使用 smplx_to_*.json；
使用两阶段 IK；
使用 ConfigurationLimit；
使用专门为 SMPL-X 调过的 body offset 和权重。
```

### Direct mapping

预期：

```text
能反映动作大趋势；
但末端位置可能不准；
机器人关节轴和 SMPL-X 局部旋转不完全对应时，误差明显。
```

原因：

```text
只做局部旋转变化投影；
不追踪 body 空间目标；
不做 IK 优化；
默认不做关节限制。
```

### Basic IK

预期：

```text
手脚、骨盆等 body 位置会比 Direct mapping 更接近人体；
但容易关节超限、动作跳变或姿态不自然。
```

原因：

```text
使用 IK 追目标；
但不使用 ConfigurationLimit；
不使用 VelocityLimit；
默认只使用一张 task table。
```

## 12. 开发步骤建议

推荐分四步做，不要一次全部改。

### 第一步：验证 GMR 原方法 npz

目标：

```text
确认 npz 文件能被现有 smplx_to_robot.py 读取。
```

命令示例：

```bash
cd /mnt/d/GMR_WORK/GMR
python scripts/smplx_to_robot.py \
  --smplx_file /path/to/motion.npz \
  --robot unitree_g1 \
  --save_path outputs/gmr_npz/motion_unitree_g1_gmr.pkl \
  --rate_limit
```

如果这一步失败，先不要改 Direct mapping 和 Basic IK。因为说明 npz 本身或 SMPL-X body model 没准备好。

### 第二步：抽象 motion_source_loader

目标：

```text
让 BVH 和 NPZ 都能输出同一种 frames 结构。
```

完成后先写一个检查脚本打印：

```text
frame count
fps
actual_human_height
src_human
first frame body names
parent_map size
```

### 第三步：改 Basic IK

Basic IK 对 parent map 不敏感，所以优先改它。

目标：

```text
Basic IK 能跑 smplx_npz；
第 0 帧和 GMR npz 第 0 帧一致；
能保存 pkl。
```

### 第四步：改 Direct mapping

Direct mapping 最后改，因为它需要处理 SMPL-X parent map。

目标：

```text
Direct mapping 能用 SMPL-X 局部旋转；
第 0 帧和 GMR npz 第 0 帧一致；
能保存 pkl。
```

## 13. 验收标准

建议用同一个 npz 文件、同一个机器人做验收。

### 13.1 路径和格式验收

```text
能读取 npz；
能找到 SMPL-X body model；
能打印 frames 数量；
能打印支持的 body names；
```

### 13.2 三方法输出验收

每种方法都应生成：

```text
root_pos
root_rot
dof_pos
fps
metadata
```

保存路径建议：

```text
outputs/gmr_npz/
outputs/direct_mapping_npz/
outputs/basic_ik_npz/
```

### 13.3 初始帧一致性验收

检查三种方法第 0 帧：

```text
root_pos[0] 一致
root_rot[0] 一致
dof_pos[0] 一致
```

允许极小浮点误差：

```text
1e-6 ~ 1e-5
```

### 13.4 可视化验收

用：

```bash
python scripts/vis_robot_motion.py \
  --robot unitree_g1 \
  --robot_motion_path outputs/xxx.pkl
```

观察：

```text
GMR 是否稳定；
Direct mapping 是否有明显轴向错误；
Basic IK 是否出现关节超限或跳变；
三者第 0 帧是否一致。
```

## 14. 推荐命令设计

最终希望三种方法命令形式尽量统一。

### GMR

```bash
python scripts/smplx_to_robot.py \
  --smplx_file /path/to/motion.npz \
  --robot unitree_g1 \
  --save_path outputs/gmr_npz/motion_unitree_g1_gmr.pkl
```

### Direct mapping

```bash
python "direct mapping/run_direct_mapping.py" \
  --motion_format smplx_npz \
  --smplx_file /path/to/motion.npz \
  --robot unitree_g1 \
  --save_path outputs/direct_mapping_npz/motion_unitree_g1_direct.pkl \
  --no_visualize
```

### Basic IK

```bash
python "Basic IK retargeting/run_basic_ik_retargeting.py" \
  --motion_format smplx_npz \
  --smplx_file /path/to/motion.npz \
  --robot unitree_g1 \
  --save_path outputs/basic_ik_npz/motion_unitree_g1_basic_ik.pkl \
  --no_visualize
```

## 15. 总结

让 npz 使用三种方法是可行的，最佳路线是：

```text
1. 不改变三种方法的核心算法；
2. 增加统一 motion_source_loader；
3. 让 BVH 和 NPZ 都转换成同一种 frame dict；
4. Direct mapping 额外接收 parent_map；
5. Basic IK 和 GMR 通过 src_human="smplx" 使用现有 smplx_to_*.json；
6. 保持三种方法第 0 帧都来自 GMR initial_qpos。
```

最终得到的实验会比现在只使用 LAFAN1 BVH 更完整：

```text
BVH 实验说明三种方法在 LAFAN1 骨架上的差异；
NPZ 实验说明三种方法在 SMPL-X/AMASS 动作上的差异；
两组实验都能保持同一个机器人、同一个初始姿态、同一套评价方式。
```
