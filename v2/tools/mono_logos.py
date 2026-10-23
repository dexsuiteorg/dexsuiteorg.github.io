#!/usr/bin/env python
"""Partner logos in one ink colour for the footer: v2/assets/logos/<name>.png.

Each logo keeps its shape and its light/dark structure (darkest part = full ink, white = transparent), so details such as
the McGill crest or the Hugging Face face survive. Amazon is the official logo (Wikimedia Commons SVG, rasterised to amazon.png).
    .venv-dexsuite/bin/python v2/tools/mono_logos.py
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

V2 = Path(__file__).resolve().parents[1]
SRC, OUT = V2.parent / "static/images/partners_logo", V2 / "assets/logos"
FONTS = Path("/efs/projects/fudi/scripts/analysis/hoir_pipeline_figure/fonts")
INK = (90, 90, 96)
H = 120                                            # stored height; shown at ~34 px


def mono(im, solid=False):
    a = np.asarray(im.convert("RGBA"), np.float32)
    lum = a[..., :3] @ np.array([0.299, 0.587, 0.114], np.float32)
    seen = a[..., 3] > 16
    lo = np.percentile(lum[seen], 2) if seen.any() else 0
    ink = (a[..., 3] / 255) if solid else np.clip((255 - lum) / max(1.0, 255 - lo), 0, 1) * (a[..., 3] / 255)
    out = np.zeros(a.shape, np.uint8)
    out[..., :3] = INK
    out[..., 3] = (ink * 255).astype(np.uint8)
    im = Image.fromarray(out)
    return im.crop(im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox())


def wordmark(text):
    f = ImageFont.truetype(str(FONTS / "Inter-Bold.ttf"), 200)
    w = int(f.getlength(text)) + 40
    im = Image.new("RGBA", (w, 280), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((20, 20), text, font=f, fill=(0, 0, 0, 255))
    return im


OUT.mkdir(parents=True, exist_ok=True)
for name, im in (("mcgill", Image.open(SRC / "mcgill.png")), ("mila", Image.open(SRC / "mila.png")), ("amazon", Image.open(SRC / "amazon.png")),
                 ("hf", Image.open(SRC / "hf.png")), ("kinova", Image.open(SRC / "kinova.png")), ("manus", Image.open(SRC / "manus.webp"))):
    m = mono(im, solid=name == "amazon")   # the smile is a second colour, not a highlight: one ink
    m = m.resize((round(m.width * H / m.height), H), Image.LANCZOS)
    m.save(OUT / f"{name}.png", optimize=True)
    print(name, m.size)
