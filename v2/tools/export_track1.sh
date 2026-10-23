#!/bin/bash
# Track 1 replays: the same task on a gripper and on the Allegro hand (episode 1 of each human-teleoperation set). GPU from $GPU.
cd /efs/projects/fudi
W=dexsuite_website/v2/work/replays; L=dexsuite_website/v2/work/logs
export CUDA_VISIBLE_DEVICES=${GPU:-3} EGL_DEVICE_ID=${GPU:-3} PYOPENGL_PLATFORM=egl HF_TOKEN=$(cat .hf/token)
run() { name=$1; shift; [ -f $W/$name/scene.json ] && { echo "skip $name"; return; }
  echo "[$(date +%H:%M:%S)] $name"; .venv-dexsuite/bin/python dexsuite_website/v2/tools/export_replay.py "$@" --out $W/$name > $L/export_$name.log 2>&1 || echo "FAILED $name"; tail -1 $L/export_$name.log; }
for spec in "$@"; do eval "run $spec"; done
echo done
