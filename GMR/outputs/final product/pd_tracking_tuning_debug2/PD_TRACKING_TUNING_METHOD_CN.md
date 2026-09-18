# PD Tracking Tuning Method

## Pipeline

1. Replay check: verify GMR qpos can be loaded by the selected MuJoCo XML.
2. Kinematic-root PD search: force the floating root to the reference and tune joint tracking.
3. Free-root PD search: test dynamic tracking with fall detection and duration-completion scoring.
4. Final validation: rerun all motions with the best global parameters.

## Best Parameters

```json
{
  "kp": 80.0,
  "kd": 4.0,
  "torque_clip": 150.0,
  "time_scale": 1.5,
  "smooth_window": 5,
  "target_blend": 0.8,
  "root_height_offset": 0.05,
  "extra_joint_damping": 0.3,
  "ignore_actuator_ctrlrange": false,
  "mode": "pd",
  "root_mode": "free",
  "success_rate": 0.0,
  "mean_score": -3502.2506468260294
}
```

The score prioritizes success and completion before joint error. Failed trials are kept in `tuning_trials.csv`.
