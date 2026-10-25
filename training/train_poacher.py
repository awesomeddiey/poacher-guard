"""Fine-tune YOLO on your own poacher/ranger/weapon images.

1. Label images (Roboflow / CVAT / labelImg) in YOLO format with classes such as:
       0 poacher   1 weapon   2 snare
2. Put them in the Ultralytics layout and write data.yaml (see training/data.example.yaml).
3. python training/train_poacher.py data.yaml
4. In config.yaml set vision.model: runs/poacher/weights/best.pt
   (person_classes / weapon_classes in config.yaml must match your class names)

Tip: train on night/IR frames, camouflage, distance shots and partial occlusion;
that is what the field looks like. The BLE tag, not the model, decides who is a ranger.
"""
import sys

from ultralytics import YOLO

data = sys.argv[1] if len(sys.argv) > 1 else "data.yaml"
model = YOLO("yolo11n.pt")
model.train(data=data, epochs=80, imgsz=640, batch=16, project="runs", name="poacher", exist_ok=True)
print("Best weights: runs/poacher/weights/best.pt")
