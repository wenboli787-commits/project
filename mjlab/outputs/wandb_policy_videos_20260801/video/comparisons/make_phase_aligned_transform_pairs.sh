#!/usr/bin/env bash

set -euo pipefail

root_dir="/mnt/d/GMR_WORK/mjlab/outputs/wandb_policy_videos_20260801"
output_dir="${root_dir}/video/comparisons"
font_file="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

make_pair() {
  local output_name="$1"
  shift
  local frame_dir="${output_dir}/${output_name}_frames"
  mkdir -p "${frame_dir}"

  local index=0
  local spec run_id frame_number label filename time_seconds frame_name
  for spec in "$@"; do
    run_id="${spec%%|*}"
    spec="${spec#*|}"
    frame_number="${spec%%|*}"
    spec="${spec#*|}"
    label="${spec%%|*}"
    filename="${spec#*|}"
    time_seconds="$(awk -v frame="${frame_number}" 'BEGIN { printf "%.2f", frame / 50 }')"
    printf -v frame_name '%02d.png' "${index}"
    ffmpeg -loglevel error -y -i "${filename}" \
      -vf "select=eq(n\,${frame_number}),crop=1000:1000:460:80,scale=900:900,drawbox=x=0:y=0:w=iw:h=128:color=black@0.82:t=fill,drawtext=fontfile=${font_file}:text='${label}':fontcolor=white:fontsize=42:x=28:y=16,drawtext=fontfile=${font_file}:text='${run_id}   FRAME ${frame_number}   ${time_seconds} s':fontcolor=white:fontsize=30:x=28:y=76" \
      -frames:v 1 "${frame_dir}/${frame_name}"
    index=$((index + 1))
  done

  ffmpeg -loglevel error -y -framerate 1 -i "${frame_dir}/%02d.png" \
    -vf "tile=2x1" -frames:v 1 "${output_dir}/${output_name}.png"
}

make_pair "p5jxr34o_vs_3ah12ywt_green_pose_aligned" \
  "p5jxr34o|180|05_04  ORIGINAL|${root_dir}/cache/g1_tracking/wandb_checkpoints/p5jxr34o/videos/play/rl-video-step-0.mp4" \
  "3ah12ywt|30|05_04  POLICY TRANSFORM|${root_dir}/video/policy transform/05_04_gmr_3ah12ywt.mp4"

make_pair "qwdsvlx8_vs_f5v4oslz_green_pose_aligned" \
  "qwdsvlx8|250|111_23  ORIGINAL|${root_dir}/cache/g1_tracking/wandb_checkpoints/qwdsvlx8/videos/play/rl-video-step-0.mp4" \
  "f5v4oslz|76|111_23  POLICY TRANSFORM|${root_dir}/video/policy transform/111_23_gmr_f5v4oslz.mp4"
