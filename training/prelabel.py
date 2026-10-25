"""Draft the person boxes with the pretrained model so annotation is a correction job.

    python training/prelabel.py

Reads data/poacher_dataset/raw/*.jpg and writes YOLO-format .txt files beside them
(class 0 = person). Open the folder in the annotation tool (CVAT, labelImg or Roboflow),
CORRECT every box and add class 1 = weapon by hand. Pre-labels are drafts, never ground truth:
an annotator must review every image. Record how many boxes were corrected (see
docs/annotation_guide.md) so the correction rate can be reported.
"""
import sys
from pathlib import Path

from ultralytics import YOLO

raw = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/poacher_dataset/raw")
model = YOLO("models/yolo11n.pt")
(raw / "classes.txt").write_text("person\nweapon\n")
n_img = n_box = 0
for img in sorted(raw.glob("*.jpg")):
    r = model.predict(str(img), conf=0.25, classes=[0], verbose=False)[0]
    lines = []
    for b in r.boxes:
        x, y, w, h = b.xywhn[0].tolist()
        lines.append(f"0 {x:.6f} {y:.6f} {w:.6f} {h:.6f}")
    img.with_suffix(".txt").write_text("\n".join(lines) + ("\n" if lines else ""))
    n_img, n_box = n_img + 1, n_box + len(lines)
print(f"{n_box} draft boxes written for {n_img} images. Now review every image by hand.")
