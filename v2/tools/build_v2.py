#!/usr/bin/env python3
"""Write the scroll-driven DexSuite page to the site root (index.html, assets in v2/) and a redirect at v2/index.html.
Numbers come from the paper's sources (Overleaf clone).

    python3 v2/tools/build_v2.py
"""
import html
import json
import re
from pathlib import Path

V2 = Path(__file__).resolve().parents[1]
PAPER = Path("/efs/projects/fudi/test_stuff/paper_ol")
TEX = (PAPER / "ral_2026.tex").read_text(encoding="utf-8")
TABLE = (PAPER / "Dexsuite/imitation_results.tex").read_text(encoding="utf-8")
HF = "https://huggingface.co/dexsuite"

TITLE = re.search(r"\\title\{(.*?)\}", TEX).group(1)
EPISODES = re.search(r"dataset of (\d\{,\}\d+) successful episodes", TEX).group(1).replace("{,}", ",")
PAIRS = re.search(r"benchmark of (\d+) task-embodiment pairs", TEX).group(1)
ARMS, EFFECTORS = re.search(r"any of its (\d+) arms paired with any of its (\d+) end-effectors", TEX).groups()
N_TASKS = re.search(r"provides (\d+) tasks", TEX).group(1)
TIERS = {"human": 700, "scripted": int(re.search(r"scripted tier adds (\d\{,\}\d+|\d+)", TEX).group(1).replace("{,}", "")),
         "machine": int(re.search(r"machine-generated tier contributes (\d\{,\}\d+|\d+)", TEX).group(1).replace("{,}", ""))}


def panels():
    """[(tasks, rows)] of Table II, rows = list of 8 means."""
    out = []
    for block in re.findall(r"\\begin\{tabular\*\}.*?\\end\{tabular\*\}", TABLE, re.S):
        lines = [l.strip() for l in block.splitlines()]
        head = next(l for l in lines if l.startswith("\\textbf{Model"))
        tasks = [re.sub(r"\\textbf\{(.*?)\}", r"\1", t).replace("\\&", "&").strip() for t in re.split(r"(?<!\\)&", head.rstrip("\\"))[1:]]
        rows = []
        for l in lines:
            if re.match(r"(BC-G|BC-GMM|BC-T|Diffusion|ACT) \(", l):
                rows.append([float(re.search(r"(\d+(?:\.\d+)?)", c).group(1)) for c in l.rstrip("\\").split("&")[1:]])
        out.append((tasks, rows))
    return out


(P1T, P1), (P2T, P2) = panels()


def full_table():
    """Table II cell by cell: per panel, (tasks, [(label, [(mean, std, bold)])])."""
    out = []
    for block in re.findall(r"\\begin\{tabular\*\}.*?\\end\{tabular\*\}", TABLE, re.S):
        lines = [l.strip() for l in block.splitlines()]
        head = next(l for l in lines if l.startswith("\\textbf{Model"))
        tasks = [re.sub(r"\\textbf\{(.*?)\}", r"\1", t).replace("\\&", "&").strip() for t in re.split(r"(?<!\\)&", head.rstrip("\\"))[1:]]
        rows = []
        for l in lines:
            m = re.match(r"((?:BC-G|BC-GMM|BC-T|Diffusion|ACT) \((?:state|image)\))", l)
            if m:
                cells = []
                for c in l.rstrip("\\").split("&")[1:]:
                    v = re.search(r"\$\s*(?:\\bm\{)?(\d+(?:\.\d+)?)", c).group(1)
                    sd = re.search(r"\\pm\\,\s*(\d+(?:\.\d+)?)", c).group(1)
                    cells.append((float(v), float(sd), "\\bm{" in c))
                rows.append((m.group(1), cells))
        out.append((tasks, rows))
    return out


(FT1, FR1), (FT2, FR2) = full_table()
assert FT1[:5] == FT2[:5] and len(FR1) == len(FR2) == 6
GROUPS = [("Track 1", "Parallel-jaw gripper", 0, range(0, 5)), ("Track 1", "Allegro hand", 1, range(0, 5)),
          ("Track 2", "Allegro hand", 0, range(5, 8)), ("Track 2", "Allegro hand", 1, range(5, 6)), ("Track 2", "Sharpa hand", 1, range(6, 8))]


