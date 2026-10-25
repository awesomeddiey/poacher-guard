"""Create the Label Studio project (classes: person, vehicle, animal) and import an African test image with its boxes."""
import json
import sys
from pathlib import Path

import cv2
import requests

BASE = "http://localhost:8099"
S = requests.Session()
S.get(f"{BASE}/user/login/")
r = S.post(f"{BASE}/user/login/", data={"email": "researcher@example.com", "password": "poacherguard2026", "csrfmiddlewaretoken": S.cookies["csrftoken"]}, headers={"Referer": f"{BASE}/user/login/"})
assert r.status_code in (200, 302), r.status_code
H = {"X-CSRFToken": S.cookies["csrftoken"], "Referer": BASE}
DATA = Path("/tmp/claude-0/data/oi_african")
cfg = """<View>
  <Image name="image" value="$image" zoom="true"/>
  <RectangleLabels name="label" toName="image">
    <Label value="person" background="#2563eb"/>
    <Label value="vehicle" background="#16a34a"/>
    <Label value="animal" background="#f59e0b"/>
  </RectangleLabels>
</View>"""
p = S.post(f"{BASE}/api/projects", headers=H, json={"title": "Poacher Guard: person detection", "label_config": cfg}); p.raise_for_status(); pid = p.json()["id"]
tasks = []
for iid in sys.argv[1:]:
    im = cv2.imread(str(DATA / "images" / f"{iid}.jpg")); h, w = im.shape[:2]; res = []
    for k, l in enumerate((DATA / "labels" / f"{iid}.txt").read_text().split("\n")):
        if not l.strip(): continue
        _, x, y, bw, bh = map(float, l.split())
        res.append({"id": f"b{k}", "type": "rectanglelabels", "from_name": "label", "to_name": "image", "original_width": w, "original_height": h, "image_rotation": 0,
                    "value": {"x": (x - bw / 2) * 100, "y": (y - bh / 2) * 100, "width": bw * 100, "height": bh * 100, "rotation": 0, "rectanglelabels": ["person"]}})
    tasks.append({"data": {"image": f"http://127.0.0.1:8100/{iid}.jpg"}, "annotations": [{"result": res}]})
r = S.post(f"{BASE}/api/projects/{pid}/import?commit_to_project=true", headers=H, json=tasks); r.raise_for_status()
t = S.get(f"{BASE}/api/projects/{pid}/tasks?page_size=10", headers=H).json()
print(json.dumps({"project": pid, "tasks": [(x["id"], x["data"]["image"]) for x in (t["tasks"] if isinstance(t, dict) else t)]}))
