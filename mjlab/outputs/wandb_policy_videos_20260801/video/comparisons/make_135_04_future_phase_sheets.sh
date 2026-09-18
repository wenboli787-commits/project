#!/usr/bin/env bash

set -euo pipefail

root_dir="/mnt/d/GMR_WORK/mjlab/outputs/wandb_policy_videos_20260801"
output_dir="${root_dir}/video/comparisons/135_04_future_phase_sheets"
font_file="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
specs=(
  "0uclfphn|${root_dir}/video/ppo/135_04_gmr_0uclfphn.mp4"
  "0hguvktg|${root_dir}/video/future frames/135_04_gmr_future_F2_0hguvktg.mp4"
  "0h5k9qzz|${root_dir}/video/future frames/135_04_gmr_future_F4_0h5k9qzz.mp4"
  "enq4cb0m|${root_dir}/video/future frames/135_04_gmr_future_F6_enq4cb0m.mp4"
)

mkdir -p "${output_dir}"
for spec in "${specs[@]}"; do
  run_id="${spec%%|*}"
  filename="${spec#*|}"
  ffmpeg -loglevel error -y -i "${filename}" \
    -vf "fps=5,crop=1000:1000:460:80,scale=240:240,drawbox=x=0:y=0:w=iw:h=28:color=black@0.8:t=fill,drawtext=fontfile=${font_file}:text='${run_id}  F%{eif\\:n*10\\:d}':fontcolor=white:fontsize=16:x=6:y=5,tile=10x5" \
    -frames:v 1 "${output_dir}/${run_id}_timeline.png"
done
