#!/usr/bin/env python
"""Build index.html of the DexSuite project page from the paper's sources.

The page keeps the original nerfies/Bulma theme. Every paper number and sentence on it (title, abstract, framework,
teleoperation, tactile, dataset and benchmark text, Table II) is read from the Overleaf clone, so re-running this
script after a paper edit keeps the page in sync. Task metadata for the data viewer comes from the paper's stage data.

    python3 tools/build_site.py          (from the site root; the data viewer assets come from build_data_viewer.py)
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
PAPER = Path("/efs/projects/fudi/test_stuff/paper_ol")
TEX = (PAPER / "ral_2026.tex").read_text(encoding="utf-8")
TABLE = (PAPER / "Dexsuite/imitation_results.tex").read_text(encoding="utf-8")
STAGES = json.loads((PAPER / "figures/data/task_stages.json").read_text())
HF_ORG = "https://huggingface.co/dexsuite"


# ----------------------------------------------------------------------------------------------------- LaTeX to HTML
def tex2html(t: str) -> str:
    t = re.sub(r"\s*\(Fig\.~\\ref\{[^}]*\}\)", "", t)
    t = re.sub(r"As shown in Fig\.~\\ref\{[^}]*\}, this", "This", t)
    t = re.sub(r"\s*as shown in Fig\.~\\ref\{[^}]*\}", "", t)
    t = re.sub(r"~?\s*\\cite\{[^}]*\}", "", t)
    t = t.replace("$\\pm$", "\u00b1").replace("$", "")
    t = t.replace("{,}", ",").replace("\\%", "%").replace("\\&", "&").replace("\\,", "\u2009").replace("~", " ")
    t = html.escape(t, quote=False)
    t = re.sub(r"\\textit\{([^}]*)\}", r"<em>\1</em>", t)
    t = re.sub(r"\\textbf\{([^}]*)\}", r"<strong>\1</strong>", t)
    t = re.sub(r"\\texttt\{([^}]*)\}", r"<code>\1</code>", t)
    t = re.sub(r"\\noindent\s*", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    assert "\\" not in t, t[:200]
    return t


def para(start: str) -> str:
    """The paragraph (one source line) of the paper that starts with `start`."""
    i = TEX.index(start)
    return TEX[i:TEX.index("\n", i)]


TITLE = re.search(r"\\title\{(.*?)\}", TEX).group(1)
NAME, SUBTITLE = TITLE.split(": ", 1)
ABSTRACT = tex2html(re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", TEX, re.S).group(1))
FRAMEWORK = tex2html(para("DexSuite is a simulation framework built on top of Genesis"))
TELEOP = tex2html(para("\\noindent\\textbf{Teleoperation.}").replace("\\noindent\\textbf{Teleoperation.} ", ""))
TACTILE = tex2html(para("\\noindent\\textbf{Tactile sensing.}").replace("\\noindent\\textbf{Tactile sensing.} ", ""))
DATASET = [tex2html(para("We release 4{,}700")), tex2html(para("All trajectories share"))]
BENCH = tex2html(para("To address the three questions raised in the introduction"))
TRACK1 = tex2html(para("\\textbf{Track 1.").split("} ", 1)[1])
TRACK2 = tex2html(para("\\textbf{Track 2.").split("} ", 1)[1])
EPISODES = re.search(r"dataset of (\d\{,\}\d+) successful episodes", TEX).group(1).replace("{,}", ",")
PAIRS = re.search(r"benchmark of (\d+) task-embodiment pairs", TEX).group(1)
ARMS, EFFECTORS = re.search(r"any of its (\d+) arms paired with any of its (\d+) end-effectors", TEX).groups()
N_TASKS = re.search(r"provides (\d+) tasks", TEX).group(1)
N_BENCH = re.search(r"the benchmark contains (\d+) tasks", TEX).group(1)


# ----------------------------------------------------------------------------------------------------- Table II
def cell(c: str) -> str:
    c = c.strip()
    mean = re.search(r"(\d+(?:\.\d+)?)", c).group(1)
    sd = re.search(r"\\pm\\,\s*(\d+(?:\.\d+)?)", c)
    txt = mean + (f'<span class="sd">&thinsp;&plusmn;&thinsp;{sd.group(1)}</span>' if sd else "")
    return f"<strong>{txt}</strong>" if "\\bm" in c else txt


def multicol(line: str):
    """[(span, text)] for every \\multicolumn{n}{c}{...} on the line (balanced braces)."""
    out, i = [], 0
    while (i := line.find("\\multicolumn{", i)) >= 0:
        n = int(re.match(r"\\multicolumn\{(\d+)\}\{[^}]*\}\{", line[i:]).group(1))
        j = line.index("{", line.index("}{", i) + 2)
        depth, k = 0, j
        for k in range(j, len(line)):
            depth += {"{": 1, "}": -1}.get(line[k], 0)
            if depth == 0:
                break
        body = re.sub(r"\\text(?:bf|it)\{(.*?)\}", r"\1", line[j + 1:k])
        out.append((n, body))
        i = k
    return out


def table_panels():
    panels = []
    for block in re.findall(r"\\begin\{tabular\*\}.*?\\end\{tabular\*\}", TABLE, re.S):
        lines = [l.strip() for l in block.splitlines()]
        heads = [multicol(l) for l in lines if l.startswith("& \\multicolumn")]
        tasks = [re.sub(r"\\textbf\{(.*?)\}", r"\1", t).replace("\\&", "&").strip()
                 for t in re.split(r"(?<!\\)&", next(l for l in lines if l.startswith("\\textbf{Model")).rstrip("\\"))[1:]]
        rows, groups = [], []
        for l in lines:
            m = re.match(r"(BC-G|BC-GMM|BC-T|Diffusion|ACT) \((state|image)\)\s*&(.*)\\\\", l)
            if m:
                if groups and groups[-1] != m.group(2) or not groups:
                    groups.append(m.group(2))
                rows.append((m.group(1), m.group(2), [cell(c) for c in m.group(3).split("&")]))
        assert len(heads) == 2 and len(tasks) == 8 and len(rows) == 6, (len(heads), len(tasks), len(rows))
        panels.append((heads, tasks, rows))
    assert len(panels) == 2
    return panels


def table_html() -> str:
    out = []
    for heads, tasks, rows in table_panels():
        h = ['<table class="table is-fullwidth results-table">', "<thead>"]
        for i, row in enumerate(heads):
            cls = "track-row" if i == 0 else "group-row"
            h.append(f'<tr class="{cls}"><th></th>' + "".join(
                f'<th colspan="{n}"><span>{html.escape(t)}</span></th>' for n, t in row) + "</tr>")
        h.append("<tr><th>Model / input</th>" + "".join(f"<th>{html.escape(t)}</th>" for t in tasks) + "</tr>")
        h.append("</thead><tbody>")
        prev = None
        for name, obs, cells in rows:
            sep = ' class="modality-break"' if prev and prev != obs else ""
            h.append(f'<tr{sep}><td>{name} <span class="obs">({obs})</span></td>' + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
            prev = obs
        h.append("</tbody></table>")
        out.append('<div class="table-container">' + "".join(h) + "</div>")
    return "\n".join(out)


CAPTION = tex2html(re.search(r"\\caption\{(.*?)\}\n\\label\{tab:il_results\}", TABLE, re.S).group(1))


# ----------------------------------------------------------------------------------------------------- data viewer metadata
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
    "spray_graffiti": "Grasp the aerosol can and fill the stencil outline on the sheet of paper.",
    "put_bread_toaster": "Stand the slice of bread in a toaster slot and push the lever down.",
}
ORDER = ["reach", "lift", "push", "pick_place", "stack", "pick_place_mug", "pick_place_pan", "drill_to_point",
         "pick_place_fruit", "spray_graffiti", "put_bread_toaster"]
STAGE_NAMES = {"second_object": "second object", "insert": "insert", "press": "press lever", "aim": "aim", "fill": "fill"}
TASKS = []
for k in ORDER:
    t = next(x for x in STAGES["tasks"] if x["key"] == k)
    TASKS.append({"key": k, "name": t["task"], "track": 1 if "gripper" in t["embodiments"] else 2,
                  "blurb": BLURB[k], "seconds": t["horizon_steps"] // 20,
                  "success": t["success"].replace(">=", "\u2265").replace("<=", "\u2264").replace(" deg", "\u00b0").replace(" %", "%"),
                  "stages": [STAGE_NAMES.get(s, s) for s in t["required"]]})

CAROUSEL = [  # (clip, task, embodiment)
    ("pick_place_pan_franka_allegro", "Move Pan", "Allegro hand"),
    ("spray_graffiti_sharpa", "Spray Graffiti", "Sharpa hand"),
    ("pick_place_mug_franka_allegro", "Rack Mug", "Allegro hand"),
    ("put_bread_toaster_sharpa", "Toast Bread", "Sharpa hand"),
    ("drill_to_point_franka_allegro", "Drill to Point", "Allegro hand"),
    ("pick_place_fruit_franka_allegro", "Place Fruits", "Allegro hand"),
    ("pick_place_franka_franka_umi_tacticle", "Pick & Place", "UMI gripper"),
    ("lift_franka_allegro", "Lift", "Allegro hand"),
    ("push_franka_franka_umi_tacticle", "Push", "UMI gripper"),
]


def carousel_html() -> str:
    items = []
    for clip, task, emb in CAROUSEL:
        assert (SITE / f"static/videos/tasks/{clip}.mp4").exists(), clip
        items.append(f'''<div class="item">
                        <video poster="static/videos/tasks/{clip}.jpg" autoplay muted loop playsinline preload="auto">
                            <source src="static/videos/tasks/{clip}.mp4" type="video/mp4">
                        </video>
                        <span class="clip-label">{html.escape(task)} <span>{emb}</span></span>
                    </div>''')
    return "\n                    ".join(items)


def facts_html() -> str:
    facts = [(N_TASKS, "tasks"), (ARMS, "arms"), (EFFECTORS, "end-effectors"),
             (PAIRS, "benchmark task-embodiment pairs"), (EPISODES, "episodes")]
    return "".join(f'<div class="fact"><span class="fact-value">{v}</span><span class="fact-label">{l}</span></div>' for v, l in facts)


BIBTEX = f"""@article{{dexsuite2026,
  author  = {{Anonymous}},
  title   = {{{TITLE}}},
  journal = {{Under review}},
  year    = {{2026}},
}}"""

page = f"""<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="description" content="{html.escape(SUBTITLE)}. {N_TASKS} tasks, {ARMS} arms, {EFFECTORS} end-effectors, a benchmark of {PAIRS} task-embodiment pairs and {EPISODES} demonstration episodes.">
    <meta name="keywords" content="DexSuite, dexterous manipulation, simulation, benchmark, dataset, Genesis, teleoperation, imitation learning">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta property="og:title" content="{html.escape(TITLE)}">
    <meta property="og:description" content="{html.escape(SUBTITLE)}.">
    <meta property="og:image" content="static/images/paper/benchmark.jpg">
    <title>{html.escape(TITLE)}</title>
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-H0BF1KZ38G"></script>
    <script>
        window.dataLayer = window.dataLayer || [];
        function gtag() {{ dataLayer.push(arguments); }}
        gtag('js', new Date());
        gtag('config', 'G-H0BF1KZ38G');
    </script>
    <link href="https://fonts.googleapis.com/css?family=Google+Sans|Noto+Sans|Castoro" rel="stylesheet">
    <link rel="stylesheet" href="./static/css/bulma.min.css">
    <link rel="stylesheet" href="./static/css/bulma-carousel.min.css">
    <link rel="stylesheet" href="./static/css/fontawesome.all.min.css">
    <link rel="stylesheet" href="./static/css/index.css">
    <link rel="stylesheet" href="./static/css/site.css">
    <link rel="icon" href="./static/images/favicon.svg">
    <script src="https://ajax.googleapis.com/ajax/libs/jquery/3.5.1/jquery.min.js"></script>
    <script defer src="./static/js/fontawesome.all.min.js"></script>
    <script src="./static/js/bulma-carousel.min.js"></script>
    <script defer src="./static/js/site.js"></script>
    <script defer src="./static/js/data_viewer.js"></script>
