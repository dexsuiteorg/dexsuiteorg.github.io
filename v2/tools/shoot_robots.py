"""Step through the #robots section in headless Chromium and screenshot each position, to check the transitions.

    /tmp/hoirfig/bpyenv/bin/python v2/tools/shoot_robots.py [--n 96] [--w 1440 --h 900] [--out dir]
Writes <out>/r000.png ..., <out>/robots.mp4 (the frames in order) and <out>/sheet.jpg (every 4th frame).
"""
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROME = "/efs/projects/fudi/.pw-browsers/chromium-1243/chrome-linux64/chrome"
args = sys.argv[1:]
opt = lambda k, d: type(d)(args[args.index(k) + 1]) if k in args else d  # noqa: E731
N, W, H = opt("--n", 96), opt("--w", 1440), opt("--h", 900)
out = Path(opt("--out", "/efs/projects/fudi/runs/website_update_20261023/shots/robots"))
out.mkdir(parents=True, exist_ok=True)
for p in out.glob("r*.png"):
    p.unlink()

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME if Path(CHROME).exists() else None, args=["--use-angle=swiftshader"])
    pg = b.new_page(viewport={"width": W, "height": H})
    logs = []
    pg.on("pageerror", lambda e: logs.append(f"pageerror: {e}"))
    pg.goto("http://localhost:8770/v2/", wait_until="networkidle")
    pg.wait_for_timeout(1500)
    top, span = pg.evaluate("(() => { const s = document.querySelector('#robots'); return [s.offsetTop, s.offsetHeight - innerHeight]; })()")
    for k in range(N):
        pg.evaluate(f"window.scrollTo({{top: {top + span * k / (N - 1)}, behavior: 'instant'}})")
        pg.wait_for_timeout(900)
        pg.screenshot(path=str(out / f"r{k:03d}.png"))
    b.close()

subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "12", "-i", str(out / "r%03d.png"), "-vf", "scale=960:-2,format=yuv420p",
                "-c:v", "libx264", "-crf", "22", str(out / "robots.mp4")], check=True)
from PIL import Image  # noqa: E402
ims = [Image.open(out / f"r{k:03d}.png").convert("RGB") for k in range(0, N, 4)]
tw, th, cols = 480, int(H * 480 / W), 4
sheet = Image.new("RGB", (cols * (tw + 6), ((len(ims) + cols - 1) // cols) * (th + 6)), "#888")
for k, im in enumerate(ims):
    sheet.paste(im.resize((tw, th)), ((k % cols) * (tw + 6), (k // cols) * (th + 6)))
sheet.save(out / "sheet.jpg", quality=82)
print(f"{N} frames -> {out}", "\n".join(logs) or "no page errors")
