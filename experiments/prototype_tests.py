"""Software-in-the-loop prototype tests (Section 3.8.3, Table 3.10).

Runs the real VisionWorker and AlertEngine of the prototype on 3-second clips made from test photographs and records
whether an alert was raised, the time from the first frame containing a person to the alert, and the processing frame rate.
Camera hardware, BLE and flame hardware are NOT involved; those tests still need the field session.
"""
import json
import sys
import tempfile
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, "/home/user/poacher-guard")
from app.ble_registry import RangerRegistry  # noqa: E402
from app.config import load_config  # noqa: E402
from app.engine import AlertEngine  # noqa: E402
from app.store import EventStore  # noqa: E402
from app.vision import VisionWorker  # noqa: E402
from common import DATA, OUT  # noqa: E402

cfg = load_config()
cfg["vision"].update(model="/home/user/poacher-guard/models/yolo11n.pt", width=640, height=480)
tmp = Path(tempfile.mkdtemp())


def clip(img_path, n=30, size=(640, 480)):
    im = cv2.resize(cv2.imread(str(img_path)), size); out = tmp / (Path(img_path).stem + ".mp4")
    w = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), 10, size)
    for _ in range(n): w.write(im)
    w.release(); return str(out)


def run_once(video, timeout=8.0):
    c = json.loads(json.dumps(cfg)); c["vision"]["source"] = video
    store = EventStore(tmp / f"e_{time.time_ns()}.db"); reg = RangerRegistry([], 15, -90)
    got = {}; ev_ready = threading.Event()
    eng = AlertEngine(c, store, reg, publish=lambda m: (m.get("kind") == "event" and (got.setdefault("e", m["event"]), ev_ready.set())))
    w = VisionWorker(c, eng); t0 = time.time(); w.start(); ev_ready.wait(timeout); w.stop(); w.join(3)
    e = got.get("e"); return dict(alert=bool(e), latency_s=(e or {}).get("detail", {}).get("latency_s"), wall_s=time.time() - t0, type=(e or {}).get("type"))


def main(n=None):
    afr = pd.read_csv(OUT / "african_test_set.csv"); ctl = pd.read_csv(OUT / "control_test_set.csv")
    res = {}
    for name, df, d in (("african", afr, DATA / "oi_african"), ("control", ctl, DATA / "oi_control")):
        rows = []
        for r in (df if n is None else df.head(n)).itertuples():
            rows.append(run_once(clip(d / "images" / f"{r.ImageID}.jpg")))
        t = pd.DataFrame(rows); lat = t.latency_s.dropna()
        res[name] = dict(n=len(t), alerts=int(t.alert.sum()), alert_rate=float(t.alert.mean()), latency_mean=float(lat.mean()), latency_median=float(lat.median()),
                         latency_p95=float(lat.quantile(0.95)), latency_max=float(lat.max()))
        print(name, res[name], flush=True)
    # frame rate on a looping 60 s run (mixed African images)
    imgs = [cv2.resize(cv2.imread(str(DATA / "oi_african" / "images" / f"{i}.jpg")), (640, 480)) for i in afr.ImageID.head(30)]
    out = tmp / "mix.mp4"; w = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), 10, (640, 480))
    for im in imgs:
        for _ in range(20): w.write(im)
    w.release()
    c = json.loads(json.dumps(cfg)); c["vision"]["source"] = str(out); store = EventStore(tmp / "fps.db")
    eng = AlertEngine(c, store, RangerRegistry([], 15, -90)); w = VisionWorker(c, eng); w.start(); fps = []; t_end = time.time() + 70
    time.sleep(10)
    while time.time() < t_end: time.sleep(5); fps.append(w.status["fps"])
    w.stop(); res["fps"] = dict(mean=float(np.mean(fps)), min=float(np.min(fps)), max=float(np.max(fps)), samples=len(fps))
    print(res["fps"]); (OUT / "prototype_tests.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
