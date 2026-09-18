# GMR + PD Tracking 自动调参方法

## 目标

本流程用于在已经完成 GMR 重定向的基础上，搜索一组更适合 MuJoCo 动力学仿真的 PD tracking 参数。

## 阶段

1. `stage1_replay`：只做 kinematic replay，检查 PKL、XML、qpos 维度和 NaN。
2. `stage2_kinematic`：固定 floating root，只搜索关节 PD tracking 参数。
3. `stage3_free`：释放 floating root，加入摔倒检测和完成比例评分。
4. `final_validation`：用全局最好参数重新跑验证集，并输出标准化 CSV。

## 评分原则

评分优先考虑：

- 是否成功完成；
- 是否摔倒；
- 是否完成足够动作时长；
- joint/root tracking error；
- torque/control cost；
- jerk 和 foot slip。

其中 success 和不摔倒的权重最高，误差和控制代价作为次级排序。

## 当前最好参数

```json
{
  "kp": 100.0,
  "kd": 3.0,
  "torque_clip": 200.0,
  "time_scale": 1.5,
  "smooth_window": 5,
  "target_blend": 0.8,
  "root_height_offset": 0.08,
  "extra_joint_damping": 0.5,
  "ignore_actuator_ctrlrange": false,
  "mode": "pd",
  "root_mode": "free",
  "success_rate": 0.1111111111111111,
  "mean_score": -2616.010432318187
}
```

完整 trial 记录保存在 `tuning_trials.csv`，失败 trial 保存在 `failed_trials.csv`。
