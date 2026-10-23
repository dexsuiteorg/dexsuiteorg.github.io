#!/usr/bin/env python
"""Rendered RGBA frames (v2/work/frames) -> web assets (v2/assets), on white or transparent. Safe to re-run while renders are going:
only finished frames are converted, and a clip is encoded once all of its frames exist.

    .venv-dexsuite/bin/python v2/tools/encode_assets.py
"""
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
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


def hero_scene(size=1200):
    """The hero: hand, can and paper from one fixed camera, transparent."""
    src, out = FR / "hero_scene", AS / "hero" / "scene"
    out.mkdir(parents=True, exist_ok=True)
    k = 0
    for p in sorted(src.glob("f*.png")) if src.exists() else []:
        dst = out / (p.stem + ".webp")
        if newer(p, dst):
            Image.open(p).convert("RGBA").resize((size, size), Image.LANCZOS).save(dst, "WEBP", quality=80, alpha_quality=88, method=5)
            k += 1
    print(f"hero scene: {k} new, {len(list(out.glob('*.webp')))}/{n_frames('hero_scene')}")


FONTS = Path("/efs/projects/fudi/scripts/analysis/hoir_pipeline_figure/fonts")


def og_card(frame=200):
    """1200x630 link preview: the wordmark in DexSuite blue, one line, the Sharpa hand mid-spray."""
    from PIL import ImageDraw, ImageFont
    S = 2                                             # draw at 2x, downsample
    W, H = 1200 * S, 630 * S
    card = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    im = Image.open(FR / "hero_scene" / f"f{frame:04d}.png").convert("RGBA")
    im = im.crop(im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox())
    k = min(540 * S / im.height, 470 * S / im.width)   # right of the text block, never under it
    im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    card.alpha_composite(im, (W - im.width - 44 * S, (H - im.height) // 2))
    big = ImageFont.truetype(str(FONTS / "Inter-Bold.ttf"), 132 * S)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).text((72 * S, 196 * S), "DexSuite", font=big, fill=255)
    grad = np.zeros((H, W, 3), np.float32)
    t = np.clip((np.arange(W) - 72 * S) / (560 * S), 0, 1)[None, :, None]
    c0, c1 = np.array([0x14, 0x68, 0xb8], np.float32), np.array([0x45, 0xb2, 0xee], np.float32)
    grad[:] = c0 + (c1 - c0) * t
    card.paste(Image.fromarray(grad.astype(np.uint8)), (0, 0), mask)
    d = ImageDraw.Draw(card)
    med = ImageFont.truetype(str(FONTS / "Inter-Medium.ttf"), 34 * S)
    d.text((76 * S, 372 * S), "An all-in-one framework", font=med, fill=(29, 29, 31))
    d.text((76 * S, 416 * S), "for dexterous manipulation", font=med, fill=(29, 29, 31))
    sm = ImageFont.truetype(str(FONTS / "Inter-Medium.ttf"), 22 * S)
    d.text((76 * S, 490 * S), "30 tasks   10 arms   12 end-effectors   4,700 episodes", font=sm, fill=(110, 110, 115))
    card.convert("RGB").resize((1200, 630), Image.LANCZOS).save(AS / "og.jpg", quality=90)
    print("og card written")


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


def fit_on_floor(im, size=1100, fill=0.80, bottom=0.14):
    """Trim a transparent render to its content and stand it, centred, on one baseline shared by every arm."""
    im = im.crop(im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox())
    k = min(size * fill / im.width, size * fill / im.height)
    im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.alpha_composite(im, ((size - im.width) // 2, size - round(size * bottom) - im.height))
    return out


def edge_fade(im, s=1.0, left=0.18, bottom=0.24):
    """The close-ups cut the arm at the left and bottom edges: fade it out there instead of a hard edge."""
    a = np.asarray(im.getchannel("A"), np.float32)
    h, w = a.shape
    sm = lambda x: x * x * (3 - 2 * x)  # noqa: E731
    mx = sm(np.clip(np.arange(w) / (left * w), 0, 1))[None, :]
    my = sm(np.clip((h - 1 - np.arange(h)) / (bottom * h), 0, 1))[:, None]
    im.putalpha(Image.fromarray((a * (1 - s * (1 - mx * my))).astype(np.uint8)))
    return im


def robots():
    """Robot stills from the shadow-free renders (ns_*), transparent. The arms are fitted to one baseline; the hands keep
    the shared Franka-wrist camera, so one dissolves into the next. The Franka arm shot is already framed by its camera
    (it is the first frame of the fly-in to the wrist)."""
    out = AS / "robots"
    out.mkdir(parents=True, exist_ok=True)
    for d in sorted(FR.glob("ns_*")):
        ps, name = sorted(d.glob("f*.png")), d.name[3:]
        dst = out / f"{name}.webp"
        if ps and newer(ps[0], dst):
            im = Image.open(ps[0]).convert("RGBA")
            if name.startswith(("ib_", "rb_")) and name != "rb_franka":
                im = fit_on_floor(im)
            else:
                im = im.resize((1100, 1100), Image.LANCZOS)
                if name.startswith("ee_"):
                    im = edge_fade(im)
            im.save(dst, "WEBP", quality=88, alpha_quality=95, method=5)
    print("robots:", len(list(out.glob("*.webp"))))


def zoom(n=40):
    """Fly-in from the whole Franka to its wrist: frame 0 is the arm still, the last frame is the Robotiq close-up."""
    out = AS / "robots" / "zoom"
    out.mkdir(parents=True, exist_ok=True)
    src = [FR / "ns_rb_franka"] + [FR / "zoom" / f"k{i:02d}" for i in range(1, n - 1)] + [FR / "ns_ee_robotiq"]
    have = 0
    for i, d in enumerate(src):
        p, dst = d / "f0000.png", out / f"z{i:02d}.webp"
        if p.exists():
            have += 1
            if newer(p, dst):
                im = edge_fade(Image.open(p).convert("RGBA").resize((1100, 1100), Image.LANCZOS), s=i / (n - 1))
                im.save(dst, "WEBP", quality=84, alpha_quality=92, method=5)
    print(f"zoom: {have}/{n}")


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
    hero_scene()
    og_card()
    robots()
    zoom()
    thumbs()
    for c in CLIPS:
        clip(c)
