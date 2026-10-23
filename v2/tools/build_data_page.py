#!/usr/bin/env python3
"""Write v2/data.html, the standalone data viewer. Episodes come from ../static/data_viewer (tools/build_data_viewer.py),
task facts from the paper's stage data.

    python3 v2/tools/build_data_page.py
"""
import html
import json
import re
from pathlib import Path

V2 = Path(__file__).resolve().parents[1]
PAPER = Path("/efs/projects/fudi/test_stuff/paper_ol")
STAGES = json.loads((PAPER / "figures/data/task_stages.json").read_text())
TEX = (PAPER / "ral_2026.tex").read_text(encoding="utf-8")
PAIRS = re.search(r"benchmark of (\d+) task-embodiment pairs", TEX).group(1)
HF = "https://huggingface.co/dexsuite"

BLURB = {
    "reach": "Bring the tool center point to a random target in the workspace.",
    "lift": "Grasp the cube and hold it above the table.",
    "push": "Slide the cube to the goal without lifting it.",
    "pick_place": "Pick up the cube and set it down on the goal.",
    "stack": "Stack two cubes onto a third, in order.",
    "pick_place_mug": "Pick up the mug, place it in the rack and let go.",
    "pick_place_pan": "Lift the pan off the hot plate and set it on the mat.",
    "drill_to_point": "Pick up the drill and align its tip with the target.",
    "pick_place_fruit": "Put the apple and the lemon into the bowl.",
    "spray_graffiti": "Grasp the aerosol can and fill the stencil outline on the paper.",
    "put_bread_toaster": "Stand the slice in a toaster slot and push the lever down.",
}
ORDER = list(BLURB)
NICE = {"second_object": "second object", "press": "press lever"}
tasks = []
for k in ORDER:
    t = next(x for x in STAGES["tasks"] if x["key"] == k)
    tasks.append({"key": k, "name": t["task"], "track": 1 if "gripper" in t["embodiments"] else 2, "blurb": BLURB[k],
                  "seconds": t["horizon_steps"] // 20,
                  "success": t["success"].replace(">=", "≥").replace("<=", "≤").replace(" deg", "°").replace(" %", "%"),
                  "stages": [NICE.get(s, s) for s in t["required"]]})

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DexSuite Data Viewer</title>
<meta name="description" content="Browse episodes of the DexSuite dataset: front and wrist cameras, the tool center point trajectory and hand closure, for every benchmark task-embodiment pair.">
<link rel="icon" href="../static/images/favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="site.css">
<link rel="stylesheet" href="data.css">
<script>window.DV_TASKS = {json.dumps(tasks)};</script>
<script defer src="data.js"></script>
</head>
<body class="dv-page">
<nav class="nav">
  <a class="brand" href="index.html">DexSuite</a>
  <div class="links"><a href="index.html#robots">Robots</a><a href="index.html#dexterity">Tasks</a><a href="index.html#data">Data</a><a href="data.html" class="cur">Data viewer</a><a href="index.html#benchmark">Benchmark</a>
  <a class="pill" href="{HF}" target="_blank" rel="noopener">Get the data</a></div>
</nav>

<header class="dv-head wrap">
  <p class="eyebrow">Dataset</p>
  <h1 class="headline">Data Viewer.</h1>
  <p class="lede">Three episodes for every one of the {PAIRS} benchmark task-embodiment pairs and each collection tier, straight from the released data.</p>
</header>

<section class="wrap">
  <div class="dv-picker" id="dv-picker" role="listbox" aria-label="Task"></div>
</section>

<section class="wrap dv-main">
  <div class="dv-bar">
    <div>
      <h2 class="dv-title" id="dv-title"></h2>
      <p class="dv-sub" id="dv-sub"></p>
    </div>
    <div class="dv-controls">
      <div class="seg" id="dv-emb" role="radiogroup" aria-label="Embodiment"></div>
      <div class="seg" id="dv-tier" role="radiogroup" aria-label="Source"></div>
      <div class="seg small" id="dv-ep" role="radiogroup" aria-label="Episode"></div>
    </div>
  </div>

  <div class="dv-cams">
    <figure><div class="cam"><video id="cam-front" muted playsinline preload="auto"></video></div><figcaption>Front camera</figcaption></figure>
    <figure><div class="cam wrist"><video id="cam-wrist" muted playsinline preload="auto"></video></div><figcaption>Wrist camera</figcaption></figure>
  </div>

  <div class="dv-transport">
    <button class="play" id="dv-play" aria-label="Pause"><span></span></button>
    <input type="range" id="dv-scrub" min="0" max="1000" value="0" aria-label="Time in the episode">
    <span class="time" id="dv-time">0.0 s</span>
  </div>

  <div class="dv-charts">
    <div class="chart-card">
      <div class="chart-head"><h3>Tool center point</h3><p>Position relative to the first frame, cm</p></div>
      <div class="dv-legend" id="lg-tcp"></div>
      <svg id="ch-tcp" role="img" aria-label="Tool center point trajectory"></svg>
    </div>
    <div class="chart-card">
      <div class="chart-head"><h3>Hand closure</h3><p>Mean position of the moving finger joints, 0 open to 100 closed</p></div>
      <svg id="ch-grip" role="img" aria-label="Hand closure over the episode"></svg>
    </div>
    <div class="dv-tip" id="dv-tip" hidden></div>
  </div>

  <div class="dv-facts">
    <div><span>Track</span><b id="f-track"></b></div>
    <div><span>Episode length</span><b id="f-len"></b></div>
    <div><span>Time limit</span><b id="f-limit"></b></div>
    <div class="wide"><span>Success</span><b id="f-success"></b></div>
    <div class="wide"><span>Stages</span><div class="chips" id="f-stages"></div></div>
  </div>
  <div class="dv-cta"><a class="pill big" id="dv-hf" target="_blank" rel="noopener">Open this dataset on Hugging Face</a><span class="dv-note" id="dv-note"></span></div>
</section>

<footer class="dv-foot"><div class="wrap center">
  <p class="fine">Episodes are cut from the LeRobot v3 videos at 20&nbsp;Hz; charts are sampled at 10&nbsp;Hz. <a href="index.html">Back to DexSuite</a></p>
</div></footer>
</body>
</html>
"""
(V2 / "data.html").write_text(page, encoding="utf-8")
print("v2/data.html", len(page) // 1024, "KB,", len(tasks), "tasks")