def results_table():
    labels = [r[0] for r in FR1]
    fmt = lambda v: f"{v:g}"  # noqa: E731
    head = ('<thead><tr><th></th><th colspan="4" class="mod">State input</th><th colspan="2" class="mod">Image input</th></tr>'
            '<tr><th class="task">Task</th>' + "".join(f"<th>{esc(l.split(' (')[0])}</th>" for l in labels) + "</tr></thead>")
    body, last = [], None
    for track, emb, panel, cols in GROUPS:
        tasks, rows = (FT1, FR1) if panel == 0 else (FT2, FR2)
        if (track, emb) != last:
            body.append(f'<tr class="grp"><th colspan="7">{track}<span>{emb}</span></th></tr>')
            last = (track, emb)
        for j in cols:
            tds = []
            for _, cells in rows:
                v, sd, bold = cells[j]
                num = f"<b>{fmt(v)}</b>" if bold else fmt(v)
                tds.append(f'<td style="--a:{v / 100:.2f}">{num}<small>&plusmn;{fmt(sd)}</small></td>')
            body.append(f'<tr><th class="task">{esc(tasks[j])}</th>{"".join(tds)}</tr>')
    return f'<table class="res">{head}<tbody>{"".join(body)}</tbody></table>'


N_PAIRS_TABLE = sum(len(c) for _, _, _, c in GROUPS)
assert str(N_PAIRS_TABLE) == PAIRS, (N_PAIRS_TABLE, PAIRS)
best = lambda rows, j: max(r[j] for r in rows)  # noqa: E731
TRACK1 = [(P1T[j], best(P1, j), best(P2, j)) for j in range(5)]          # (task, gripper best, Allegro best)
HARD = [("Stack", max(best(P1, 4), best(P2, 4)), "best of any baseline, either embodiment"),
        ("Place Fruits", best(P2, 5), "best of any baseline"),
        ("Spray Graffiti", best(P2, 6), "best of any baseline"),
        ("Toast Bread", best(P2, 7), "best of any baseline")]

EES = [  # key, name, kind
    ("robotiq", "Robotiq 2F-85", "Parallel-jaw gripper"), ("umi", "UMI gripper", "Parallel-jaw gripper"),
    ("franka_umi_tacticle", "UMI tactile gripper", "Gripper with FlexiTac pads"), ("barrett", "BarrettHand", "3 fingers, 8 DoF"),
    ("dclaw", "D'Claw", "3 fingers, 9 DoF"), ("inspire", "Inspire Hand", "5 fingers, 6 DoF"),
    ("ability", "Ability Hand", "5 fingers, 6 DoF"), ("schunk", "Schunk SVH", "5 fingers, 9 DoF"),
    ("allegro", "Allegro Hand", "4 fingers, 16 DoF"), ("leap", "LEAP Hand", "4 fingers, 16 DoF"),
    ("sharpa", "Sharpa Hand", "5 fingers, 22 DoF"), ("shadow", "Shadow Hand", "5 fingers, 24 DoF"),
]
ARM_NAMES = [("franka", "Franka Panda"), ("kuka", "KUKA LBR iiwa 14"), ("ur5", "UR5e"), ("ur10", "UR10e"),
             ("sawyer", "Rethink Sawyer"), ("gen3", "Kinova Gen3"), ("lite6", "UFactory Lite 6"), ("link6", "Link6"),
             ("z1", "Unitree Z1")]
