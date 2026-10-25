"""Capture still frames from the webcam (or a video file) into the raw image folder.

    python training/collect_frames.py --tag day-open --subject s01 --every 1.0 --max 120

File names follow  <condition>_<subject>_<index>.jpg  (for example day-open_s01_0007.jpg).
The condition tag drives the per-condition evaluation, and the subject code keeps all
frames of one volunteer in the same train/val/test split (no leakage between splits).
Use only volunteers who signed the consent form (docs/consent_form_template.md).
"""
import argparse
import time
from pathlib import Path

import cv2

ap = argparse.ArgumentParser()
ap.add_argument("--source", default="0", help="camera index or video file")
ap.add_argument("--tag", required=True, help="condition, e.g. day-open, dusk, night-ir, bush, occluded")
ap.add_argument("--subject", required=True, help="anonymous volunteer code, e.g. s01")
ap.add_argument("--every", type=float, default=1.0, help="seconds between saved frames")
ap.add_argument("--max", type=int, default=100)
ap.add_argument("--out", default="data/poacher_dataset/raw")
a = ap.parse_args()

out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
cap = cv2.VideoCapture(int(a.source) if a.source.isdigit() else a.source)
if not cap.isOpened():
    raise SystemExit("Cannot open the camera or video source")
start = len(list(out.glob(f"{a.tag}_{a.subject}_*.jpg")))
saved, last = 0, 0.0
print("Capturing... press Ctrl+C to stop early")
try:
    while saved < a.max:
        ok, frame = cap.read()
        if not ok:
            break
        if time.time() - last >= a.every:
            name = f"{a.tag}_{a.subject}_{start + saved:04d}.jpg"
            cv2.imwrite(str(out / name), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
            saved, last = saved + 1, time.time()
            print(f"saved {name}", end="\r")
except KeyboardInterrupt:
    pass
cap.release()
print(f"\n{saved} frames written to {out}")
