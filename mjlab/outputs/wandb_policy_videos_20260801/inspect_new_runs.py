from __future__ import annotations

import sys

import wandb


api = wandb.Api(timeout=120)
for run_id in sys.argv[1:]:
    run_path = f"wenboli787-university-of-glasgow/mjlab/{run_id}"
    run = api.run(run_path)
    print(f"=== {run_id} ===")
    print(f"name: {run.name}")
    print(f"job_type: {run.job_type}")
    print("used_artifacts:")
    for artifact in run.used_artifacts():
        print(
            f"  {artifact.type}: name={artifact.name} "
            f"entity={getattr(artifact, 'entity', None)} "
            f"project={getattr(artifact, 'project', None)} "
            f"qualified={getattr(artifact, 'qualified_name', None)}"
        )
    config = dict(run.config)
    env_cfg = config.get("env_cfg", {})
    motion_cfg = env_cfg.get("commands", {}).get("motion", {})
    print(f"task: {config.get('task')}")
    print(f"motion_file: {motion_cfg.get('motion_file')}")
    print(f"episode_length_s: {env_cfg.get('episode_length_s')}")
    observations = env_cfg.get("observations", {}).get("actor", {}).get("terms", {})
    print("special_observations:")
    for key, value in observations.items():
        if "future" in key.lower() or "history" in key.lower():
            print(f"  {key}: {value.get('params')}")