TILES = [  # clip, task, line, meta
    ("pan_allegro", "Move Pan", "Lift the pan off the hot plate and set it down on the mat.", "Allegro hand, human teleoperation"),
    ("mug_allegro", "Rack Mug", "Pick up the mug, place it in the rack and let go.", "Allegro hand, human teleoperation"),
    ("drill_allegro", "Drill to Point", "Pick up the drill and align its tip with the target.", "Allegro hand, human teleoperation"),
    ("fruit_allegro", "Place Fruits", "Put the apple and the lemon into the bowl, one after the other.", "Allegro hand, human teleoperation"),
    ("toast_sharpa", "Toast Bread", "Stand the slice in a toaster slot and push the lever down.", "Sharpa hand, scripted expert"),
]
ABSTRACT = re.sub(r"\s+", " ", re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", TEX, re.S).group(1)).strip()
ABSTRACT = ABSTRACT.replace("{,}", ",").replace("~", " ").replace("\\%", "%")
T1 = [  # clip key, tab label, gripper used in the dataset
    ("reach", "Reach", "Robotiq 2F-85"), ("lift", "Lift", "UMI gripper"), ("push", "Push", "UMI gripper"),
    ("pickplace", "Pick & Place", "UMI gripper"), ("stack", "Stack", "UMI gripper"),
]
STATEMENT = ("DexSuite brings the robot, the tasks, teleoperation, tactile sensing, the data and the evaluation into "
             "one stack. Any of its tasks runs with any arm and any hand.")


def esc(s):
    return html.escape(s, quote=True)


def words(s):
    return " ".join(f'<span class="w">{esc(w)}</span>' for w in s.split())


hero_n = len(json.load(open(json.load(open(V2 / "shots/hero_scene.json"))["scene"]))["frames"])
ROBOTS = [  # asset, name, kind, phase
    ("ib_so_100", "SO-100", "Built-in gripper", "own"),
    ("ib_aloha_tactile", "ALOHA", "Built-in gripper with tactile pads", "own"),
    ("ib_gen3_lite", "Kinova Gen3 Lite", "Built-in gripper", "own"),
    ("ib_trossen_vx300s", "Trossen ViperX 300 S", "Built-in gripper", "own"),
    ("ib_trossen_wx250s", "Trossen WidowX 250 S", "Built-in gripper", "own"),
    ("rb_ur5", "UR5e", "With a Robotiq 2F-85", "arm"), ("rb_ur10", "UR10e", "With a Robotiq 2F-85", "arm"),
    ("rb_gen3", "Kinova Gen3", "With a Robotiq 2F-85", "arm"),
    ("rb_franka", "Franka Panda", "With a Robotiq 2F-85", "arm"),
    ("ee_robotiq", "Robotiq 2F-85", "Parallel-jaw gripper", "hand"), ("ee_franka_umi_tacticle", "UMI gripper", "Parallel-jaw gripper with FlexiTac pads", "hand"),
    ("ee_barrett", "BarrettHand", "3 fingers, 8 DoF", "hand"), ("ee_dclaw", "D'Claw", "3 fingers, 9 DoF", "hand"),
    ("ee_inspire", "Inspire Hand", "5 fingers, 6 DoF", "hand"), ("ee_ability", "Ability Hand", "5 fingers, 6 DoF", "hand"),
    ("ee_schunk", "Schunk SVH", "5 fingers, 9 DoF", "hand"), ("ee_allegro", "Allegro Hand", "4 fingers, 16 DoF", "hand"),
    ("ee_leap", "LEAP Hand", "4 fingers, 16 DoF", "hand"), ("ee_sharpa", "Sharpa Hand", "5 fingers, 22 DoF", "hand"),
]
PHASES = {"own": ("Robots", "Every arm.", "Robots that come with their own gripper run every task as they are."),
          "arm": ("Modular arms", "Every arm.", "Modular arms take any end-effector. Here, each one carries the same Robotiq 2F-85."),
          "hand": ("End-effectors", "Every hand.", "And every end-effector mounts on the same arm, from parallel-jaw grippers to a 22-joint hand.")}
robot_imgs = "\n".join(
    f'<img src="assets/robots/{a}.webp" data-name="{esc(n)}" data-kind="{esc(k)}" data-phase="{ph}" alt="{esc(n)}" loading="lazy" decoding="async"'
    f'{" data-zoom=1" if a == "rb_franka" else ""}{" style=opacity:1" if i == 0 else ""}>'
    for i, (a, n, k, ph) in enumerate(ROBOTS))
robot_lists = "\n".join(
    f'<ul class="hand-list" data-phase="{ph}"{"" if ph == "own" else " hidden"}>' + "".join(f"<li data-i=\"{i}\">{esc(n)}</li>" for i, (a, n, k, p2) in enumerate(ROBOTS) if p2 == ph) + "</ul>"
    for ph in PHASES)
ee_imgs = "\n".join(
    f'<img src="assets/ee/{k}.webp" data-name="{esc(n)}" data-kind="{esc(kind)}" alt="{esc(n)} on a Franka arm"{" class=on" if i == 0 else ""}>'
    for i, (k, n, kind) in enumerate(EES))
ee_list = "\n".join(f'<li{" class=on" if i == 0 else ""}>{esc(n)}</li>' for i, (k, n, kind) in enumerate(EES))
arms = "\n".join(f'<figure class="reveal"><img src="assets/arms/{k}.webp" alt="{esc(n)} with an Allegro hand" loading="lazy"><figcaption>{esc(n)}</figcaption></figure>'
                 for k, n in ARM_NAMES if (V2 / f"assets/arms/{k}.webp").exists())
T1_DATA = [{"key": k, "grip": g} for k, _, g in T1]
t1_tabs = "".join(f'<button type="button" role="tab" data-i="{j}"{" class=on" if j == 0 else ""}>{esc(lab)}</button>' for j, (_, lab, _) in enumerate(T1))
LOGOS = [("mcgill", "McGill University", 40), ("mila", "Mila", 32), ("amazon", "Amazon", 30), ("hf", "Hugging Face", 30),
         ("kinova", "Kinova", 17), ("manus", "Manus", 16)]
logos = "".join(f'<img loading="lazy" src="assets/logos/{n}.png" alt="{esc(a)}" style="height:{h}px">' for n, a, h in LOGOS)
tiles = "\n".join(f'''<article class="tile"><video muted loop playsinline preload="metadata" poster="assets/clips/{c}.jpg"><source src="assets/clips/{c}.mp4" type="video/mp4"></video>
<h3>{esc(t)}</h3><p>{esc(line)}</p><div class="meta">{esc(meta)}</div></article>''' for c, t, line, meta in TILES)
chart = "\n".join(f'''<div class="grp"><div class="name">{esc(t)}</div><div class="bars">
<div class="hb g" data-w="{g:g}"><i data-w="{g:g}"></i><em>{g:g}%</em></div>
<div class="hb h" data-w="{h:g}"><i data-w="{h:g}"></i><em>{h:g}%</em></div></div></div>''' for t, g, h in TRACK1)
hard = "\n".join(f'<div><b data-count="{v:g}" data-suffix="%">0%</b><span>{esc(t)}, {esc(note)}</span></div>' for t, v, note in HARD)
total = sum(TIERS.values())
tiers = "\n".join(f'''<div class="tier"><div class="row"><span>{label}</span><b>{v:,}</b></div><div class="bar"><i data-w="{100 * v / total:.1f}"></i></div></div>'''
                  for label, v in (("Human teleoperation", TIERS["human"]), ("Scripted experts", TIERS["scripted"]),
                                   ("Machine-generated", TIERS["machine"])))
AUTHORS = "Anas Houssaini, Hugo He, Junming Shi, Amin Abyaneh, Ricardo Chahine, Shuo Wen, Mohamad H. Danesh, Charles-Étienne Fréchette, Mariana Sosa Guzman, Mathias Desrochers, Rayan Houssaini, Adam Landa, Theophile Soulie, Charlotte Morissette, Annie Tims, Martino Russi, Jonathan Lussier, Gregory Dudek, Doina Precup, Julen Urain, Hsiu-Chin Lin, David Meger"
ARXIV = "https://arxiv.org/abs/2610.37799"
bib = """@article{houssaini2026dexsuite,
  title   = {DexSuite: An All-in-One Framework for Dexterous Manipulation Across Arms, Hands, and Tasks},
  author  = {Houssaini, Anas and He, Hugo and Shi, Junming and Abyaneh, Amin and Chahine, Ricardo and Wen, Shuo and Danesh, Mohamad H. and Fr{\\'e}chette, Charles-{\\'E}tienne and Sosa Guzman, Mariana and Desrochers, Mathias and Houssaini, Rayan and Landa, Adam and Soulie, Theophile and Morissette, Charlotte and Tims, Annie and Russi, Martino and Lussier, Jonathan and Dudek, Gregory and Precup, Doina and Urain, Julen and Lin, Hsiu-Chin and Meger, David},
  journal = {arXiv preprint arXiv:2610.37799},
  year    = {2026}
}"""

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(TITLE)}</title>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-H0BF1KZ38G"></script>
<script>window.dataLayer = window.dataLayer || []; function gtag() {{ dataLayer.push(arguments); }} gtag('js', new Date()); gtag('config', 'G-H0BF1KZ38G');</script>
<meta name="description" content="{esc(TITLE)}. {N_TASKS} tasks, {ARMS} arms, {EFFECTORS} end-effectors, {PAIRS} benchmark task-embodiment pairs, {EPISODES} episodes.">
<meta name="theme-color" content="#ffffff">
<meta property="og:type" content="website">
<meta property="og:url" content="https://dexsuiteorg.github.io/">
<meta property="og:title" content="DexSuite">
<meta property="og:description" content="An all-in-one simulation framework for dexterous manipulation. {N_TASKS} tasks, {ARMS} arms, {EFFECTORS} end-effectors, {EPISODES} episodes.">
<meta property="og:image" content="https://dexsuiteorg.github.io/v2/assets/og.jpg">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta property="og:image:alt" content="DexSuite: a Sharpa hand spray-paints a stencil">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="DexSuite">
<meta name="twitter:description" content="An all-in-one simulation framework for dexterous manipulation.">
<meta name="twitter:image" content="https://dexsuiteorg.github.io/v2/assets/og.jpg">
<link rel="icon" href="../static/images/favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="preload" as="image" href="assets/hero/scene/f0000.webp" fetchpriority="high">
<link rel="stylesheet" href="site.css">
<script>document.documentElement.classList.add('js'); window.V2 = {json.dumps({"hero": {"n": hero_n, "dir": "assets/hero/scene"}, "phases": {k: list(v) for k, v in PHASES.items()}, "zoom": {"n": 40, "dir": "assets/robots/zoom"}, "t1": T1_DATA, "clips": "assets/clips"})};</script>
<script defer src="site.js"></script>
</head>
<body>
<nav class="nav">
  <a class="brand" href="#hero">DexSuite</a>
  <div class="links"><a href="#robots">Robots</a><a href="#dexterity">Tasks</a><a href="#data">Data</a><a href="data.html">Data viewer</a><a href="#benchmark">Benchmark</a>
  <a class="pill" href="{HF}" target="_blank" rel="noopener">Get the data</a></div>
