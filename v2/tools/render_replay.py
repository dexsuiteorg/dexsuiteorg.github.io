"""Render an exported replay (export_replay.py) with Blender Cycles on a white studio backdrop.

    CUDA_VISIBLE_DEVICES=2 /tmp/hoirfig/bpyenv/bin/python v2/tools/render_replay.py v2/shots/pan_hero.json

A shot file: {"scene": <scene.json>, "out": <frames dir>, "res": [w, h], "samples": 128,
              "camera": {"loc": [...], "target": [...], "lens": 50} or {"orbit": {...}},
              "frames": [start, stop, step] (scene frame indices), "look": "studio" | ..., "hide_roles": [...],
              "materials": {role or mesh-name prefix: material spec}}
Uses the material, light and shadow-catcher helpers of scripts/analysis/hoir_pipeline_figure/render_blender.py.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, "/efs/projects/fudi/scripts/analysis/hoir_pipeline_figure")
import bpy  # noqa: E402
import numpy as np  # noqa: E402
import render_blender as RB  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

Z_UP = Matrix.Rotation(-math.pi / 2, 4, "X")

LOOKS = {
    "studio": {
        "world": {"color": "#ffffff", "strength": 0.22},
        "lights": [
            {"type": "AREA", "energy": 470, "size": 3.2, "loc": [1.6, -2.2, 3.2], "target": [0.35, 0, 0.25]},
            {"type": "AREA", "energy": 95, "size": 4.0, "loc": [-2.4, 0.8, 1.8], "target": [0.35, 0, 0.3]},
            {"type": "AREA", "energy": 320, "size": 1.2, "loc": [-0.6, 2.4, 2.2], "target": [0.35, 0, 0.35]},
            {"type": "AREA", "energy": 160, "size": 3.0, "loc": [0.4, 0.0, 3.5], "target": [0.4, 0, 0.0]},
        ],
    },
}


def orbit_cam(o, t):
    """Camera on a circle around `target`: azimuth from a0 to a1 (deg) over t in [0, 1], fixed elevation and radius."""
    ease = 0.5 - 0.5 * math.cos(math.pi * t)
    az = math.radians(o["a0"] + (o["a1"] - o["a0"]) * ease)
    el = math.radians(o.get("el", 25))
    r = o["radius"] + (o.get("radius1", o["radius"]) - o["radius"]) * ease
    tg = np.array(o["target"], float)
    loc = tg + r * np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])
    return loc.tolist(), tg.tolist()


def main(shot_path, only=None, samples=None, scale=1.0):
    shot = json.load(open(shot_path))
    scene = json.load(open(shot["scene"]))
    root = Path(shot["scene"]).parent
    out = Path(shot["out"])
    out.mkdir(parents=True, exist_ok=True)
    job = {"res": [int(round(r * scale)) for r in shot["res"]], "samples": samples or shot.get("samples", 128),
           "out": str(out / "f0000.png"), "exposure": shot.get("exposure", 0.0)}
    sc = RB.setup(job)
    sc.render.use_persistent_data = True
    sc.view_settings.view_transform = shot.get("view_transform", "AgX")
    sc.view_settings.look = shot.get("view_look", "None")
    look = LOOKS[shot.get("look", "studio")]
    RB.add_world(shot.get("world", look["world"]))
    RB.add_lights(shot.get("lights", look["lights"]))
    cam = shot["camera"]
    track = None
    if "track" in cam:                            # follow the centroid of some meshes, offset rotating about z
        tr = cam["track"]
        sel = [m for m in scene["meshes"] if any(m["role"] == r or m["role"].startswith(r + ":") for r in tr["roles"])]
        C = np.array([[np.array(m["frames"][f])[:3, 3] for m in sel] for f in range(len(scene["frames"]))]).mean(1)
        k = int(tr.get("smooth", 9))
        pad = np.concatenate([np.repeat(C[:1], k, 0), C, np.repeat(C[-1:], k, 0)])
        C = np.array([pad[i:i + 2 * k + 1].mean(0) for i in range(len(C))]) + np.array(tr.get("target_offset", [0, 0, 0]))
        track = (C, np.array(tr["offset"], float), tr.get("orbit", [0, 0]))
        cam = {"loc": (C[0] + track[1]).tolist(), "target": C[0].tolist(), "lens": cam.get("lens", 50),
               "shift_x": cam.get("shift_x", 0), "shift_y": cam.get("shift_y", 0)}
    if "orbit" not in cam:
        RB.add_camera(cam)
    else:
        loc, tg = orbit_cam(cam["orbit"], 0.0)
        RB.add_camera({"loc": loc, "target": tg, "lens": cam.get("lens", 50)})
    camobj = bpy.context.scene.camera
    if shot.get("shadow_catcher", True):
        RB.add_shadow_catcher({"size": 6, "z": shot.get("floor_z", 0.0), "center": shot.get("floor_center", (0.4, 0))})

    hide = set(shot.get("hide_roles", ["floor"]))
    mats = shot.get("materials", {})
    moving = []
    paint_nodes = []
    for m in scene["meshes"]:
        if m["role"] in hide or any(m["name"].startswith(h) for h in shot.get("hide_names", [])):
            continue
        if shot.get("only_roles") and not any(m["role"] == r or m["role"].startswith(r + ":") for r in shot["only_roles"]):
            continue
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(root / m["glb"]))
        holder = bpy.data.objects.new(m["name"], None)
        bpy.context.scene.collection.objects.link(holder)
        spec = None
        for key in (m["name"], m["role"], m["role"].split(":")[0]):
            for k, v in mats.items():
                if key == k or (k.endswith("*") and key.startswith(k[:-1])):
                    spec = v
                    break
            if spec:
                break
        for ob in set(bpy.data.objects) - before - {holder}:
            if ob.parent is None:
                mw = ob.matrix_world.copy()
                ob.parent = holder
                ob.matrix_parent_inverse = Matrix.Identity(4)
                ob.matrix_basis = Z_UP @ mw   # the glTF importer turns our Z-up meshes as if they were Y-up
            if ob.type == "MESH":
                if spec:
                    ob.data.materials.clear()
                    ob.data.materials.append(RB.material(m["name"] + "_mat", spec))
                elif len(ob.data.color_attributes):   # sim colours come as vertex colours (COLOR_0)
                    base = shot.get("vertex_color_material", {"rough": 0.38, "coat": 0.15})
                    ob.data.materials.clear()
                    ob.data.materials.append(RB.material(m["name"] + "_vc", dict(base, attr=ob.data.color_attributes[0].name)))
                ob.data.shade_smooth() if spec and spec.get("smooth") else None
        moving.append((holder, m["frames"]))
        if m["role"] == "object:paper" and scene.get("paint"):
            for ob in holder.children_recursive:
                if ob.type != "MESH":
                    continue
                for slot in ob.material_slots:
                    nt = slot.material.node_tree if slot.material else None
                    for node in (nt.nodes if nt else []):
                        if node.type == "TEX_IMAGE":
                            paint_nodes.append(node)

    n = len(scene["frames"])
    lo, hi, st = shot.get("frames", [0, n, 1])
    if only:
        lo, hi, st = only
    idx = list(range(lo, min(hi, n), st))
    for j, f in enumerate(idx):
        if (out / f"f{f:04d}.png").exists() and not shot.get("overwrite"):
            continue
        for holder, fr in moving:
            holder.matrix_world = Matrix(fr[f])
        if "orbit" in cam:
            loc, tg = orbit_cam(cam["orbit"], j / max(1, len(idx) - 1))
            RB.look_at(camobj, loc, tg)
        if track is not None:
            C, off, (a0, a1) = track
            t = f / max(1, n - 1)
            az = math.radians(a0 + (a1 - a0) * (0.5 - 0.5 * math.cos(math.pi * t)))
            Rz = np.array([[math.cos(az), -math.sin(az), 0], [math.sin(az), math.cos(az), 0], [0, 0, 1]])
            RB.look_at(camobj, (C[f] + Rz @ off).tolist(), C[f].tolist())
        if paint_nodes:
            img = bpy.data.images.load(str(root / scene["paint"][f]), check_existing=True)
            for node in paint_nodes:
                old = node.image
                node.image = img
                if old is not None and old != img and old.users == 0:
                    bpy.data.images.remove(old)
        dst = out / f"f{f:04d}.png"           # named by scene frame, so frame ranges can run on several GPUs
        if dst.exists() and not shot.get("overwrite"):
            continue
        sc.render.filepath = str(dst)
        bpy.ops.render.render(write_still=True)
        print(f"frame {j + 1}/{len(idx)}", flush=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    only = samples = None
    scale = 1.0
    if "--frames" in args:
        only = tuple(int(x) for x in args[args.index("--frames") + 1].split(":"))
    if "--samples" in args:
        samples = int(args[args.index("--samples") + 1])
    if "--scale" in args:
        scale = float(args[args.index("--scale") + 1])
    main(args[0], only, samples, scale)
