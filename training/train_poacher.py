"""Fine-tune YOLO11n on the annotated person / weapon dataset.

    python training/split_dataset.py
    python training/train_poacher.py data/poacher_dataset/data.yaml

Writes runs/poacher/ with results.png (training curves), confusion_matrix.png, PR_curve.png and
weights/best.pt. Point config.yaml -> vision.model at runs/poacher/weights/best.pt afterwards.
Classes describe what is VISIBLE (person, weapon). Whether a person is a poacher or a ranger
is decided by the alert engine from the BLE tag, never from appearance.
"""
import json
import sys

from ultralytics import YOLO

data = sys.argv[1] if len(sys.argv) > 1 else "data/poacher_dataset/data.yaml"
cfg = dict(data=data, epochs=80, imgsz=640, batch=16, patience=20, seed=0, project="runs", name="poacher", exist_ok=True)
YOLO("models/yolo11n.pt").train(**cfg)
with open("results/train_config.json", "w") as f:
    json.dump(cfg, f, indent=2)
print("Best weights: runs/poacher/weights/best.pt")
