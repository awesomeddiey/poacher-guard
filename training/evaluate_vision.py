"""Evaluate the poacher detection model on the held-out TEST split.

    python training/evaluate_vision.py --weights runs/poacher/weights/best.pt \
        --baseline models/yolo11n.pt --data data/poacher_dataset/data.yaml

Produces, in results/:
  vision_results.json / vision_results.md   overall + per-condition + per-subject person metrics
  predictions_grid.jpg                      test images with ground truth (green) and predictions (red)
Person metrics are computed at the deployment confidence (config.yaml vision.confidence) with
IoU >= 0.5 matching. The optional baseline is the pretrained model run on the same images, so the
benefit of fine-tuning on the local dataset can be reported honestly.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import yaml
from ultralytics import YOLO

ap = argparse.ArgumentParser()
ap.add_argument("--weights", required=True)
ap.add_argument("--baseline", default=None)
ap.add_argument("--data", default="data/poacher_dataset/data.yaml")
ap.add_argument("--split", default="test")
ap.add_argument("--conf", type=float, default=0.45)
a = ap.parse_args()

d = yaml.safe_load(open(a.data))
root = Path(d["path"])
img_dir, lab_dir = root / d[a.split], root / d[a.split].replace("images", "labels")
imgs = sorted(img_dir.glob("*.jpg"))
if not imgs:
    raise SystemExit(f"No images in {img_dir}")
Path("results").mkdir(exist_ok=True)


def iou(a_, b_):
    x1, y1, x2, y2 = max(a_[0], b_[0]), max(a_[1], b_[1]), min(a_[2], b_[2]), min(a_[3], b_[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    u = (a_[2] - a_[0]) * (a_[3] - a_[1]) + (b_[2] - b_[0]) * (b_[3] - b_[1]) - inter
    return inter / u if u else 0.0


def gt_boxes(p, w, h, cls=0):
    f = lab_dir / (p.stem + ".txt")
    out = []
    for line in f.read_text().splitlines() if f.exists() else []:
        c, x, y, bw, bh = line.split()
        if int(c) == cls:
            x, y, bw, bh = float(x) * w, float(y) * h, float(bw) * w, float(bh) * h
            out.append([x - bw / 2, y - bh / 2, x + bw / 2, y + bh / 2])
    return out


def run(weights, tag):
    model = YOLO(weights)
    pid = next(i for i, n in model.names.items() if str(n).lower() == "person")
    tot = defaultdict(lambda: np.zeros(3))  # tp, fp, fn
    by_cond, by_subj, grid = defaultdict(lambda: np.zeros(3)), defaultdict(lambda: np.zeros(3)), []
    for p in imgs:
        im = cv2.imread(str(p)); h, w = im.shape[:2]
        gts = gt_boxes(p, w, h)
        r = model.predict(im, conf=a.conf, classes=[pid], verbose=False)[0]
        preds = [b.xyxy[0].tolist() for b in r.boxes]
        used, tp = set(), 0
        for g in gts:
            best, bi = 0, None
            for i, pr in enumerate(preds):
                if i not in used and iou(g, pr) > best:
                    best, bi = iou(g, pr), i
            if best >= 0.5:
                used.add(bi); tp += 1
        v = np.array([tp, len(preds) - tp, len(gts) - tp])
        t = p.stem.split("_")
        for key, tab in ((t[0], by_cond), (t[1] if len(t) > 2 else p.stem, by_subj), ("all", tot)):
            tab[key] += v
        if len(grid) < 12:
            vis = im.copy()
            for g in gts: cv2.rectangle(vis, tuple(map(int, g[:2])), tuple(map(int, g[2:])), (60, 200, 60), 3)
            for pr in preds: cv2.rectangle(vis, tuple(map(int, pr[:2])), tuple(map(int, pr[2:])), (40, 40, 230), 2)
            grid.append(cv2.resize(vis, (480, 360)))
    def m(v):
        tp, fp, fn = v
        return {"images_gt_boxes": int(tp + fn), "tp": int(tp), "fp": int(fp), "fn": int(fn),
                "precision": round(tp / (tp + fp), 4) if tp + fp else None,
                "recall": round(tp / (tp + fn), 4) if tp + fn else None}
    return {"overall": m(tot["all"]), "by_condition": {k: m(v) for k, v in sorted(by_cond.items())},
            "by_subject": {k: m(v) for k, v in sorted(by_subj.items())}}, grid


res = {"split": a.split, "n_images": len(imgs), "confidence": a.conf}
res["fine_tuned"], grid = run(a.weights, "fine_tuned")
if a.baseline:
    res["baseline"], _ = run(a.baseline, "baseline")
if d.get("names") and a.split in d:
    m = YOLO(a.weights).val(data=a.data, split=a.split, verbose=False, plots=True, project="runs", name="poacher_eval", exist_ok=True)
    res["ultralytics_val"] = {"precision": float(m.box.mp), "recall": float(m.box.mr), "mAP50": float(m.box.map50), "mAP50_95": float(m.box.map)}
Path("results/vision_results.json").write_text(json.dumps(res, indent=2))
rows = ["| Condition | Model | GT persons | Precision | Recall |", "|---|---|---|---|---|"]
for key in ("fine_tuned", "baseline"):
    if key in res:
        for c, v in {"all": res[key]["overall"], **res[key]["by_condition"]}.items():
            rows.append(f"| {c} | {key} | {v['images_gt_boxes']} | {v['precision']} | {v['recall']} |")
Path("results/vision_results.md").write_text("\n".join(rows) + "\n")
if grid:
    while len(grid) % 4: grid.append(np.zeros_like(grid[0]))
    cv2.imwrite("results/predictions_grid.jpg", np.vstack([np.hstack(grid[i:i + 4]) for i in range(0, len(grid), 4)]))
print("\n".join(rows)); print("Saved results/vision_results.json, vision_results.md, predictions_grid.jpg")
