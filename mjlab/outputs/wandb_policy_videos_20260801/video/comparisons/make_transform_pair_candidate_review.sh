#!/usr/bin/env bash

set -euo pipefail

root_dir="/mnt/d/GMR_WORK/mjlab/outputs/wandb_policy_videos_20260801"
output_dir="${root_dir}/video/comparisons"
frame_dir="${output_dir}/transform_pair_candidate_review"
font_file="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
specs=(
  "p5jxr34o|150|05_04 TARGET|${root_dir}/cache/g1_tracking/wandb_checkpoints/p5jxr34o/videos/play/rl-video-step-0.mp4"
  "3ah12ywt|2|05_04 MATCH|${root_dir}/video/policy transform/05_04_gmr_3ah12ywt.mp4"
  "p5jxr34o|180|05_04 TARGET|${root_dir}/cache/g1_tracking/wandb_checkpoints/p5jxr34o/videos/play/rl-video-step-0.mp4"
  "3ah12ywt|30|05_04 MATCH|${root_dir}/video/policy transform/05_04_gmr_3ah12ywt.mp4"
  "p5jxr34o|200|05_04 TARGET|${root_dir}/cache/g1_tracking/wandb_checkpoints/p5jxr34o/videos/play/rl-video-step-0.mp4"
  "3ah12ywt|50|05_04 MATCH|${root_dir}/video/policy transform/05_04_gmr_3ah12ywt.mp4"
  "qwdsvlx8|250|111_23 TARGET|${root_dir}/cache/g1_tracking/wandb_checkpoints/qwdsvlx8/videos/play/rl-video-step-0.mp4"
  "f5v4oslz|76|111_23 MATCH|${root_dir}/video/policy transform/111_23_gmr_f5v4oslz.mp4"
)

mkdir -p "${frame_dir}"
index=0
for spec in "${specs[@]}"; do
  run_id="${spec%%|*}"
  remainder="${spec#*|}"
  frame_number="${remainder%%|*}"
  remainder="${remainder#*|}"
  label="${remainder%%|*}"
  filename="${remainder#*|}"
  printf -v frame_name '%02d.png' "${index}"
  ffmpeg -loglevel error -y -i "${filename}" \
    -vf "select=eq(n\,${frame_number}),crop=1000:1000:460:80,scale=500:500,drawbox=x=0:y=0:w=iw:h=66:color=black@0.82:t=fill,drawtext=fontfile=${font_file}:text='${label}  ${run_id}  F${frame_number}':fontcolor=white:fontsize=25:x=12:y=17" \
    -frames:v 1 "${frame_dir}/${frame_name}"
  index=$((index + 1))
done

ffmpeg -loglevel error -y -framerate 1 -i "${frame_dir}/%02d.png" \
  -vf "tile=2x4" -frames:v 1 "${output_dir}/transform_pair_candidate_review.png"