</nav>

<section id="hero">
  <div class="sticky">
    <canvas aria-label="A Sharpa hand picks up a spray can and paints a stencil, replayed from a recorded demonstration"></canvas>
    <div class="hero-copy">
      <h1>DexSuite</h1>
      <div class="hero-lines">
        <span data-from="0" data-to="0.34">Dexterous manipulation.</span>
        <span data-from="0.34" data-to="0.68" class="grey">Simulated, teleoperated, benchmarked.</span>
        <span data-from="0.68" data-to="1.01">All in one framework.</span>
      </div>
      <div class="hero-ctas"><a class="pill big" href="{HF}" target="_blank" rel="noopener">Get the data</a><a class="pill big ghost" href="{ARXIV}" target="_blank" rel="noopener">Paper</a></div>
    </div>
    <div class="progress"><i></i></div>
    <button class="scroll-hint" type="button" aria-label="Scroll down"><span>Scroll</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg></button>
  </div>
</section>

<section class="pad" id="paper"><div class="wrap">
  <h2 class="headline reveal">Built for real dexterity.</h2>
  <p class="paper-meta reveal"><b>{esc(TITLE)}</b><br>{esc(AUTHORS)}<br><a href="{ARXIV}" target="_blank" rel="noopener">arXiv:2610.37799</a></p>
  <p class="statement" style="margin-top:110px">{words(STATEMENT)}</p>
  <details class="abs"><summary>Read the abstract</summary><p>{esc(ABSTRACT)}</p></details>
