#!/usr/bin/env python
"""Export DexSuite robots at their home pose (one frame) for the v2 gallery renders.

Each combo is built with ds.make("reach", manipulator, gripper) and only the robot is kept (arm, hand, mount parts).

  .venv-dexsuite/bin/python v2/tools/export_robot.py --combos franka:allegro franka:leap ... --out v2/work/robots
writes <out>/<manip>__<grip>/scene.json (+ meshes/), the format render_replay.py reads.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

import numpy as np

sys.path.insert(0, "/efs/projects/fudi/simulation/Dexsuite")
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
from export_replay import T_of  # noqa: E402


def export(manip, grip, out: Path):
    import dexsuite as ds
    out.mkdir(parents=True, exist_ok=True)
    (out / "meshes").mkdir(exist_ok=True)
    env = ds.make("reach", robot=ds.RobotOptions(single=ds.ArmOptions(manipulator=manip, gripper=None if grip == "none" else grip)),
                  sim=ds.SimOptions(n_envs=1), cameras=ds.CamerasOptions(static={}, dynamic={}, modalities=("rgb",)),
                  render_mode=None)
    env.reset(seed=0)
    rob = env.robot
    for cand in (rob, getattr(rob, "single", None)):
        if cand is not None and hasattr(cand, "arm_ent"):
            rob = cand
            break
    robot_uids = {rob.arm_ent.uid, rob.hand_ent.uid}
    task_uids = {getattr(env.unwrapped, "target_sphere").uid}
    meshes = []
    for e in env.scene.entities:
        if not hasattr(e, "links") or e.uid in task_uids:
            continue
        name = getattr(e, "name", "").lower()
        if "plane" in name or "table" in name or "vention" in name:
            continue
        role = "arm" if e.uid == rob.arm_ent.uid else "hand" if e.uid == rob.hand_ent.uid else "mount"
        if rob.hand_ent is rob.arm_ent:           # integrated robot: its own gripper links count as the hand
            role = "arm"
        for link in e.links:
            for k, vg in enumerate(link.vgeoms):
                tm = vg.vmesh.trimesh.copy()
                nm = f"{role}__{link.name}__{k}".replace("/", "_").replace(" ", "_")
                path = out / "meshes" / f"{len(meshes):03d}_{nm}.glb"
                try:
                    tm.export(path)
                except Exception:
                    tm.visual = tm.visual.to_color()
                    tm.export(path)
                to_np = lambda x: x.detach().cpu().numpy() if hasattr(x, "detach") else np.asarray(x)  # noqa: E731
                Tl = T_of(to_np(link.get_pos()).reshape(-1)[:3], to_np(link.get_quat()).reshape(-1)[:4])
                Tg = Tl @ T_of(to_np(vg.init_pos), to_np(vg.init_quat))
                meshes.append({"name": nm, "glb": str(path.relative_to(out)), "role": role, "link": link.name,
                               "frames": [np.round(Tg, 6).tolist()]})
    pts = np.array([np.array(m["frames"][0])[:3, 3] for m in meshes])
    (out / "scene.json").write_text(json.dumps({"manip": manip, "grip": grip, "frames": [0], "fps": 20,
                                                "bounds": [pts.min(0).tolist(), pts.max(0).tolist()], "meshes": meshes}))
    env.close()
    print(f"ok {manip}+{grip}: {len(meshes)} meshes", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--combos", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    import genesis as gs  # noqa: F401
    for c in a.combos:
        manip, grip = c.split(":")
        dst = Path(a.out) / f"{manip}__{grip}"
        if (dst / "scene.json").exists():
            print("skip", c)
            continue
        try:
            export(manip, grip, dst)
        except Exception:
            print(f"FAILED {c}\n{traceback.format_exc()[-800:]}", flush=True)


if __name__ == "__main__":
    main()