</head>

<body>
    <section class="hero">
        <div class="hero-body">
            <div class="container is-max-desktop">
                <div class="columns is-centered">
                    <div class="column has-text-centered">
                        <h1 class="title is-1 publication-title has-text-centered mb-2">{html.escape(NAME)}</h1>
                        <h2 class="title is-3 publication-title has-text-centered mt-1">{html.escape(SUBTITLE).replace(" Across ", "<br>Across ")}</h2>
                        <div class="is-size-5 publication-authors">
                            <span class="author-block">Anonymous authors</span>
                        </div>
                        <div class="partner-logos mt-4">
                            <div class="logo-row research">
                                <img class="logo-mcgill" src="static/images/partners_logo/mcgill.png" alt="McGill University">
                                <img class="logo-mila" src="static/images/partners_logo/mila.png" alt="Mila">
                            </div>
                            <div class="logo-row industry mt-3">
                                <img class="logo-hf" src="static/images/partners_logo/hf.png" alt="Hugging Face">
                                <img class="logo-kinova" src="static/images/partners_logo/kinova.png" alt="Kinova">
                                <img class="logo-manus" src="static/images/partners_logo/manus.webp" alt="Manus">
                            </div>
                        </div>
                        <div class="publication-links">
                            <span class="link-block">
                                <a class="external-link button is-normal is-rounded coming-soon" aria-disabled="true">
                                    <span class="icon"><i class="fas fa-file-pdf"></i></span><span>Paper (coming soon)</span>
                                </a>
                            </span>
                            <span class="link-block">
                                <a class="external-link button is-normal is-rounded coming-soon" aria-disabled="true">
                                    <span class="icon"><i class="fab fa-github"></i></span><span>Code (coming soon)</span>
                                </a>
                            </span>
                            <span class="link-block">
                                <a href="{HF_ORG}" target="_blank" rel="noopener" class="external-link button is-normal is-rounded is-dark">
                                    <span class="icon"><i class="fas fa-database"></i></span><span>Data</span>
                                </a>
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <section class="hero is-light is-small">
        <div class="hero-body">
            <div class="container">
                <div id="results-carousel" class="carousel results-carousel">
                    {carousel_html()}
                </div>
            </div>
        </div>
    </section>

    <section class="section facts-section">
        <div class="container is-max-desktop">
            <div class="facts">{facts_html()}</div>
        </div>
    </section>

    <section class="section" id="abstract">
        <div class="container is-max-desktop">
            <div class="columns is-centered has-text-centered">
                <div class="column is-four-fifths">
                    <h2 class="title is-3">Abstract</h2>
                    <div class="content has-text-justified"><p>{ABSTRACT}</p></div>
                </div>
            </div>
        </div>
    </section>

    <section class="section" id="framework">
        <div class="container is-max-desktop">
            <h2 class="title is-3">DexSuite Framework</h2>
            <div class="content has-text-justified"><p>{FRAMEWORK}</p></div>
            <figure class="image paper-figure"><img src="static/images/paper/overview.png" alt="DexSuite architecture" loading="lazy"></figure>
        </div>
    </section>

    <section class="section" id="data-collection">
        <div class="container is-max-desktop">
            <h2 class="title is-3">Data Collection</h2>
            <h3 class="title is-5">Teleoperation</h3>
            <div class="content has-text-justified"><p>{TELEOP}</p></div>
            <div class="columns is-vcentered">
                <div class="column"><figure class="image paper-figure"><img src="static/images/paper/teleoperation_devices.png" alt="Teleoperation devices integrated in DexSuite" loading="lazy"></figure></div>
                <div class="column"><figure class="image paper-figure"><img src="static/images/retargeting.png" alt="Direct joint mapping or geometric retargeting to the robot hand" loading="lazy"></figure></div>
            </div>
            <div class="columns">
                <div class="column">
                    <video class="media-video" autoplay muted loop playsinline preload="metadata"><source src="static/videos/vivecontroller.mp4" type="video/mp4"></video>
                    <p class="media-caption">Vive tracker and controller for the wrist pose and the gripper.</p>
                </div>
                <div class="column">
                    <video class="media-video" autoplay muted loop playsinline preload="metadata"><source src="static/videos/manusretarget.mp4" type="video/mp4"></video>
                    <p class="media-caption">Manus glove to Allegro joint commands through geometric retargeting.</p>
                </div>
            </div>
            <h3 class="title is-5 mt-5">Tactile sensing</h3>
            <div class="content has-text-justified"><p>{TACTILE}</p></div>
            <figure class="image paper-figure narrow"><img src="static/images/paper/tac_fig_annotated.png" alt="Simulated FlexiTac readings on the UMI-style gripper" loading="lazy"></figure>
        </div>
    </section>

    <section class="section" id="dataset">
        <div class="container is-max-desktop">
            <h2 class="title is-3">Dataset</h2>
            <div class="columns is-vcentered">
                <div class="column is-7 content has-text-justified">
                    <p>{DATASET[0]}</p>
                    <p>{DATASET[1]}</p>
                    <p><a href="{HF_ORG}" target="_blank" rel="noopener">Browse the datasets on Hugging Face <i class="fas fa-arrow-right"></i></a></p>
                </div>
                <div class="column is-5"><figure class="image"><img src="static/images/paper/dataset_wheel.png" alt="Dataset composition by tier, embodiment and task" loading="lazy"></figure></div>
            </div>

            <h3 class="title is-4 mt-6" id="data-viewer">Data Viewer</h3>
            <p class="has-text-centered dv-intro">Sample episodes from the dataset, with the front and wrist cameras and the tool center point trajectory.</p>
            <div class="data-viewer" id="dv">
                <div class="dv-tasks" id="dv-tasks"></div>
                <div class="columns dv-body">
                    <div class="column is-7">
                        <div class="dv-video-wrap">
                            <video id="dv-video" muted autoplay loop playsinline preload="auto"></video>
                            <div class="dv-cams"><span>Front camera</span><span>Wrist camera</span></div>
                        </div>
                        <div class="dv-chart-wrap">
                            <p class="dv-chart-title">Tool center point position relative to the first frame (cm)</p>
                            <div class="dv-legend" id="dv-legend"></div>
                            <svg id="dv-chart" role="img" aria-label="Tool center point trajectory"></svg>
                            <div class="dv-tooltip" id="dv-tooltip" hidden></div>
                        </div>
                    </div>
                    <div class="column is-5">
                        <h4 class="dv-task-name" id="dv-name"></h4>
                        <p class="dv-blurb" id="dv-blurb"></p>
                        <div class="dv-control"><span class="dv-label">Embodiment</span><div class="dv-options" id="dv-emb"></div></div>
                        <div class="dv-control"><span class="dv-label">Source</span><div class="dv-options" id="dv-tier"></div></div>
                        <div class="dv-control"><span class="dv-label">Episode</span><div class="dv-options" id="dv-ep"></div></div>
                        <table class="dv-facts"><tbody id="dv-facts"></tbody></table>
                        <a class="button is-small is-rounded is-dark" id="dv-hf" target="_blank" rel="noopener">
                            <span class="icon"><i class="fas fa-database"></i></span><span>This dataset on Hugging Face</span>
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <section class="section" id="benchmark">
        <div class="container is-max-desktop">
            <h2 class="title is-3">Benchmark</h2>
            <div class="content has-text-justified">
                <p>{BENCH}</p>
                <p><strong>Track 1. Cross-embodiment evaluation.</strong> {TRACK1} <strong>Track 2. Multi-fingered dexterous capability.</strong> {TRACK2}</p>
            </div>
            <figure class="image paper-figure wide"><img src="static/images/paper/benchmark.jpg" alt="The {N_BENCH} benchmark tasks" loading="lazy"></figure>

            <h3 class="title is-4 mt-6">Imitation learning baselines</h3>
            <p class="table-caption">{CAPTION}</p>
            {table_html()}

            <h3 class="title is-4 mt-6">Where the policies fail</h3>
            <p class="has-text-centered dv-intro">Fifty diagnostic rollouts of the low-dimensional diffusion policy per task-embodiment pair, split by the stage in which each episode ends. Successes are in blue.</p>
            <figure class="image paper-figure narrow"><img src="static/images/paper/task_stages.png" alt="Stage-wise outcomes of the diffusion policies" loading="lazy"></figure>
        </div>
    </section>

    <section class="section" id="BibTeX">
        <div class="container is-max-desktop content">
            <h2 class="title">BibTeX</h2>
            <pre><code>{html.escape(BIBTEX)}</code></pre>
        </div>
    </section>

    <footer class="footer">
        <div class="container">
            <div class="content has-text-centered">
                <p>Website template borrowed from <a href="https://github.com/nerfies/nerfies.github.io">Nerfies</a> by <a href="https://keunhong.com/">Keunhong Park</a>.</p>
            </div>
        </div>
    </footer>
    <script>window.DEXSUITE_TASKS = {json.dumps(TASKS)};</script>
</body>

</html>
"""

(SITE / "index.html").write_text(page, encoding="utf-8")
print("index.html written:", len(page) // 1024, "KB |", TITLE, "|", EPISODES, "episodes |", PAIRS, "pairs")
