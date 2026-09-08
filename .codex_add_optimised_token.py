from pathlib import Path
p = Path('/mnt/d/GMR_WORK/retarget_core_eval/loaders/motion_data.py')
s = p.read_text(encoding='utf-8')
for token in ['    "_optimized",', '    "_optimised",']:
    if token not in s:
        s = s.replace('    "_retargeted",\n', '    "_retargeted",\n' + token + '\n')
p.write_text(s, encoding='utf-8')
