# PD Tracking Operation Guide

## Run A Single Tuned Trial

```bash
cd /mnt/d/GMR_WORK/GMR
python scripts/run_pd_tracking_from_gmr.py \
  --motion_pkl "outputs/final product/pkl/13_01_unitree_g1_gmr.pkl" \
  --xml_path "assets/unitree_g1/g1_mocap_29dof.xml" \
  --save_dir "outputs/final product/pkl PD tracking debug" \
  --mode pd \
  --root_mode free \
  --kp 80.0 \
  --kd 4.0 \
  --torque_clip 150.0 \
  --time_scale 1.5 \
  --smooth_window 5
```

Use `--smooth_ref` when `smooth_window > 1`. The Unitree G1 XML in this workspace uses `ctrlrange="-1 1"` for torque motors; `--ignore_actuator_ctrlrange` is available for debugging normalized actuator limits.
