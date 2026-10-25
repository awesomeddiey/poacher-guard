"""Split the annotated images into train / val / test by SUBJECT and write data.yaml.

    python training/split_dataset.py            # 70 / 20 / 10 by subject, seed 0

All frames of one volunteer land in one split, so the test result measures performance on
people the model never saw. Also writes results/dataset_stats.json and .png (Figure: dataset
composition by condition and split).
"""
import json
import random
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/poacher_dataset")
raw, seed = root / "raw", 0
imgs = sorted(p for p in raw.glob("*.jpg") if p.with_suffix(".txt").exists())
if not imgs:
    raise SystemExit(f"No annotated images (jpg + txt pairs) in {raw}")

def parts(p):
    t = p.stem.split("_")
    return (t[0], t[1] if len(t) > 2 else p.stem)  # condition, subject

subjects = sorted({parts(p)[1] for p in imgs})
random.Random(seed).shuffle(subjects)
n = len(subjects)
n_test, n_val = max(1, round(n * 0.1)), max(1, round(n * 0.2))
split_of = {s: "test" for s in subjects[:n_test]}
split_of.update({s: "val" for s in subjects[n_test:n_test + n_val]})
split_of.update({s: "train" for s in subjects[n_test + n_val:]})

for sp in ("train", "val", "test"):
    for k in ("images", "labels"):
        shutil.rmtree(root / k / sp, ignore_errors=True)
        (root / k / sp).mkdir(parents=True)
stats = {"images": Counter(), "boxes": defaultdict(Counter), "by_condition": defaultdict(Counter), "subjects": Counter(split_of.values())}
for p in imgs:
    cond, subj = parts(p)
    sp = split_of[subj]
    shutil.copy(p, root / "images" / sp / p.name)
    shutil.copy(p.with_suffix(".txt"), root / "labels" / sp / p.with_suffix(".txt").name)
    stats["images"][sp] += 1
    stats["by_condition"][cond][sp] += 1
    for line in p.with_suffix(".txt").read_text().split("\n"):
        if line.strip():
            stats["boxes"][sp]["weapon" if line.split()[0] == "1" else "person"] += 1

(root / "data.yaml").write_text(
    f"path: {root.resolve()}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: person\n  1: weapon\n")
out = Path("results"); out.mkdir(exist_ok=True)
(out / "dataset_stats.json").write_text(json.dumps(
    {"images": stats["images"], "boxes": {k: dict(v) for k, v in stats["boxes"].items()},
     "by_condition": {k: dict(v) for k, v in stats["by_condition"].items()}, "subjects": stats["subjects"]}, indent=2))
conds = sorted(stats["by_condition"])
fig, ax = plt.subplots(figsize=(7, 3.6))
bottom = [0] * len(conds)
for sp, col in (("train", "#1d4ed8"), ("val", "#60a5fa"), ("test", "#bfdbfe")):
    vals = [stats["by_condition"][c][sp] for c in conds]
    ax.bar(conds, vals, bottom=bottom, label=sp, color=col)
    bottom = [b + v for b, v in zip(bottom, vals)]
ax.set_ylabel("Images"); ax.set_xlabel("Capture condition"); ax.legend(); ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout(); fig.savefig(out / "dataset_stats.png", dpi=200)
print(json.dumps({"images": stats["images"], "subjects": stats["subjects"], "boxes": {k: dict(v) for k, v in stats["boxes"].items()}}, indent=1))
