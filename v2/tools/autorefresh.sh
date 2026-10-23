#!/bin/bash
# Re-encode finished renders and rebuild v2/index.html every 3 minutes until every clip and the reframed hero exist.
cd /efs/projects/fudi/dexsuite_website/v2
while true; do
  /efs/projects/fudi/.venv-dexsuite/bin/python tools/encode_assets.py > work/logs/encode_last.log 2>&1
  python3 tools/build_v2.py >> work/logs/encode_last.log 2>&1
  n=$(ls assets/clips/*.mp4 2>/dev/null | wc -l); src=$(cat assets/hero/SOURCE 2>/dev/null)
  echo "[$(date +%H:%M:%S)] clips $n/7 hero=$src"
  [ "$n" -ge 7 ] && [ "$src" = spray_hero ] && [ "$(ls assets/hero/*.webp | wc -l)" -ge 239 ] && break
  sleep 180
done
echo done
