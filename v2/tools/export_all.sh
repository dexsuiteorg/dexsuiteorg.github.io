#!/bin/bash
# Export every replay the v2 site uses (Genesis kinematic replays). GPU from $GPU (default 3).
cd /efs/projects/fudi
GPU=${GPU:-3}
W=dexsuite_website/v2/work/replays
L=dexsuite_website/v2/work/logs
export CUDA_VISIBLE_DEVICES=$GPU EGL_DEVICE_ID=$GPU PYOPENGL_PLATFORM=egl HF_TOKEN=$(cat .hf/token)
run() { name=$1; shift; [ -f $W/$name/scene.json ] && [ -z "$FORCE" ] && { echo "skip $name"; return; }
  rm -rf $W/$name; echo "[$(date +%H:%M:%S)] $name"; .venv-dexsuite/bin/python dexsuite_website/v2/tools/export_replay.py "$@" --out $W/$name > $L/export_$name.log 2>&1 || echo "FAILED $name"; tail -1 $L/export_$name.log; }
SH=/efs/projects/fudi/data/task_trajectories
FORCE=1 run pan_allegro      --task pick_place_pan   --manip franka --grip allegro --source hf:dexsuite/pick_place_pan_franka_allegro --episode 1 --stride 1
FORCE=1 run mug_allegro      --task pick_place_mug   --manip franka --grip allegro --source hf:dexsuite/pick_place_mug_franka_allegro --episode 1 --stride 1
FORCE=1 run drill_allegro    --task drill_to_point   --manip franka --grip allegro --source hf:dexsuite/drill_to_point_franka_allegro --episode 1 --stride 1
FORCE=1 run fruit_allegro    --task pick_place_fruit --manip franka --grip allegro --source hf:dexsuite/pick_place_fruit_franka_allegro --episode 1 --stride 1
FORCE=1 run toast_sharpa     --task put_bread_toaster --manip floating --grip sharpa_fardexbot --source $SH/sharpa-grasp-20260927-174743-28045/toaster_simple --episode 0 --stride 1
run pickplace_umi    --task pick_place       --manip franka --grip franka_umi_tacticle --source hf:dexsuite/pick_place_franka_franka_umi_tacticle --episode 1 --stride 1
run pickplace_allegro --task pick_place      --manip franka --grip allegro --source hf:dexsuite/pick_place_franka_allegro --episode 1 --stride 1
#run stack_allegro    --task stack            --manip franka --grip allegro --source hf:dexsuite/stack_franka_allegro --episode 1 --stride 2
echo done
