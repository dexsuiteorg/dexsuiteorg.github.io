#!/bin/bash
# Low-quality preview of shots: one frame each (default: the middle frame), contact sheet in v2/work/preview/sheet.jpg
#   v2/tools/preview.sh [GPU] shot1 shot2 ...
cd /efs/projects/fudi/dexsuite_website/v2
GPU=${GPU:-2}
mkdir -p work/preview
for s in "$@"; do
  n=$(/efs/projects/fudi/.venv-dexsuite/bin/python -c "import json;sh=json.load(open('shots/$s.json'));print(len(json.load(open(sh['scene']))['frames']))")
  f=${FRAME:-$((n / 2))}
  tmp=$(mktemp -d /tmp/prev_XXXX); python3 -c "
import json; sh=json.load(open('shots/$s.json')); sh['out']='$tmp'; json.dump(sh, open('$tmp/shot.json','w'))"
  CUDA_VISIBLE_DEVICES=$GPU /tmp/hoirfig/bpyenv/bin/python tools/render_replay.py $tmp/shot.json --frames $f:$((f+1)):1 --samples ${SAMPLES:-24} --scale ${SCALE:-0.35} > $tmp/log 2>&1
  cp $tmp/f*.png work/preview/$s.png 2>/dev/null || { echo "FAILED $s"; tail -5 $tmp/log; }
  rm -rf $tmp
done
/efs/projects/fudi/.venv-dexsuite/bin/python - "$@" <<'PY'
import sys
from PIL import Image, ImageDraw
names = sys.argv[1:]; ims = []
for n in names:
    try:
        im = Image.open(f"work/preview/{n}.png").convert("RGBA")
    except FileNotFoundError:
        continue
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im); im = bg.convert("RGB")
    im.thumbnail((640, 640)); d = ImageDraw.Draw(im); d.text((8, 8), n, fill=(200, 0, 0)); ims.append(im)
cols = 3; w = max(i.width for i in ims); h = max(i.height for i in ims)
sheet = Image.new("RGB", (cols * w, ((len(ims) + cols - 1) // cols) * h), "white")
for k, im in enumerate(ims):
    sheet.paste(im, ((k % cols) * w, (k // cols) * h))
sheet.save("work/preview/sheet.jpg", quality=85); print("sheet", sheet.size)
PY
