# All-motion average evaluation

Evaluated motions: 9 (05_04, 111_23, 113_20, 113_21, 114_15, 124_11, 135_04, 47_01, 76_10)

Values are arithmetic means across finite per-motion results. Missing values are excluded, never replaced by zero.

| Method | Root-relative | Scale-normalised | End-effector | Orientation | Foot sliding | Max penetration | Self-collision | Joint-limit | RMS jerk | Success |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Direct Mapping | 0.9104 m | 0.7483 m | 0.7944 m | 13.16° | 3.5564 m | 0.0550 m | 19.47% | 44.71% | 236.2134 rad/s³ | 0/9 (0.0%) |
| Basic IK | 0.5674 m | 0.3405 m | 0.3328 m | 51.76° | 2.6467 m | 0.0604 m | 60.55% | 99.86% | 1385.2174 rad/s³ | 0/9 (0.0%) |
| GMR | 0.3288 m | 0.1565 m | 0.1589 m | 6.03° | 2.7308 m | 0.0696 m | 2.87% | 0.17% | 267.4938 rad/s³ | 0/9 (0.0%) |

Success shows successful motions over evaluated motions for each method.