</div></section>

<section id="robots">
  <div class="sticky">
    <div class="ph-copy">
      <p class="eyebrow" id="ph-eyebrow">{PHASES["own"][0]}</p>
      <h2 class="headline md" id="ph-title">{PHASES["own"][1]}</h2>
      <p class="lede" style="margin-top:18px" id="ph-lede">{PHASES["own"][2]}</p>
      {robot_lists}
      <div class="counter">01 / {len(ROBOTS):02d}</div>
    </div>
    <div class="stage">{robot_imgs}<canvas aria-hidden="true"></canvas><div class="tag"><b>{esc(ROBOTS[0][1])}</b><span>{esc(ROBOTS[0][2])}</span></div></div>
  </div>
</section>

<section class="pad alt"><div class="wrap center">
  <h2 class="headline md reveal">Everything in one place.</h2>
  <div class="stats count-on-view">
    <div class="stat"><b data-count="{N_TASKS}">0</b><span>tasks</span></div>
    <div class="stat"><b data-count="{ARMS}">0</b><span>arms</span></div>
    <div class="stat"><b data-count="{EFFECTORS}">0</b><span>end-effectors</span></div>
    <div class="stat"><b data-count="{PAIRS}">0</b><span>benchmark task-embodiment pairs</span></div>
    <div class="stat"><b data-count="{EPISODES.replace(',', '')}">0</b><span>episodes</span></div>
  </div>
