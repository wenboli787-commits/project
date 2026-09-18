import csv
import json
import subprocess
from pathlib import Path

repo = Path('/mnt/d/GMR_WORK/GMR')
python = Path('/home/ubuntu/miniconda3/envs/gmr/bin/python')
run_script = repo / 'scripts' / 'run_pd_tracking_from_gmr.py'
motion_dir = Path('outputs/final results/pkl gmr')
xml_path = Path('assets/unitree_g1/g1_mocap_29dof.xml')
out_root = repo / 'outputs/final results/pd tracking pd grid search kinematic'
logs_dir = out_root / 'logs'
out_root.mkdir(parents=True, exist_ok=True)
logs_dir.mkdir(parents=True, exist_ok=True)

kp_values = [50, 70, 90, 110, 130, 150]
kd_values = [2, 3, 4, 5, 6, 8]
rows = []

def as_float(value, default=float('nan')):
    try:
        if value in ('', None):
            return default
        return float(value)
    except Exception:
        return default

def as_bool(value):
    return str(value).strip().lower() in {'true', '1', 'yes'}

for kp in kp_values:
    for kd in kd_values:
        label = f'kp_{kp}_kd_{kd}'
        save_dir = out_root / label
        log_path = logs_dir / f'{label}.log'
        cmd = [
            str(python), str(run_script),
            '--motion_dir', str(motion_dir),
            '--xml_path', str(xml_path),
            '--save_dir', str(save_dir.relative_to(repo)),
            '--mode', 'pd',
            '--root_mode', 'kinematic',
            '--kp', str(kp),
            '--kd', str(kd),
            '--torque_clip', '250',
            '--time_scale', '1.6',
            '--smooth_ref',
            '--smooth_window', '3',
            '--target_blend', '0.7',
            '--root_height_offset', '0.08',
            '--extra_joint_damping', '0.7',
            '--sim_dt', '0.002',
            '--max_time', '3.0',
        ]
        print(f'[grid-kinematic] running {label}', flush=True)
        result = subprocess.run(cmd, cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log_path.write_text(result.stdout, encoding='utf-8')
        summary_path = save_dir / 'tracking_comparison_ready_summary.csv'
        motion_rows = []
        if summary_path.exists():
            with summary_path.open(newline='', encoding='utf-8') as f:
                motion_rows = list(csv.DictReader(f))
        success_count = sum(as_bool(r.get('success')) for r in motion_rows)
        count = len(motion_rows)
        mean_score = sum(as_float(r.get('score'), -10000.0) for r in motion_rows) / count if count else -10000.0
        mean_completion = sum(as_float(r.get('duration_completed_ratio')) for r in motion_rows) / count if count else float('nan')
        mean_joint_error = sum(as_float(r.get('mean_joint_position_error')) for r in motion_rows) / count if count else float('nan')
        mean_max_joint_error = sum(as_float(r.get('max_joint_position_error')) for r in motion_rows) / count if count else float('nan')
        row = {
            'kp': kp,
            'kd': kd,
            'root_mode': 'kinematic',
            'max_time': 3.0,
            'torque_clip': 250,
            'time_scale': 1.6,
            'smooth_window': 3,
            'target_blend': 0.7,
            'root_height_offset': 0.08,
            'extra_joint_damping': 0.7,
            'motions': count,
            'success_count': success_count,
            'success_rate': success_count / count if count else 0.0,
            'mean_score': mean_score,
            'mean_completion': mean_completion,
            'mean_joint_position_error': mean_joint_error,
            'mean_max_joint_position_error': mean_max_joint_error,
            'returncode': result.returncode,
            'summary_path': str(summary_path.relative_to(repo)) if summary_path.exists() else '',
            'log_path': str(log_path.relative_to(repo)),
        }
        rows.append(row)
        aggregate_path = out_root / 'pd_grid_summary.csv'
        with aggregate_path.open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

ranked = sorted(
    rows,
    key=lambda r: (
        r['success_rate'],
        r['mean_score'],
        r['mean_completion'],
        -r['mean_joint_position_error'],
    ),
    reverse=True,
)
best = ranked[0] if ranked else {}
(out_root / 'best_pd_params.json').write_text(json.dumps(best, indent=2, ensure_ascii=False), encoding='utf-8')
print('\n[grid-kinematic] top 10')
for r in ranked[:10]:
    print(
        f"kp={r['kp']:<3} kd={r['kd']:<3} success={r['success_count']}/{r['motions']} "
        f"score={r['mean_score']:.3f} completion={r['mean_completion']:.3f} "
        f"mean_joint_err={r['mean_joint_position_error']:.4f}"
    )
print(f"[grid-kinematic] summary: {out_root / 'pd_grid_summary.csv'}")
print(f"[grid-kinematic] best: {out_root / 'best_pd_params.json'}")