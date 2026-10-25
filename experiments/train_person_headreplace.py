"""Approach A (abandoned): replace the 80-class output layer with a new single-class layer and train for one epoch.
Reported in Section 3.6.1 as the reason Approach B (keep the pretrained output layer) was used."""
import json

import yaml
from ultralytics import YOLO

from common import DATA, OUT, SEED

yaml.safe_dump({"path": str(DATA / "voc_yolo"), "train": "train/images", "val": "val/images", "names": {0: "person"}}, open(DATA / "voc_person1.yaml", "w"))
m = YOLO("yolo11n.yaml").load("/home/user/poacher-guard/models/yolo11n.pt")   # transfers every layer except the class head
m.train(data=str(DATA / "voc_person1.yaml"), imgsz=512, batch=16, optimizer="AdamW", lr0=0.001, seed=SEED, deterministic=True, device="cpu", workers=2,
        epochs=1, plots=False, project=str(DATA / "runs"), name="person_headreplace", exist_ok=True, amp=False)
import pandas as pd
r = pd.read_csv(DATA / "runs" / "person_headreplace" / "results.csv"); r.columns = [c.strip() for c in r.columns]
out = {"epoch1_val_mAP50": float(r["metrics/mAP50(B)"].iloc[-1]), "epoch1_val_mAP50_95": float(r["metrics/mAP50-95(B)"].iloc[-1]), "epoch1_val_recall": float(r["metrics/recall(B)"].iloc[-1])}
(OUT / "headreplace.json").write_text(json.dumps(out, indent=1)); print(out)
