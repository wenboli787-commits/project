#!/usr/bin/env bash

set -euo pipefail

output_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
frame_dir="${output_dir}/comparison_fall_frame_25"
font_file="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
fall_frame=25

specs=(
  "05_04_control_hs2g9wk9.mp4|CONTROL"
  "05_04_strict_10_b5hx6inw.mp4|STRICT 10"
  "05_04_strict_20_d18ykrnq.mp4|STRICT 20"
  "05_04_strict_30_qsi7nv1f.mp4|STRICT 30"
  "05_04_strict_40_nuxh5loj.mp4|STRICT 40"
  "05_04_strict_50_scmby1b0.mp4|STRICT 50"
  "05_04_strict_60_sxwz2g6d.mp4|STRICT 60"
  "05_04_strict_70_uryz8pn2.mp4|STRICT 70"
  "05_04_strict_80_vttxn70b.mp4|STRICT 80"
  "05_04_strict_90_no_terminations_i10dxzqw.mp4|STRICT 90 (NO RESET)"
)

mkdir -p "${frame_dir}"
index=0
for spec in "${specs[@]}"; do
  IFS='|' read -r filename label <<<"${spec}"
  printf -v frame_name '%02d.jpg' "${index}"
  ffmpeg -loglevel error -y -i "${output_dir}/${filename}" \
    -vf "select=eq(n\,${fall_frame}),scale=640:360,drawtext=fontfile=${font_file}:text='${label} | FRAME ${fall_frame}':fontcolor=white:fontsize=27:x=18:y=18:box=1:boxcolor=black@0.72:boxborderw=9" \
    -frames:v 1 "${frame_dir}/${frame_name}"
  index=$((index + 1))
done

ffmpeg -loglevel error -y -framerate 1 -i "${frame_dir}/%02d.jpg" \
  -vf "tile=5x2" -frames:v 1 \
  "${output_dir}/strict_comparison_fall_frame_25.jpg"
