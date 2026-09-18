#!/usr/bin/env bash

set -euo pipefail

output_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root_dir="$(cd "${output_dir}/../.." && pwd)"
frame_dir="${output_dir}/p5j_3ah_frame_300"
font_file="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
frame_number=300

specs=(
  "${root_dir}/cache/g1_tracking/wandb_checkpoints/p5jxr34o/videos/play/rl-video-step-0.mp4|ORIGINAL 05_04 | p5jxr34o"
  "${output_dir}/05_04_gmr_3ah12ywt.mp4|47_01 TO 05_04 | 3ah12ywt"
)

mkdir -p "${frame_dir}"
index=0
for spec in "${specs[@]}"; do
  filename="${spec%%|*}"
  label="${spec#*|}"
  printf -v frame_name '%02d.jpg' "${index}"
  ffmpeg -loglevel error -y -i "${filename}" \
    -vf "select=eq(n\,${frame_number}),scale=960:540,drawtext=fontfile=${font_file}:text='${label} | FRAME ${frame_number} | t=6.0s':fontcolor=white:fontsize=28:x=24:y=24:box=1:boxcolor=black@0.74:boxborderw=11" \
    -frames:v 1 "${frame_dir}/${frame_name}"
  index=$((index + 1))
done

ffmpeg -loglevel error -y -framerate 1 -i "${frame_dir}/%02d.jpg" \
  -vf "tile=2x1" -frames:v 1 \
  "${output_dir}/p5jxr34o_vs_3ah12ywt_frame_300.jpg"
