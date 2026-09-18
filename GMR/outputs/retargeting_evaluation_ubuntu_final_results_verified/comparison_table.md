# Retargeting Method Comparison

| Method | Relative MPJPE ↓ (cm) | EE Error ↓ (cm) | Joint Limit ↓ (% frames) | Foot Sliding ↓ (cm/s) | Penetration ↓ (cm) | Self-collision ↓ (events) | Mean Jerk ↓ (rad/s³) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Direct Mapping | 20.8267 | 35.0929 | 44.7083 | 32.7419 | **5.5047** | 30.4444 | **68.1446** |
| Basic IK | **18.8777** | **27.3938** | 100.0000 | 26.7907 | 6.7817 | 138.1111 | 181.8706 |
| GMR | 19.9388 | 30.7947 | **0.1700** | **25.5997** | 6.9584 | **7.6667** | 76.0834 |

All arrows point downward: lower values are better. Values are means across motions; raw per-motion metrics remain in `summary_by_motion.csv`.
