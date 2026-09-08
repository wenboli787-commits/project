# MuJoCo 页面和视角调整说明

本文说明为什么当前 GMR、Direct mapping、Basic IK 打开的 MuJoCo viewer 有时看起来“不好调整”，以及如果之后需要打开原生 UI 面板、关闭自动跟随或修改视角，应该改哪些地方。

注意：本文件只是调整方法文档。上一次加入的“默认打开 MuJoCo 左右面板”“新增 `--no_follow_camera` 参数”“默认视角跟随改造”已经按你的要求回退，当前代码保持原来的行为。

涉及的主要文件：

```text
GMR/general_motion_retargeting/robot_motion_viewer.py
GMR/scripts/bvh_to_robot.py
GMR/scripts/smplx_to_robot.py
GMR/scripts/vis_robot_motion.py
GMR/scripts/vis_robot_motion_dataset.py
GMR/direct mapping/run_direct_mapping.py
GMR/Basic IK retargeting/run_basic_ik_retargeting.py
```

## 1. 为什么 MuJoCo 页面不好调整

主要有三个原因。

### 1.1 相机可能被每一帧重置

核心代码在：

```text
GMR/general_motion_retargeting/robot_motion_viewer.py
```

`RobotMotionViewer.step()` 里有：

```python
if follow_camera:
    self.viewer.cam.lookat = self.data.xpos[self.model.body(self.robot_base).id]
    self.viewer.cam.distance = self.viewer_cam_distance
    self.viewer.cam.elevation = -10
```

如果调用 `step()` 时 `follow_camera=True`，程序每一帧都会把相机重新对准机器人根部，并重新设置距离和俯仰角。这样你刚用鼠标旋转、缩放或平移视角，下一帧又会被程序拉回去。

### 1.2 MuJoCo 左右 UI 面板默认隐藏

当前 viewer 启动代码是：

```python
self.viewer = mjv.launch_passive(
    model=self.model,
    data=self.data,
    show_left_ui=False,
    show_right_ui=False,
    key_callback=keyboard_callback
)
```

所以窗口默认不会显示你截图里那种 MuJoCo 原生控制面板，例如 `File`、`Option`、`Simulation`、`Watch`。

### 1.3 `camera_follow=False` 不一定会影响 `step()` 默认值

`RobotMotionViewer.__init__()` 里保存了：

```python
self.camera_follow = camera_follow
```

但是 `step()` 的默认参数仍然是：

```python
follow_camera=True
```

因此如果某个脚本创建 viewer 时传了 `camera_follow=False`，但后面调用 `env.step(...)` 时没有显式传 `follow_camera=False`，相机仍然可能继续跟随。

## 2. MuJoCo 原生鼠标操作

当相机没有被代码每帧覆盖时，MuJoCo viewer 通常可以这样操作：

```text
鼠标左键拖动：旋转视角
鼠标右键拖动：平移视角
鼠标滚轮：缩放
双击物体：把相机关注点切到该物体附近
```

不同系统、触控板和 MuJoCo 版本的快捷方式可能略有差异，但核心问题通常不是 MuJoCo 不支持调整，而是代码在每帧重置相机。

## 3. 临时关闭自动跟随

如果只是想在某个脚本里临时允许手动调整视角，可以在调用 `viewer.step()` 或 `env.step()` 时传：

```python
follow_camera=False
```

例如 Direct mapping 里如果当前是：

```python
viewer.step(
    root_pos=qpos[:3],
    root_rot=qpos[3:7],
    dof_pos=qpos[7:],
    human_motion_data=mapper.scaled_human_data,
    rate_limit=args.rate_limit,
    follow_camera=True,
)
```

可以改成：

```python
viewer.step(
    root_pos=qpos[:3],
    root_rot=qpos[3:7],
    dof_pos=qpos[7:],
    human_motion_data=mapper.scaled_human_data,
    rate_limit=args.rate_limit,
    follow_camera=False,
)
```

优点是改动最小，鼠标可以自由旋转、缩放、平移。缺点是机器人走远以后，相机不会自动跟过去。

## 4. 打开 MuJoCo 左右 UI 面板

如果你想让窗口像正常 MuJoCo viewer 一样显示左侧和右侧面板，可以修改：

```text
GMR/general_motion_retargeting/robot_motion_viewer.py
```

把：

```python
show_left_ui=False,
show_right_ui=False,
```

改成：

```python
show_left_ui=True,
show_right_ui=True,
```

如果觉得面板挡画面，也可以只打开一边：

```python
show_left_ui=True,
show_right_ui=False,
```

或：

```python
show_left_ui=False,
show_right_ui=True,
```

## 5. 让 `camera_follow` 参数真正控制默认跟随

如果你希望 `RobotMotionViewer(camera_follow=False)` 能真正影响 `step()` 默认行为，可以把 `step()` 的参数从：

```python
follow_camera=True,
```

改成：

