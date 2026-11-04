"""Webcam worker: YOLO person (and weapon) detection -> AlertEngine.on_person.

Runs in its own thread. Keeps the newest annotated JPEG for the dashboard's
live view. A person must persist across several frames before it counts.
"""

from __future__ import annotations

import collections
import logging
import os
import platform
import threading
import time
from typing import Any

import cv2

from .config import resolve

log = logging.getLogger("vision")


class VisionWorker(threading.Thread):
    def __init__(self, cfg: dict[str, Any], engine):
        super().__init__(daemon=True, name="vision")
        self.cfg = cfg["vision"]
        self.engine = engine
        self._stop = threading.Event()
        self._jpeg: bytes | None = None
        self._lock = threading.Lock()
        self.status = {"running": False, "fps": 0.0, "error": None, "people": 0,
                       "detections": [], "weapon": False, "model": self.cfg.get("model", "")}
        self._hist: collections.deque[bool] = collections.deque(maxlen=self.cfg.get("window_frames", 6))
        self.person_classes = {c.lower() for c in self.cfg.get("person_classes", ["person"])}
        self.weapon_classes = {c.lower() for c in self.cfg.get("weapon_classes", [])}

    def stop(self):
        self._stop.set()

    def latest_jpeg(self) -> bytes | None:
        with self._lock:
            return self._jpeg

    def _backend(self):
        return cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY   # DirectShow opens USB webcams faster on Windows

    def _pick_source(self):
        """PG_CAMERA (environment) overrides config. 'auto' = the last working camera index, which is the USB webcam when the
        laptop also has a built-in camera (built-in is index 0)."""
        src = os.environ.get("PG_CAMERA") or self.cfg.get("source", 0)
        if isinstance(src, str) and src.strip().isdigit(): src = int(src)
        if src != "auto": return src
        found = []
        for i in range(5):
            c = cv2.VideoCapture(i, self._backend())
            if c.isOpened() and c.read()[0]: found.append(i)
            c.release()
        log.info("cameras found: %s", found)
        return found[-1] if found else 0

    def _open(self):
        src = self.cfg["source"] = self._pick_source()
        cap = cv2.VideoCapture(src, self._backend()) if isinstance(src, int) else cv2.VideoCapture(src)
        if isinstance(src, int):
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg.get("width", 640))
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.get("height", 480))
        return cap

    def run(self):
        try:
            from ultralytics import YOLO
            mp = resolve(self.cfg.get("model", "models/yolo11n.pt"))
            # A bare name like "yolo11n.pt" lets ultralytics download it on first run.
            model = YOLO(str(mp) if mp and mp.exists() else mp.name)
        except Exception as e:  # noqa: BLE001
            self.status.update(error=f"model load failed: {e}")
            log.exception("YOLO load failed")
            return
        cap = self._open()
        if not cap.isOpened():
            self.status.update(error=f"cannot open camera/source {self.cfg.get('source', 0)!r}")
            log.error(self.status["error"])
            return
        self.status.update(running=True, error=None)
        conf = self.cfg.get("confidence", 0.45)
        every = max(1, self.cfg.get("infer_every_n_frames", 2))
        need = self.cfg.get("confirm_frames", 3)
        n, t0, shown, boxes = 0, time.time(), 0, []
        weapon = False
        first_seen = None  # read time of the first frame of the current sighting (for alert latency)
        while not self._stop.is_set():
            ok, frame = cap.read()
            if not ok:
                if isinstance(self.cfg.get("source", 0), str):  # video file: loop
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                time.sleep(0.2)
                continue
            n += 1
            t_read = time.time()
            if n % every == 0:
                boxes, weapon = self._detect(model, frame, conf)
                self._hist.append(bool(boxes))
                if boxes and first_seen is None: first_seen = t_read
                if not any(self._hist):
                    first_seen = None
                    self.engine.on_clear()
                self.status["people"] = sum(1 for b in boxes if b["label"] in self.person_classes)
                self.status["detections"] = [{"label": b["label"], "conf": b["conf"]} for b in boxes][:12]
                self.status["weapon"] = weapon
                if sum(self._hist) >= need and boxes:
                    try:
                        latency = time.time() - first_seen if first_seen else None
                        ev = self.engine.on_person(self._annotate(frame, boxes), boxes, weapon, latency_s=latency)
                        if ev and latency is not None:
                            self.status["last_latency_s"] = round(latency, 3)
                    except Exception:  # noqa: BLE001
                        log.exception("engine.on_person failed")
            shown += 1
            if time.time() - t0 >= 2:
                self.status["fps"] = round(shown / (time.time() - t0), 1)
                t0, shown = time.time(), 0
            ok, buf = cv2.imencode(".jpg", self._annotate(frame, boxes), [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                with self._lock:
                    self._jpeg = buf.tobytes()
        cap.release()
        self.status["running"] = False

    def _detect(self, model, frame, conf):
        res = model.predict(frame, conf=conf, verbose=False)[0]
        names = res.names
        boxes, weapon = [], False
        for b in res.boxes:
            label = str(names[int(b.cls)]).lower()
            item = {"label": label, "conf": round(float(b.conf), 3),
                    "xyxy": [round(float(v)) for v in b.xyxy[0].tolist()]}
            if label in self.person_classes:
                boxes.append(item)
            elif label in self.weapon_classes:
                weapon = True
                boxes.append(item)
        return boxes, weapon

    @staticmethod
    def _annotate(frame, boxes):
        out = frame.copy()
        for b in boxes:
            x1, y1, x2, y2 = b["xyxy"]
            cv2.rectangle(out, (x1, y1), (x2, y2), (40, 40, 230), 2)
            cv2.putText(out, f"{b['label']} {b['conf']:.2f}", (x1, max(14, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (40, 40, 230), 2)
        return out