</div></section>

<section class="pad" id="same"><div class="wrap">
  <p class="eyebrow reveal">Track 1</p>
  <h2 class="headline md reveal">Same task.<br>Any embodiment.</h2>
  <p class="lede reveal" style="margin-top:18px">Each task is defined once, with the same reset, observations and success check for a gripper and a hand. Every pair below is a recorded human demonstration.</p>
  <div class="seg t1-tabs reveal" role="tablist">{t1_tabs}</div>
  <div class="duo t1 reveal">
    <figure><video muted playsinline preload="auto" data-k="grip" poster="assets/clips/t1_reach_grip.jpg"><source src="assets/clips/t1_reach_grip.mp4" type="video/mp4"></video><figcaption><b data-k="grip-name"></b></figcaption></figure>
    <figure><video muted playsinline preload="auto" data-k="hand" poster="assets/clips/t1_reach_hand.jpg"><source src="assets/clips/t1_reach_hand.mp4" type="video/mp4"></video><figcaption><b>Allegro hand</b></figcaption></figure>
  </div>
</div></section>

<section id="dexterity">
  <div class="sticky">
    <div class="gallery-head"><p class="eyebrow">Track 2</p><h2 class="headline md">Dexterous capability.</h2></div>
    <div class="track">{tiles}</div>
  </div>
</section>

<section class="pad alt" id="teleop"><div class="wrap">
  <p class="eyebrow reveal">Teleoperation</p>
  <h2 class="headline md reveal">Teleoperation, built in.</h2>
  <div class="teleop">
    <div class="reveal">
      <p class="lede">Plug in a device and drive any robot. The arm follows a SpaceMouse, an HTC Vive or Meta Quest controllers, and finger motion from a webcam, a Leap Motion, Quest hand tracking or a Manus glove is mapped to whichever hand is mounted.</p>
      <p class="chip-label">Arm</p><div class="chips"><span>SpaceMouse</span><span>HTC Vive</span><span>Meta Quest controllers</span></div>
      <p class="chip-label">Fingers</p><div class="chips"><span>MediaPipe</span><span>Leap Motion</span><span>Meta Quest hand tracking</span><span>Manus MetaGlove Pro</span></div>
      <p class="chip-label">Hand mapping</p><div class="chips"><span>Direct joint positions</span><span>GeoRT</span><span>DexRetargeting</span></div>
    </div>
    <div class="reveal"><video muted loop playsinline preload="metadata"><source src="../static/videos/manusretarget.mp4" type="video/mp4"></video></div>
  </div>
</div></section>

