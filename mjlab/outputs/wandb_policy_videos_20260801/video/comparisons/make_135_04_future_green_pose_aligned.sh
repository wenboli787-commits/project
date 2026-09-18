#!/usr/bin/env bash

set -euo pipefail

root_dir="/mnt/d/GMR_WORK/mjlab/outputs/wandb_policy_videos_20260801"
output_dir="${root_dir}/video/comparisons"
frame_dir="${output_dir}/135_04_future_green_pose_aligned_frames"
font_file="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
specs=(
  "0uclfphn|250|460|80|PPO|${root_dir}/video/ppo/135_04_gmr_0uclfphn.mp4"
  "0hguvktg|250|524|72|FUTURE F2|${root_dir}/video/future frames/135_04_gmr_future_F2_0hguvktg.mp4"
  "0h5k9qzz|330|552|60|FUTURE F4|${root_dir}/video/future frames/135_04_gmr_future_F4_0h5k9qzz.mp4"
  "enq4cb0m|470|519|52|FUTURE F6|${root_dir}/video/future frames/135_04_gmr_future_F6_enq4cb0m.mp4"
)

mkdir -p "${frame_dir}"
index=0
for spec in "${specs[@]}"; do
  run_id="${spec%%|*}"
  spec="${spec#*|}"
  frame_number="${spec%%|*}"
  spec="${spec#*|}"
  crop_x="${spec%%|*}"
  spec="${spec#*|}"
  crop_y="${spec%%|*}"
  spec="${spec#*|}"
  label="${spec%%|*}"
  filename="${spec#*|}"
  printf -v frame_name '%02d.png' "${index}"
  if [[ "${run_id}" == "0h5k9qzz" ]]; then
    ffmpeg -loglevel error -y -i "${filename}" \
      -vf "select=eq(n\,${frame_number}),crop=1080:1080:518:0,scale=760:760,crop=760:737:0:23,pad=760:760:0:0:black,drawbox=x=0:y=0:w=iw:h=76:color=black@0.82:t=fill,drawtext=fontfile=${font_file}:text='135_04  ${label}':fontcolor=white:fontsize=38:x=26:y=16" \
      -frames:v 1 "${frame_dir}/${frame_name}"
  else
    ffmpeg -loglevel error -y -i "${filename}" \
      -vf "select=eq(n\,${frame_number}),crop=1000:1000:${crop_x}:${crop_y},scale=760:760,drawbox=x=0:y=0:w=iw:h=76:color=black@0.82:t=fill,drawtext=fontfile=${font_file}:text='135_04  ${label}':fontcolor=white:fontsize=38:x=26:y=16" \
      -frames:v 1 "${frame_dir}/${frame_name}"
  fi
  index=$((index + 1))
done

ffmpeg -loglevel error -y -framerate 1 -i "${frame_dir}/%02d.png" \
  -vf "tile=2x2" -frames:v 1 \
  "${output_dir}/135_04_high_knee_reference_depth_size_aligned.png"
