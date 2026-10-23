#!/usr/bin/env python
"""Kinematic (open-loop) replay of one recorded DexSuite episode, exported for Blender.

The episode's own environment is built in Genesis, then for every recorded frame the robot joints are set to the
recorded joint positions and every task object to its recorded pose (articulated parts to their recorded joint
angles). Nothing is simulated. Every visual mesh of the scene is written once as a GLB (with its textures), and its
world pose is written for every frame, so Blender re-renders the recording exactly.

  .venv-dexsuite/bin/python v2/tools/export_replay.py --task pick_place_pan --manip franka --grip allegro \
      --source hf:dexsuite/pick_place_pan_franka_allegro --episode 0 --out v2/work/replays/pan_allegro

Writes <out>/scene.json (meshes, roles, per-frame 4x4 per mesh, frame rate, extra per-frame signals such as the spray
hits) and <out>/meshes/*.glb.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

sys.path.insert(0, "/efs/projects/fudi/simulation/Dexsuite")
os.environ.setdefault("PYOPENGL_PLATFORM", "egl")

# task entity attribute -> recorded field prefix (pose = <prefix>_pos, <prefix>_quat when present)
OBJECTS = {
    "reach": {"target_sphere": "target"},
    "lift": {"cube": "cube", "goal": "target"},
    "push": {"cube": "cube", "goal": "goal"},
    "pick_place": {"cube": "cube", "goal": "goal"},
    "stack": {"cube_a": "cube_a", "cube_b": "cube_b", "cube_c": "cube_c"},
    "pick_place_mug": {"mug": "mug", "rack": "rack"},
    "pick_place_pan": {"pan": "pan"},
    "drill_to_point": {"drill": "drill"},
    "pick_place_fruit": {"apple": "apple", "lemon": "lemon", "bowl": "bowl"},
    "spray_graffiti": {"can": "can"},
    "put_bread_toaster": {"toast": "toast", "toaster": "toaster"},
}
HIDE = {"pan_target", "drill_tip", "mat_collision"}       # invisible helpers / markers


def quat_to_R(q):  # wxyz
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def T_of(pos, quat):
    T = np.eye(4)
    T[:3, :3] = quat_to_R(np.asarray(quat, float))
    T[:3, 3] = np.asarray(pos, float)
    return T


class Source:
    """A LeRobot v3 dataset on Hugging Face (hf:<repo>) or on disk (a collection batch with run-*/lerobot shards)."""

    def __init__(self, spec: str):
        self.hf = spec.startswith("hf:")
        if self.hf:
            self.repo = spec[3:]
        else:
            self.root = sorted(p for p in Path(spec).glob("run-*") if p.is_dir())[0] / "lerobot"

    def path(self, rel):
        if not self.hf:
            return str(self.root / rel)
        from huggingface_hub import hf_hub_download
        return hf_hub_download(self.repo, rel, repo_type="dataset",
                               cache_dir="/efs/projects/fudi/runs/website_update_20261023/hf_cache")

    def info(self):
        return json.load(open(self.path("meta/info.json")))

    def episode(self, ep: int, columns):
        eps = pq.read_table(self.path("meta/episodes/chunk-000/file-000.parquet")).to_pylist()
        e = next(x for x in eps if x["episode_index"] == ep)
        rel = f"data/chunk-{e['data/chunk_index']:03d}/file-{e['data/file_index']:03d}.parquet"
        cols = ["episode_index"] + columns
        if self.hf:
            from huggingface_hub import HfFileSystem
            with HfFileSystem().open(f"datasets/{self.repo}/{rel}", "rb") as f:
                t = pq.read_table(f, columns=cols)
        else:
            t = pq.read_table(self.root / rel, columns=cols)
        idx = np.asarray(t.column("episode_index").to_numpy(zero_copy_only=False)).reshape(-1)
        keep = idx == ep
        out = {}
        for c in columns:
            rows = t.column(c).to_pylist()
            out[c] = np.array([np.asarray(r, dtype=np.float64).reshape(-1) for r, k in zip(rows, keep) if k])
        return out, e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--manip", required=True)
    ap.add_argument("--grip", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--episode", type=int, default=0)
    ap.add_argument("--stride", type=int, default=1)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    (out / "meshes").mkdir(parents=True, exist_ok=True)

    src = Source(a.source)
    feats = src.info()["features"]
    other = [k for k in feats if k.startswith("obs.state.other.") and feats[k]["dtype"].startswith("float")]
    cols = ["obs.state.manipulator.qpos", "obs.state.gripper.qpos"] + other
    if "obs.state.manipulator.eef_pos" in feats:
        cols += ["obs.state.manipulator.eef_pos", "obs.state.manipulator.eef_quat"]
    rec, emeta = src.episode(a.episode, cols)
    n = len(rec["obs.state.gripper.qpos"])
    frames = list(range(0, n, a.stride))
    if frames[-1] != n - 1:
        frames.append(n - 1)
    print(f"episode {a.episode}: {n} recorded frames, exporting {len(frames)}", flush=True)

    import genesis as gs  # noqa: F401
    import torch
    import dexsuite as ds
    env = ds.make(a.task, robot=ds.RobotOptions(single=ds.ArmOptions(manipulator=a.manip, gripper=a.grip)),
                  sim=ds.SimOptions(n_envs=1), cameras=ds.CamerasOptions(static={}, dynamic={}, modalities=("rgb",)),
                  render_mode=None)
    env.reset(seed=a.episode)
    scene = env.scene
    rob = env.robot
    for cand in (rob, getattr(rob, "single", None), getattr(rob, "robot", None), getattr(rob, "_robot", None)):
        if cand is not None and hasattr(cand, "arm_ent"):
            rob = cand
            break
    arm_ent, hand_ent = getattr(rob, "arm_ent", None), getattr(rob, "hand_ent", None)
    print("robot:", type(rob).__name__, getattr(arm_ent, "name", None), getattr(arm_ent, "n_dofs", None),
          getattr(hand_ent, "name", None), getattr(hand_ent, "n_dofs", None), flush=True)

    # entity roles
    attr_of = {}
    for name in dir(env.unwrapped):
        if name.startswith("_"):
            continue
        try:
            v = getattr(env.unwrapped, name)
        except Exception:
            continue
        if hasattr(v, "links") and hasattr(v, "uid"):
            attr_of[v.uid] = name
    robot_uids = {e.uid for e in (arm_ent, hand_ent) if e is not None}

    def role(e):
        if e.uid == getattr(arm_ent, "uid", None):
            return "arm"
        if e.uid == getattr(hand_ent, "uid", None):
            return "hand"
        nm = attr_of.get(e.uid, "")
        if nm:
            return "object:" + nm
        if a.task == "spray_graffiti" and e.uid == env.unwrapped.canvas.entity.uid:
            return "object:paper"
        fname = str(getattr(getattr(e, "morph", None), "file", "") or "")
        if "table" in getattr(e, "name", "").lower() or "Vention" in getattr(e, "name", ""):
            return "table"
        if "plane" in getattr(e, "name", "").lower():
            return "floor"
        return "prop:" + (Path(fname).stem if fname else getattr(e, "name", "entity"))

    def to_np(x):
        return x.detach().cpu().numpy() if hasattr(x, "detach") else np.asarray(x)

    def set_state(i):
        q_arm = rec["obs.state.manipulator.qpos"][i]
        q_hand = rec["obs.state.gripper.qpos"][i]
        if arm_ent is not None and arm_ent.n_dofs:
            arm_ent.set_dofs_position(torch.tensor(q_arm[:arm_ent.n_dofs], dtype=torch.float32))
        if hand_ent is not None and hand_ent.n_dofs:
            hand_ent.set_dofs_position(torch.tensor(q_hand[:hand_ent.n_dofs], dtype=torch.float32))
        for attr, pre in OBJECTS.get(a.task, {}).items():
            ent = getattr(env.unwrapped, attr, None)
            p, q = f"obs.state.other.{pre}_pos", f"obs.state.other.{pre}_quat"
            if ent is None or p not in rec:
                continue
            try:
                ent.set_pos(torch.tensor(rec[p][i], dtype=torch.float32))
                if q in rec:
                    ent.set_quat(torch.tensor(rec[q][i], dtype=torch.float32))
            except Exception as exc:  # fixed bases may refuse; their reset pose stays
                if i == 0:
                    print(f"  could not place {attr}: {exc}", flush=True)
        if a.task == "pick_place_pan" and i == frames[0]:      # static props from the recorded mat box (env layout)
            lo, hi = rec["obs.state.other.mat_inner_lo"][i], rec["obs.state.other.mat_inner_hi"][i]
            cx, cy = (lo + hi) / 2
            env.unwrapped.kitchen_mat.set_pos(torch.tensor([cx, cy, -0.005], dtype=torch.float32))
            env.unwrapped.hot_plate.set_pos(torch.tensor([cx, cy - 0.55, -0.01], dtype=torch.float32))
        if a.task == "drill_to_point" and i == frames[0]:      # the target rides on the wall: move the wall
            wall, tgt = env.unwrapped.wooden_wall, env.unwrapped.target
            off = to_np(tgt.get_pos()).reshape(-1)[:3] - to_np(wall.get_pos()).reshape(-1)[:3]
            wall.set_pos(torch.tensor(rec["obs.state.other.target_pos"][i] - off, dtype=torch.float32))
        if a.task == "spray_graffiti" and "obs.state.other.paper_pos" in rec:
            paper = env.unwrapped.canvas.entity
            paper.set_pos(torch.tensor(rec["obs.state.other.paper_pos"][i], dtype=torch.float32))
            paper.set_quat(torch.tensor(rec["obs.state.other.paper_quat"][i], dtype=torch.float32))
        if a.task == "put_bread_toaster":
            ts = env.unwrapped.toaster
            for jname, key in (("lever", "lever_q"), ("dial", "dial_q")):
                k = f"obs.state.other.{key}"
                if k in rec:
                    for jn in ts.joints:
                        if jname in jn.name and jn.n_dofs:
                            ts.set_dofs_position(torch.tensor([rec[k][i][0]], dtype=torch.float32), [jn.dofs_idx_local[0]])
        if a.task == "spray_graffiti" and "obs.state.other.head_q" in rec:
            can = env.unwrapped.can
            for jn in can.joints:
                if jn.n_dofs and "head" in jn.name:
                    can.set_dofs_position(torch.tensor([rec["obs.state.other.head_q"][i][0]], dtype=torch.float32), [jn.dofs_idx_local[0]])

    # meshes, once
    meshes = []
    for e in scene.entities:
        if not hasattr(e, "links"):
            continue
        r = role(e)
        if r == "floor" or (r.startswith("object:") and r.split(":", 1)[1] in HIDE):
            continue
        for link in e.links:
            for k, vg in enumerate(link.vgeoms):
                tm = vg.vmesh.trimesh.copy()
                name = f"{r.replace(':', '_')}__{link.name}__{k}".replace("/", "_").replace(" ", "_")
                path = out / "meshes" / f"{len(meshes):03d}_{name}.glb"
                try:
                    tm.export(path)
                except Exception:
                    tm.visual = tm.visual.to_color()
                    tm.export(path)
                col = None
                try:
                    c = getattr(vg.surface, "color", None)
                    col = None if c is None else [float(x) for x in np.asarray(c).reshape(-1)[:3]]
                except Exception:
                    pass
                meshes.append({"name": name, "glb": str(path.relative_to(out)), "role": r, "link": link.name,
                               "entity": getattr(e, "name", ""), "color": col,
                               "local": T_of(to_np(vg.init_pos), to_np(vg.init_quat)), "lk": link, "frames": []})
    print(f"{len(meshes)} meshes", flush=True)

    extra = {k.replace("obs.state.other.", ""): [] for k in rec if k.startswith("obs.state.other.") and
             any(s in k for s in ("spray_hit_xy", "spray_active", "paper_pos", "paper_quat", "stencil", "paint_coverage",
                                  "press_frac", "lever_frac", "nozzle"))}
    canvas = None
    if a.task == "spray_graffiti":      # re-run the env's own spray cone + splats on the recorded nozzle poses
        import dexsuite.environments.single.rigid.spray_graffiti as SG
        from PIL import Image
        canvas = env.unwrapped.canvas
        canvas.mask[:] = 0
        (out / "paint").mkdir(exist_ok=True)
        rng = np.random.default_rng(a.episode)
    fset = set(frames)
    paint_files = []
    for i in range(n) if canvas is not None else frames:
        if canvas is not None:
            paper = canvas.entity
            paper.set_pos(torch.tensor(rec["obs.state.other.paper_pos"][i], dtype=torch.float32))
            paper.set_quat(torch.tensor(rec["obs.state.other.paper_quat"][i], dtype=torch.float32))
            if rec["obs.state.other.spray_active"][i][0] > 0.5:
                uv, _ = canvas.spray_hits(rec["obs.state.other.nozzle_pos"][i], rec["obs.state.other.nozzle_dir"][i],
                                          half_angle_rad=SG.CONE_HALF_ANGLE, n_rays=SG.RAYS_PER_STEP,
                                          near=SG.SPRAY_NEAR, far=SG.SPRAY_FAR, rng=rng)
                canvas.splat(uv, SG.SPLAT_RADIUS, SG.SPLAT_STRENGTH)
            if i not in fset:
                continue
            canvas._compose()
            pf = f"paint/p{len(paint_files):04d}.png"
            Image.fromarray(np.ascontiguousarray(canvas.image[..., :3])).save(out / pf)
            paint_files.append(pf)
        set_state(i)
        for m in meshes:
            Tl = T_of(to_np(m["lk"].get_pos()).reshape(-1)[:3], to_np(m["lk"].get_quat()).reshape(-1)[:4])
            m["frames"].append(np.round(Tl @ m["local"], 6).tolist())
        for k in extra:
            extra[k].append(np.round(rec["obs.state.other." + k][i], 6).tolist())
    fps = 20.0 / a.stride
    allp = np.array([f[:3] for m in meshes if m["role"] in ("arm", "hand") or m["role"].startswith("object")
                     for f in [np.array(m["frames"][0])[:3, 3]]])
    scene_json = {"paint": paint_files, "task": a.task, "manip": a.manip, "grip": a.grip, "source": a.source, "episode": a.episode,
                  "recorded_frames": n, "frames": frames, "fps": fps, "extra": extra,
                  "bounds": [allp.min(0).tolist(), allp.max(0).tolist()],
                  "meshes": [{k: v for k, v in m.items() if k not in ("lk", "local")} for m in meshes]}
    (out / "scene.json").write_text(json.dumps(scene_json))
    print("wrote", out / "scene.json", flush=True)
    env.close()


if __name__ == "__main__":
    main()
