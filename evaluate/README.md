# Humanoid Retargeting Evaluation

`evaluate` compares the already-generated outputs of Direct Mapping, Basic IK,
and GMR / Constrained IK. It does **not** implement a retargeting method.

All inputs first become `CanonicalMotion`, then simulator-independent metrics
run on that format. MuJoCo integration is optional and isolated in
`simulator_adapters/mujoco_adapter.py`; Isaac logs are read offline and do not
require Isaac Sim/Lab to be installed.

## Quick start

```bash
cd ~/GMR/evaluate                 # Change this to your actual Ubuntu project path.
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python examples/run_dummy_evaluation.py
```

This creates `examples/dummy_evaluation_output/` with CSV, JSON, Markdown and
PNG plots. Read the full Chinese guide: [操作手册_CN.md](操作手册_CN.md).

## Normal use

```bash
python evaluate_retargeting.py \
  --simulator offline \
  --ref_motion /data/motions/reference_motion.npz \
  --direct_motion /data/results/direct_mapping_result.pkl \
  --ik_motion /data/results/basic_ik_result.pkl \
  --gmr_motion /data/results/gmr_result.pkl \
  --mapping config/my_robot_mapping.yaml \
  --out_dir /data/results/evaluation_offline
```

Start from `config/eval_mapping_template.yaml` and replace its robot body and
reference joint names. Existing GMR Direct Mapping / Basic IK pickles already
contain compatible `fps`, `root_pos`, `root_rot` (xyzw), and `dof_pos` fields.

If an input does not contain the data a metric needs, that metric is reported
as `unavailable`; evaluation continues and records a warning instead of
fabricating a zero. See the manual for MuJoCo, Isaac, reference-file, contact,
normalization, and troubleshooting details.
