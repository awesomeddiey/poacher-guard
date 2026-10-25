"""Fine-tune YOLO11n (COCO weights) on the VOC 2007 person subset. Section 3.6.1, Table 3.4.

Approach B (reported): keep the original 80-class output layer and its pretrained weights, train on images in
which only people are labelled. Approach A (abandoned after one epoch, see train_person_headreplace.py)
replaced the output layer with a new single-class layer.
"""
import json
import sys
import time

import yaml
from ultralytics import YOLO

from common import DATA, OUT, SEED

ROOT = DATA / "voc_yolo"
model = YOLO("/home/user/poacher-guard/models/yolo11n.pt")
names = model.names                                    # 80 COCO names, person = 0
yaml.safe_dump({"path": str(ROOT), "train": "train/images", "val": "val/images", "test": "test/images",
                "names": {int(k): v for k, v in names.items()}}, open(DATA / "voc_person80.yaml", "w"))
budget_h = float(sys.argv[1]) if len(sys.argv) > 1 else 0.8
t0 = time.time()
cfg = dict(data=str(DATA / "voc_person80.yaml"), imgsz=512, batch=16, optimizer="AdamW", lr0=0.001, seed=SEED,
           deterministic=True, device="cpu", workers=2, time=budget_h, epochs=30, patience=100, plots=False,
           project=str(DATA / "runs"), name="person_ft", exist_ok=True, amp=False)
model.train(**cfg)
(OUT / "train_person_config.json").write_text(json.dumps({**cfg, "wall_minutes": round((time.time() - t0) / 60, 1)}, indent=2))
print("done", round((time.time() - t0) / 60, 1), "min")
