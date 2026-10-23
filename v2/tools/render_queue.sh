#!/bin/bash
# render_queue.sh GPU "shot[@lo:hi:st]" ...   renders the shots one after another on one GPU (resumable)
cd /efs/projects/fudi/dexsuite_website/v2
GPU=$1; shift
for item in "$@"; do
  shot=${item%@*}; fr=""; [[ $item == *@* ]] && fr="--frames ${item#*@}"
  echo "[$(date +%H:%M:%S)] GPU$GPU $shot $fr"
  CUDA_VISIBLE_DEVICES=$GPU /tmp/hoirfig/bpyenv/bin/python tools/render_replay.py shots/$shot.json $fr > work/logs/render_${shot}_${GPU}.log 2>&1 || echo "FAILED $shot"
done
echo "[$(date +%H:%M:%S)] GPU$GPU done"
