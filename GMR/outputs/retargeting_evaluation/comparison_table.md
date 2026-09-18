# Retargeting Method Comparison

| Method | Relative MPJPE ↓ (cm) | EE Error ↓ (cm) | Joint Limit ↓ (% frames) | Foot Sliding ↓ (cm/s) | Penetration ↓ (cm) | Self-collision ↓ (events) | Mean Jerk ↓ (rad/s³) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Direct Mapping | **18.0323** | **29.6203** | 64.8649 | 32.0199 | **1.8155** | 33.0000 | 79.7402 |
| Basic IK | 21.2027 | 35.8056 | **0.0000** | **25.1923** | 8.2993 | 29.0000 | **53.7246** |
| GMR | 22.4864 | 39.2243 | **0.0000** | 40.1306 | 9.7152 | **10.0000** | 141.9178 |

All arrows point downward: lower values are better. Values are means across motions; raw per-motion metrics remain in `summary_by_motion.csv`.