<section class="pad" id="data"><div class="wrap">
  <p class="eyebrow reveal">Dataset</p>
  <div class="data">
    <div class="observe">
      <div class="big-number count-on-view" data-count="{EPISODES.replace(',', '')}">0</div>
      <h2 class="headline md" style="margin-top:6px">episodes.</h2>
      <p class="lede" style="margin-top:18px">Every one of the {PAIRS} benchmark task-embodiment pairs, recorded at 20&nbsp;Hz with front and wrist cameras, proprioception and object states, in LeRobot format with an HDF5 export for robomimic.</p>
      <div class="tiers">{tiers}</div>
      <div class="ctas"><a class="pill big" href="{HF}" target="_blank" rel="noopener">Browse on Hugging Face</a><a class="pill big ghost" href="data.html">Open the data viewer</a></div>
    </div>
    <div class="reveal"><img src="../static/images/paper/dataset_wheel.png" alt="Dataset composition by tier, embodiment and task" loading="lazy"></div>
  </div>
</div></section>

<section class="pad alt" id="benchmark"><div class="wrap">
  <p class="eyebrow reveal">Benchmark</p>
  <h2 class="headline md reveal">Hands keep up.</h2>
  <p class="lede reveal" style="margin-top:18px">Policies trained and evaluated on the Allegro hand match or outperform their gripper counterparts on several shared tasks.</p>
  <div class="chart observe">
    <div class="legend"><span><i style="background:var(--grip)"></i>Parallel-jaw gripper</span><span><i style="background:var(--hand)"></i>Allegro hand</span></div>
    {chart}
    <p class="chart-note">Best success rate (%) of the six baselines in the table below, per task and embodiment, three seeds with 50 episodes each.</p>
  </div>
  <h3 class="headline md reveal" style="margin-top:110px;font-size:clamp(30px,3.6vw,48px)">Still far from solved.</h3>
  <div class="hard observe">{hard}</div>
  <h3 class="headline md reveal" style="margin-top:110px;font-size:clamp(30px,3.6vw,48px)">All {PAIRS} task-embodiment pairs.</h3>
  <p class="lede reveal" style="margin-top:14px">Success rate (%) of every baseline, mean and standard deviation across three seeds with 50 episodes each. Bold is the best result within each input type.</p>
  <div class="results reveal">{results_table()}</div>
</div></section>

<footer><div class="wrap center">
  <h2 class="headline md">DexSuite</h2>
  <div class="ctas" style="justify-content:center"><a class="pill big" href="{ARXIV}" target="_blank" rel="noopener">Paper</a><span class="pill big disabled">Code, coming soon</span><a class="pill big" href="{HF}" target="_blank" rel="noopener">Data</a></div>
  <div class="logos">{logos}</div>
  <pre class="bib">{esc(bib)}</pre>
</div></footer>
</body>
</html>
"""



import sys  # noqa: E402
sys.path.insert(0, str(Path(__file__).parent))
from brand import brand  # noqa: E402

page = brand(page)


def at_root(page):
    """The page is written with v2/-relative paths; the site root serves it, so point them into v2/ and static/."""
    import hashlib
    ver = lambda f: hashlib.md5((V2 / f).read_bytes()).hexdigest()[:8]  # noqa: E731  new name per deploy, so no stale CSS/JS
    page = page.replace('href="site.css"', f'href="site.css?v={ver("site.css")}"').replace('src="site.js"', f'src="site.js?v={ver("site.js")}"')
    for a, c in (('src="assets/', 'src="v2/assets/'), ('poster="assets/', 'poster="v2/assets/'), ('"dir": "assets/', '"dir": "v2/assets/'), ('"clips": "assets/', '"clips": "v2/assets/'),
                 ('href="assets/', 'href="v2/assets/'), ('href="site.css', 'href="v2/site.css'), ('src="site.js', 'src="v2/site.js'), ('href="data.html"', 'href="v2/data.html"'),
                 ('"../static/', '"static/')):
        page = page.replace(a, c)
    assert "../" not in page and '"assets/' not in page, "a v2-relative path is left in the root page"
    return page


(V2.parent / "index.html").write_text(at_root(page), encoding="utf-8")
(V2 / "index.html").write_text('<!DOCTYPE html><meta charset="utf-8"><title>DexSuite</title>'
                               '<meta http-equiv="refresh" content="0; url=../"><link rel="canonical" href="../">'
                               '<a href="../">DexSuite</a>\n', encoding="utf-8")
print("index.html", len(page) // 1024, "KB; hero frames", hero_n, "; track 1", TRACK1, "; hard", [(t, v) for t, v, _ in HARD])
