"""Build the VOC 2007 person-detection subsets used in Chapter 3 (Table 3.2).

Training: 1,200 trainval images with people + 400 trainval images without people.
Validation: 300 random images from the rest of trainval. Test: 1,000 random images from the VOC 2007 test list.
Objects flagged 'difficult' are excluded. Labels are written in YOLO format (class 0 = person).
"""
import json
import random
import xml.etree.ElementTree as ET
from pathlib import Path

from common import DATA, OUT, SEED

root = DATA / "voc" / "VOCdevkit" / "VOC2007"
dst = DATA / "voc_yolo"


def read_ids(name):
    return [l.strip() for l in (root / "ImageSets" / "Main" / f"{name}.txt").read_text().split() if l.strip()]


def persons(img_id):
    t = ET.parse(root / "Annotations" / f"{img_id}.xml").getroot()
    W, H = int(t.find("size/width").text), int(t.find("size/height").text)
    boxes, any_person = [], False
    for o in t.findall("object"):
        if o.find("name").text != "person":
            continue
        any_person = True
        if o.find("difficult").text == "1":
            continue
        b = o.find("bndbox"); x1, y1, x2, y2 = (float(b.find(k).text) for k in ("xmin", "ymin", "xmax", "ymax"))
        boxes.append((0, (x1 + x2) / 2 / W, (y1 + y2) / 2 / H, (x2 - x1) / W, (y2 - y1) / H))
    return boxes, any_person


def write(split, ids):
    (dst / split / "images").mkdir(parents=True, exist_ok=True); (dst / split / "labels").mkdir(parents=True, exist_ok=True)
    n_box = n_img_p = 0
    for i in ids:
        boxes, _ = persons(i)
        link = dst / split / "images" / f"{i}.jpg"
        if not link.exists(): link.symlink_to(root / "JPEGImages" / f"{i}.jpg")
        (dst / split / "labels" / f"{i}.txt").write_text("".join(f"{c} {x:.6f} {y:.6f} {w:.6f} {h:.6f}\n" for c, x, y, w, h in boxes))
        n_box += len(boxes); n_img_p += bool(boxes)
    return {"images": len(ids), "images_with_people": n_img_p, "person_boxes": n_box}


rng = random.Random(SEED)
tv = read_ids("trainval"); rng.shuffle(tv)
with_p = [i for i in tv if persons(i)[0]]
without = [i for i in tv if not persons(i)[1]]
train = with_p[:1200] + without[:400]
rest = [i for i in tv if i not in set(train)]
rng.shuffle(rest); val = rest[:300]
test_ids = read_ids("test"); rng.shuffle(test_ids); test = test_ids[:1000]
summary = {"train": write("train", train), "val": write("val", val), "test": write("test", test)}
(OUT / "voc_summary.json").write_text(json.dumps(summary, indent=2)); print(json.dumps(summary, indent=1))
