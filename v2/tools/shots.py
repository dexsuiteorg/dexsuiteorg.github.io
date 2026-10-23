#!/usr/bin/env python3
"""Shot list of the v2 site: writes v2/shots/<name>.json for render_replay.py.

    python3 v2/tools/shots.py            (writes every shot file)
"""
import json
from pathlib import Path

V2 = Path(__file__).resolve().parents[1]
W = V2 / "work"

# Franka scenes: robot base at the origin, table top at z = 0, objects around x 0.3-0.6
WIDE = {"loc": [1.95, -1.40, 1.05], "target": [0.33, 0.0, 0.30], "lens": 40}
MED = {"loc": [1.45, -1.05, 0.80], "target": [0.36, 0.02, 0.22], "lens": 42}
CLIPS = {
    "pan_allegro": {"camera": dict(WIDE, target=[0.30, 0.0, 0.26])},
    "mug_allegro": {"camera": MED},
    "drill_allegro": {"camera": {"loc": [1.35, -1.15, 0.85], "target": [0.35, 0.12, 0.30], "lens": 40}},
    "fruit_allegro": {"camera": dict(MED, target=[0.34, -0.05, 0.20])},
    "stack_allegro": {"camera": {"loc": [1.30, -0.95, 0.70], "target": [0.40, 0.05, 0.16], "lens": 45}},
    "pickplace_allegro": {"camera": {"loc": [1.40, -1.00, 0.75], "target": [0.36, 0.06, 0.18], "lens": 42}},
    "pickplace_umi": {"camera": {"loc": [1.40, -1.00, 0.75], "target": [0.36, 0.06, 0.18], "lens": 42}},
    "toast_sharpa": {"camera": {"loc": [1.30, -1.05, 0.78], "target": [0.47, 0.0, 0.24], "lens": 40}, "floor_z": -0.004,
                     "lights": "SHARPA"},
    "spray_sharpa": {"camera": {"loc": [1.25, -0.95, 0.62], "target": [0.5, -0.1, 0.12], "lens": 45}, "floor_z": -0.006,
                     "lights": "SHARPA"},
}
EE_CAM = {"loc": [1.02, -0.62, 0.78], "target": [0.36, 0.0, 0.52], "lens": 52}
ROBOT_LIGHTS = [
    {"type": "AREA", "energy": 520, "size": 3.5, "loc": [0.9, -1.3, 3.4], "target": [0.3, 0, 0.3]},
    {"type": "AREA", "energy": 110, "size": 4.0, "loc": [-2.2, 0.6, 1.6], "target": [0.3, 0, 0.4]},
    {"type": "AREA", "energy": 300, "size": 1.2, "loc": [-0.6, 2.2, 2.0], "target": [0.3, 0, 0.45]},
]


def write(name, scene, out, camera, res, samples, frames=None, **kw):
    shot = {"scene": str(scene), "out": str(out), "res": res, "samples": samples, "camera": camera,
            "hide_roles": ["floor", "table"], "floor_z": kw.pop("floor_z", -0.01), "floor_center": [0.4, 0.0]}
    if frames:
        shot["frames"] = frames
    shot.update(kw)
    (V2 / "shots").mkdir(exist_ok=True)
    (V2 / "shots" / f"{name}.json").write_text(json.dumps(shot, indent=1))


GRAPHITE = {"color": "#2b2d32", "rough": 0.42, "coat": 0.25}
OFFSET = [1.70, -1.45, 0.80]


