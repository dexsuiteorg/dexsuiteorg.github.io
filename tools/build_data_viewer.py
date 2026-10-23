#!/usr/bin/env python
"""Build the assets of the website data viewer from the released DexSuite datasets.

For every task, embodiment and collection tier of the paper's dataset, three episodes are cut from the LeRobot v3
videos (front and wrist cameras side by side, H.264 so every browser plays them) and the tool center point
trajectory is stored next to them. Human, scripted (UMI) and machine-generated sets are read from Hugging Face,
the two Sharpa sets from the local collection until they are uploaded.

    .venv-dexsuite/bin/python tools/build_data_viewer.py        (from the site root)

Writes static/data_viewer/manifest.json and static/data_viewer/clips/<id>.{mp4,json}.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

SITE = Path(__file__).resolve().parents[1]
OUT = SITE / "static" / "data_viewer"
CACHE = Path("/efs/projects/fudi/runs/website_update_20261023/hf_cache")
LOCAL = Path("/efs/projects/fudi/data/task_trajectories")
N_EPISODES = 3
CAMS = ("obs.cameras.front.rgb", "obs.cameras.wrist.rgb")
TCP = "obs.state.gripper.tcp_pos"

TASKS = [  # key, name, track
    ("reach", "Reach", 1), ("lift", "Lift", 1), ("push", "Push", 1), ("pick_place", "Pick & Place", 1),
    ("stack", "Stack", 1), ("pick_place_mug", "Rack Mug", 2), ("pick_place_pan", "Move Pan", 2),
    ("drill_to_point", "Drill to Point", 2), ("pick_place_fruit", "Place Fruits", 2),
    ("spray_graffiti", "Spray Graffiti", 2), ("put_bread_toaster", "Toast Bread", 2),
]
HAND_ONLY = {"pick_place_mug", "pick_place_pan", "drill_to_point", "pick_place_fruit"}


def sources():
    """(task, embodiment, tier, kind, location) for the 16 task-embodiment pairs of the paper."""
    for key, _, _ in TASKS:
        if key in ("spray_graffiti", "put_bread_toaster"):
            continue
        hands = [("Allegro hand", f"{key}_franka_allegro")]
        if key not in HAND_ONLY:
            grip = "reach_franka_robotiq" if key == "reach" else f"{key}_franka_franka_umi_tacticle"
            hands.insert(0, ("Robotiq gripper" if key == "reach" else "UMI gripper", grip))
        for emb, repo in hands:
            yield key, emb, "Human teleoperation", "hf", f"dexsuite/{repo}"
            if emb == "UMI gripper":
                yield key, emb, "Scripted expert", "hf", f"dexsuite/{repo}_scripted"
            yield key, emb, "Machine-generated", "hf", f"dexsuite/{repo}_mg"
    yield ("spray_graffiti", "Sharpa hand", "Scripted expert", "local",
           str(LOCAL / "sharpa-grasp-20260927-174805-188/spray"))
    yield ("put_bread_toaster", "Sharpa hand", "Scripted expert", "local",
           str(LOCAL / "sharpa-grasp-20260927-174743-28045/toaster_simple"))


class Dataset:
    """One LeRobot v3 dataset, on Hugging Face or on disk."""

    def __init__(self, kind: str, loc: str):
        self.kind, self.loc = kind, loc
        if kind == "local":  # a collection batch holds several shards; the first one carries enough episodes
            shard = sorted(p for p in Path(loc).glob("run-*") if p.is_dir())[0]
            self.root = shard / "lerobot"

    def path(self, rel: str) -> str:
        if self.kind == "local":
            return str(self.root / rel)
        from huggingface_hub import hf_hub_download
        return hf_hub_download(self.loc, rel, repo_type="dataset", cache_dir=str(CACHE))

    def read_columns(self, rel: str, columns: list[str]):
        if self.kind == "local":
            return pq.read_table(self.root / rel, columns=columns)
        from huggingface_hub import HfFileSystem
        fs = HfFileSystem()
        with fs.open(f"datasets/{self.loc}/{rel}", "rb") as f:  # range reads, only the two columns travel
            return pq.read_table(f, columns=columns)


def cut(video_paths, t0, t1, dst: Path):
    """Front and wrist cameras side by side, H.264, from t0 to t1 seconds of the concatenated v3 files."""
    cmd = ["ffmpeg", "-v", "error", "-y"]
    for p in video_paths:
        cmd += ["-ss", f"{t0:.3f}", "-to", f"{t1:.3f}", "-i", p]
    cmd += ["-filter_complex", "[0:v][1:v]hstack=inputs=2,format=yuv420p[v]", "-map", "[v]", "-an",
            "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-movflags", "+faststart", str(dst)]
    subprocess.run(cmd, check=True)


def build_one(key, emb, tier, kind, loc):
    ds = Dataset(kind, loc)
    eps = pq.read_table(ds.path("meta/episodes/chunk-000/file-000.parquet")).to_pylist()
    eps = sorted(eps, key=lambda e: e["episode_index"])[:N_EPISODES]
    out = []
    data_cache = {}
    for e in eps:
        cid = f"{key}__{emb.split()[0].lower()}__{tier.split()[0].lower()}__ep{e['episode_index']}"
        mp4, js = OUT / "clips" / f"{cid}.mp4", OUT / "clips" / f"{cid}.json"
        vids = []
        for cam in CAMS:
            rel = f"videos/{cam}/chunk-{e[f'videos/{cam}/chunk_index']:03d}/file-{e[f'videos/{cam}/file_index']:03d}.mp4"
            vids.append(ds.path(rel))
        t0, t1 = e[f"videos/{CAMS[0]}/from_timestamp"], e[f"videos/{CAMS[0]}/to_timestamp"]
        if not mp4.exists():
            cut(vids, t0, t1, mp4)
        drel = f"data/chunk-{e['data/chunk_index']:03d}/file-{e['data/file_index']:03d}.parquet"
        if drel not in data_cache:
            data_cache[drel] = ds.read_columns(drel, ["episode_index", TCP])
        tab = data_cache[drel]
        idx = np.asarray(tab.column("episode_index").to_numpy(zero_copy_only=False)).reshape(-1)
        tcp = np.stack(tab.column(TCP).to_numpy(zero_copy_only=False))[idx == e["episode_index"]].reshape(-1, 3)
        tcp = tcp[::2]  # 10 Hz is plenty for the chart
        js.write_text(json.dumps({"fps": 10, "tcp": np.round(tcp, 4).tolist()}))
        out.append({"id": cid, "episode": int(e["episode_index"]), "seconds": round(e["length"] / 20, 2)})
    return out


def main():
    (OUT / "clips").mkdir(parents=True, exist_ok=True)
    manifest = {"tasks": [{"key": k, "name": n, "track": t} for k, n, t in TASKS], "sets": []}
    for key, emb, tier, kind, loc in sources():
        try:
            clips = build_one(key, emb, tier, kind, loc)
        except Exception as exc:  # report and keep going, the manifest lists only what was built
            print(f"FAILED {key} {emb} {tier}: {exc}", file=sys.stderr, flush=True)
            continue
        manifest["sets"].append({"task": key, "embodiment": emb, "tier": tier,
                                 "hf": loc if kind == "hf" else None, "clips": clips})
        print(f"ok {key:18s} {emb:16s} {tier:20s} {len(clips)} clips", flush=True)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"{len(manifest['sets'])} sets")


if __name__ == "__main__":
    main()
