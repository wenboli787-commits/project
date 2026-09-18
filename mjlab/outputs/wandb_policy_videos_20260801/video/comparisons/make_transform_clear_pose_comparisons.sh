#!/usr/bin/env bash

set -euo pipefail

root_dir="/mnt/d/GMR_WORK/mjlab/outputs/wandb_policy_videos_20260801"
output_dir="${root_dir}/video/comparisons"
font_file="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Pair 1: previously pose-matched frames (p5jxr34o F180 vs 3ah12ywt F30).
# Remove the metadata row while preserving the selected images and main titles.
ffmpeg -loglevel error -y \
  -i "${output_dir}/p5jxr34o_vs_3ah12ywt_green_pose_aligned.png" \
  -vf "drawbox=x=0:y=58:w=iw:h=62:color=black:t=fill" \
  -frames:v 1 "${output_dir}/05_04_green_pose_matched_clear_difference.png"

# Pair 2: both videos are synchronized at F250, so the green reference pose,
# location, and direction match directly while the white-policy response differs.
frame_dir="${output_dir}/111_23_green_pose_matched_clear_difference_frames"
mkdir -p "${frame_dir}"

specs=(
  "111_23 ORIGINAL|${root_dir}/video/ppo/111_23_gmr_qwdsvlx8.mp4"
  "111_23 POLICY TRANSFORM|${root_dir}/video/policy transform/111_23_gmr_f5v4oslz.mp4"
)

index=0
for spec in "${specs[@]}"; do
  label="${spec%%|*}"
  video="${spec#*|}"
  printf -v frame_name '%02d.png' "${index}"
  ffmpeg -loglevel error -y -i "${video}" \
    -vf "select=eq(n\,250),crop=1000:1000:460:80,scale=900:900,drawbox=x=0:y=0:w=iw:h=82:color=black@0.88:t=fill,drawtext=fontfile=${font_file}:text='${label}':fontcolor=white:fontsize=42:x=28:y=18" \
    -frames:v 1 "${frame_dir}/${frame_name}"
  index=$((index + 1))
done

ffmpeg -loglevel error -y -framerate 1 -i "${frame_dir}/%02d.png" \
  -vf "tile=2x1" -frames:v 1 \
  "${output_dir}/111_23_green_pose_matched_clear_difference.png"
