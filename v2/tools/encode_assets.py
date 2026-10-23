#!/usr/bin/env python
"""Rendered RGBA frames (v2/work/frames) -> web assets on white (v2/assets). Safe to re-run while renders are going:
only finished frames are converted, and a clip is encoded once all of its frames exist.

    .venv-dexsuite/bin/python v2/tools/encode_assets.py
"""
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

V2 = Path(__file__).resolve().parents[1]
FR, AS = V2 / "work" / "frames", V2 / "assets"
CLIPS = ["pickplace_umi", "pickplace_allegro", "pan_allegro", "mug_allegro", "drill_allegro", "fruit_allegro", "toast_sharpa"]


def on_white(p, size=None):
    im = Image.open(p).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    im = bg.convert("RGB")
    if size:
        im = im.resize(size, Image.LANCZOS)
    return im


def newer(src, dst):
    return not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime


def n_frames(shot):
    sh = json.load(open(V2 / "shots" / f"{shot}.json"))
    return len(json.load(open(sh["scene"]))["frames"])


def hero_source():
    """The reframed hero (scene on the right of the headline) once complete, else the first render."""
    done = len(list((FR / "spray_hero").glob("f*.png"))) if (FR / "spray_hero").exists() else 0
    return "spray_hero" if done >= n_frames("spray_hero") else "spray_sharpa"


def hero():
    out = AS / "hero"
    out.mkdir(parents=True, exist_ok=True)
    src = hero_source()
    stamp = out / "SOURCE"
    if not stamp.exists() or stamp.read_text() != src:     # switching source: re-encode everything
        for f in out.glob("*.webp"):
            f.unlink()
        stamp.write_text(src)
    k = 0
    for p in sorted((FR / src).glob("f*.png")):
        dst = out / (p.stem + ".webp")
        if newer(p, dst):
            on_white(p, (1600, 900)).save(dst, "WEBP", quality=80, method=5)
            k += 1
    print(f"hero: {k} new, {len(list(out.glob('*.webp')))}/{n_frames('spray_sharpa')} frames")


def stills(prefix, sub):
    out = AS / sub
    out.mkdir(parents=True, exist_ok=True)
    k = 0
    for d in sorted(FR.glob(prefix + "*")):
        p = d / "f0000.png"
        if p.exists():
            dst = out / (d.name[len(prefix):] + ".webp")
            if newer(p, dst):
                on_white(p, (1100, 1100)).save(dst, "WEBP", quality=86, method=5)
                k += 1
    print(f"{sub}: {k} new, {len(list(out.glob('*.webp')))} total")


def clip(name):
    src, out = FR / name, AS / "clips"
    out.mkdir(parents=True, exist_ok=True)
    n = n_frames(name)
    have = sorted(src.glob("f*.png")) if src.exists() else []
    if have:   # poster from the frame nearest two thirds of the way in
        mid = min(have, key=lambda p: abs(int(p.stem[1:]) - int(0.66 * n)))
        if newer(mid, out / f"{name}.jpg"):
            on_white(mid, (1600, 900)).save(out / f"{name}.jpg", quality=86)
    if len(have) < n:
        print(f"clip {name}: {len(have)}/{n} frames, waiting")
        return
    mp4 = out / f"{name}.mp4"
    if mp4.exists() and mp4.stat().st_mtime > max(p.stat().st_mtime for p in have):
        print(f"clip {name}: up to date")
        return
    with tempfile.TemporaryDirectory() as tmp:
        for i, p in enumerate(have):
            on_white(p).save(f"{tmp}/c{i:04d}.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "20", "-i", f"{tmp}/c%04d.png",
                        "-vf", "tpad=stop_mode=clone:stop_duration=1,format=yuv420p", "-c:v", "libx264", "-preset", "slow",
                        "-crf", "21", "-movflags", "+faststart", str(mp4)], check=True)
    print(f"clip {name}: wrote {mp4.name} ({mp4.stat().st_size // 1024} KB)")


def hero_layers():
    """The hand and the paper as separate transparent sequences, composited by the page."""
    for layer, size in (("hand", (1400, 1050)), ("paper", (1280, 880))):
        src, out = FR / f"hero_{layer}", AS / "hero" / layer
        out.mkdir(parents=True, exist_ok=True)
        k = 0
        for p in sorted(src.glob("f*.png")) if src.exists() else []:
            dst = out / (p.stem + ".webp")
            if newer(p, dst):
                Image.open(p).convert("RGBA").resize(size, Image.LANCZOS).save(dst, "WEBP", quality=82, alpha_quality=90, method=5)
                k += 1
        print(f"hero {layer}: {k} new, {len(list(out.glob('*.webp')))}/{n_frames('hero_' + layer)}")


def robots():
    out = AS / "robots"
    out.mkdir(parents=True, exist_ok=True)
    for d in sorted(list(FR.glob("ib_*")) + list(FR.glob("rb_*")) + list(FR.glob("ee_*"))):
        ps = sorted(d.glob("f*.png"))
        if ps and newer(ps[0], out / f"{d.name}.webp"):
            on_white(ps[0], (1100, 1100)).save(out / f"{d.name}.webp", "WEBP", quality=86, method=5)
    print("robots:", len(list(out.glob("*.webp"))))


def thumbs():
    out = AS / "thumbs"
    out.mkdir(parents=True, exist_ok=True)
    srcs = {t: next(iter(sorted((FR / f"th_{t}").glob("f*.png"))), None) for t in ("reach", "lift", "push", "stack")
            if (FR / f"th_{t}").exists()}
    srcs["spray_graffiti"] = FR / "spray_sharpa" / "f0200.png"
    for t, p in srcs.items():
        if p and p.exists() and newer(p, out / f"{t}.jpg"):
            on_white(p, (1200, 675)).save(out / f"{t}.jpg", quality=86)
    for name, t in (("pan_allegro", "pick_place_pan"), ("mug_allegro", "pick_place_mug"), ("drill_allegro", "drill_to_point"),
                    ("fruit_allegro", "pick_place_fruit"), ("toast_sharpa", "put_bread_toaster"), ("pickplace_allegro", "pick_place")):
        p = AS / "clips" / f"{name}.jpg"
        if p.exists() and newer(p, out / f"{t}.jpg"):
            Image.open(p).resize((1200, 675), Image.LANCZOS).save(out / f"{t}.jpg", quality=86)
    print("thumbs:", sorted(x.stem for x in out.glob("*.jpg")))


if __name__ == "__main__":
    hero_layers()
    robots()
    thumbs()
    for c in CLIPS:
        clip(c)
