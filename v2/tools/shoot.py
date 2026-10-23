"""Scroll through the v2 page in headless Chromium and take a screenshot at several scroll positions.

    /tmp/hoirfig/bpyenv/bin/python v2/tools/shoot.py [url] [--w 1440 --h 900] [--out dir]
Writes <out>/s00.png ... and a contact sheet <out>/sheet.jpg.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROME = "/efs/projects/fudi/.pw-browsers/chromium-1243/chrome-linux64/chrome"
args = sys.argv[1:]
url = args[0] if args and not args[0].startswith("--") else "http://localhost:8770/"
W = int(args[args.index("--w") + 1]) if "--w" in args else 1440
H = int(args[args.index("--h") + 1]) if "--h" in args else 900
out = Path(args[args.index("--out") + 1]) if "--out" in args else Path("/efs/projects/fudi/runs/website_update_20261023/shots/v2scroll")
out.mkdir(parents=True, exist_ok=True)
for p in out.glob("s*.png"):
    p.unlink()

with sync_playwright() as pw:
    exe = CHROME if Path(CHROME).exists() else None
    b = pw.chromium.launch(executable_path=exe, args=["--autoplay-policy=no-user-gesture-required", "--use-angle=swiftshader"])
    pg = b.new_page(viewport={"width": W, "height": H})
    logs = []
    pg.on("console", lambda m: logs.append(f"{m.type}: {m.text}"))
    pg.on("pageerror", lambda e: logs.append(f"pageerror: {e}"))
    pg.goto(url, wait_until="networkidle")
    pg.wait_for_timeout(1500)
    total = pg.evaluate("document.documentElement.scrollHeight")
    ys = list(range(0, total - H + 1, int(H * 0.9)))
    shots = []
    for k, y in enumerate(ys):
        pg.evaluate(f"window.scrollTo(0, {y})")
        pg.wait_for_timeout(700)
        p = out / f"s{k:02d}.png"
        pg.screenshot(path=str(p))
        shots.append(p)
    b.close()

from PIL import Image  # noqa: E402
ims = [Image.open(p).convert("RGB") for p in shots]
tw = 480
th = int(H * tw / W)
cols = 4
sheet = Image.new("RGB", (cols * (tw + 8), ((len(ims) + cols - 1) // cols) * (th + 8)), "#888")
for k, im in enumerate(ims):
    sheet.paste(im.resize((tw, th)), ((k % cols) * (tw + 8), (k // cols) * (th + 8)))
sheet.save(out / "sheet.jpg", quality=82)
print(f"page height {total}, {len(shots)} shots -> {out}/sheet.jpg")
print("\n".join(logs[:20]) or "no console messages")