```python
follow_camera=None,
```

然后在 `step()` 内部相机逻辑前加入：

```python
if follow_camera is None:
    follow_camera = self.camera_follow
```

这样：

```python
RobotMotionViewer(camera_follow=False)
```

就会默认不跟随；某一帧如果需要临时跟随，仍然可以显式传：

```python
viewer.step(..., follow_camera=True)
```

## 6. 如果想加命令行开关

如果以后希望运行时用参数控制相机跟随，可以给脚本加：

```python
parser.add_argument(
    "--no_follow_camera",
    action="store_true",
    help="Disable camera following so the MuJoCo view can be adjusted manually.",
)
```

然后调用 `RobotMotionViewer` 时：

```python
camera_follow=not args.no_follow_camera
```

调用 `step()` 时：

```python
follow_camera=not args.no_follow_camera
```

运行时就可以这样关闭跟随：

```bash
python "direct mapping/run_direct_mapping.py" \
  --motion_name walk1_subject1.bvh \
  --robot unitree_g1 \
  --rate_limit \
  --no_follow_camera
```

当前代码已经按你的要求回退，所以现在这些入口脚本里没有这个参数。

## 7. 调整默认相机距离和角度

默认距离来自：

```text
GMR/general_motion_retargeting/params.py
```

里面有：

```python
VIEWER_CAM_DISTANCE_DICT = {
    "unitree_g1": 2.0,
    "unitree_g1_with_hands": 2.0,
    "unitree_h1": 3.0,
    ...
}
```

如果机器人看起来太近或太远，可以改这里的数值，例如：

```python
"unitree_g1": 3.0
```

相机角度在 `robot_motion_viewer.py` 里控制：

```python
self.viewer.cam.distance = self.viewer_cam_distance
self.viewer.cam.elevation = -10
```

常用参数含义：

```text
distance   相机离目标多远，越大越远
elevation  相机俯仰角，负数表示略向下看
azimuth    相机水平旋转角
lookat     相机看的中心点
```

## 8. 折中方案：只在第一帧对准相机

如果你希望第一帧自动对准机器人，之后允许手动调视角，可以在 `RobotMotionViewer.__init__()` 中增加：

```python
self.camera_initialized = False
```

然后把每帧跟随逻辑改成：

```python
if follow_camera and not self.camera_initialized:
    self.viewer.cam.lookat = self.data.xpos[self.model.body(self.robot_base).id]
    self.viewer.cam.distance = self.viewer_cam_distance
    self.viewer.cam.elevation = -10
    self.camera_initialized = True
```

这样相机只初始化一次，不会一直覆盖你的鼠标操作。

## 9. 折中方案：低频跟随

如果机器人移动范围很大，但又不希望每一帧都重置相机，可以低频更新 `lookat`：

```python
if follow_camera and self.frame_id % 30 == 0:
    self.viewer.cam.lookat = self.data.xpos[self.model.body(self.robot_base).id]
```

注意只更新 `lookat`，不要每次都重设 `distance`、`elevation`、`azimuth`。否则手动缩放和旋转仍然会被覆盖。

## 10. 调整录制视频大小

窗口大小和录制视频大小不是同一件事。录制分辨率由创建 viewer 时的参数控制：

```python
RobotMotionViewer(
    ...,
    video_width=640,
    video_height=480,
)
```

如果要录制高清：

```python
RobotMotionViewer(
    ...,
    record_video=True,
    video_path="videos/example.mp4",
    video_width=1920,
    video_height=1080,
)
```

手动拖大 MuJoCo 窗口不一定会改变录制视频分辨率，因为视频由 `mj.Renderer` 的 `width` 和 `height` 决定。

## 11. 常见现象

| 现象 | 原因 | 调整方法 |
|---|---|---|
| 鼠标刚旋转视角马上弹回 | 每帧 `follow_camera=True` 重置相机 | 调用 `step()` 时传 `follow_camera=False` |
| 看不到 MuJoCo 控制面板 | `show_left_ui=False`, `show_right_ui=False` | 改成 `True` |
| 创建 viewer 时写了 `camera_follow=False` 仍然跟随 | `step()` 默认 `follow_camera=True` | 改成 `follow_camera=None` 并读取 `self.camera_follow` |
| 机器人走远后出画面 | 关闭跟随后相机不再移动 | 使用第一帧初始化或低频更新 `lookat` |
| 录制视频仍是 640x480 | 视频分辨率由 `video_width/video_height` 控制 | 创建 viewer 时传 1920x1080 |

## 12. 当前回退后的状态

按你的“回退上面的两次的修改”要求，当前代码状态是：

```text
1. MuJoCo 左右 UI 面板仍按原代码默认隐藏；
2. 入口脚本没有 `--no_follow_camera` 参数；
3. `RobotMotionViewer.step()` 的默认 `follow_camera` 行为已恢复；
4. 上面所有改法只作为后续需要时的手动调整参考。
```