def auto_wide(scene_path, bias=0.55, z=0.30, lens=38):
    """Wide Franka framing: target between the robot base and the task objects, same camera offset for every task."""
    import numpy as np
    sc = json.load(open(scene_path))
    objs = [np.array(m["frames"][len(m["frames"]) // 2])[:3, 3] for m in sc["meshes"] if m["role"].startswith("object")]
    c = np.mean(objs, 0) if objs else np.array([0.4, 0.0, 0.1])
    t = np.array([0.18 + bias * (c[0] - 0.18), bias * c[1], z])
    return {"loc": (t + np.array(OFFSET)).round(3).tolist(), "target": t.round(3).tolist(), "lens": lens}


SHARPA_LIGHTS = [
    {"type": "AREA", "energy": 380, "size": 3.0, "loc": [1.1, -0.7, 2.8], "target": [0.5, -0.05, 0.0]},
    {"type": "AREA", "energy": 90, "size": 4.0, "loc": [-2.0, 0.8, 1.6], "target": [0.5, 0, 0.2]},
    {"type": "AREA", "energy": 280, "size": 1.2, "loc": [-0.2, 2.0, 1.8], "target": [0.5, 0, 0.3]},
]


def main():
    for c in CLIPS.values():
        if c.get("lights") == "SHARPA":
            c["lights"] = SHARPA_LIGHTS
    for name in [n for n in CLIPS if n.endswith("_allegro") or n.endswith("_umi")]:
        CLIPS[name]["camera"] = auto_wide(W / "replays" / name / "scene.json")
        if name.endswith("_allegro"):
            CLIPS[name]["materials"] = {"hand": GRAPHITE}
    for name, c in CLIPS.items():
        extra = {k: v for k, v in c.items() if k != "camera"}
        hero = name == "spray_sharpa"
        write(name, W / "replays" / name / "scene.json", W / "frames" / name, c["camera"],
              [1920, 1080] if hero else [1600, 900], 128 if hero else 96, **extra)
    import numpy as np
    for d in sorted((W / "robots").iterdir()):
        if not (d / "scene.json").exists():
            continue
        sc = json.load(open(d / "scene.json"))
        if d.name.startswith("franka__"):            # end-effector close-up, same camera for all twelve
            write("ee_" + d.name.split("__")[1], d / "scene.json", W / "frames" / ("ee_" + d.name.split("__")[1]),
                  EE_CAM, [1400, 1400], 192, floor_z=0.0, lights=ROBOT_LIGHTS,
                  materials={"hand": GRAPHITE, "mount": GRAPHITE})
        if d.name.endswith("__robotiq") or d.name.endswith("__none"):   # whole robot, framed to fit
            P = np.array([np.array(m["frames"][0])[:3, 3] for m in sc["meshes"]])
            lo, hi = P.min(0), P.max(0)
            c = (lo + hi) / 2
            r = 0.5 * np.linalg.norm(hi - lo)
            dist = 1.3 * r / np.tan(np.radians(39.6 / 2))
            u = np.array([0.74, -0.60, 0.30]); u /= np.linalg.norm(u)
            cam = {"loc": (c + dist * u).round(3).tolist(), "target": c.round(3).tolist(), "lens": 50}
            pre = "rb_" if d.name.endswith("__robotiq") else "ib_"
            write(pre + d.name.split("__")[0], d / "scene.json", W / "frames" / (pre + d.name.split("__")[0]),
                  cam, [1400, 1400], 192, floor_z=0.0, lights=ROBOT_LIGHTS, floor_center=c[:2].round(3).tolist(),
                  materials={"hand": GRAPHITE, "mount": GRAPHITE})
        if d.name.endswith("__allegro"):              # whole arm, framed to fit
            P = np.array([np.array(m["frames"][0])[:3, 3] for m in sc["meshes"]])
            lo, hi = P.min(0), P.max(0)
            c = (lo + hi) / 2
            r = 0.5 * np.linalg.norm(hi - lo)
            dist = 1.25 * r / np.tan(np.radians(39.6 / 2))
            u = np.array([0.74, -0.60, 0.30]); u /= np.linalg.norm(u)
            cam = {"loc": (c + dist * u).round(3).tolist(), "target": c.round(3).tolist(), "lens": 50}
            write("arm_" + d.name.split("__")[0], d / "scene.json", W / "frames" / ("arm_" + d.name.split("__")[0]),
                  cam, [1400, 1400], 192, floor_z=0.0, lights=ROBOT_LIGHTS, floor_center=c[:2].round(3).tolist(),
                  materials={"hand": GRAPHITE, "mount": GRAPHITE})


if __name__ == "__main__":
    main()
    print("\n".join(sorted(p.name for p in (V2 / "shots").glob("*.json"))))
