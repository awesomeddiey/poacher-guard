"""Webcam worker: YOLO person (and weapon) detection -> AlertEngine.on_person.

Runs in its own thread. Keeps the newest annotated JPEG for the dashboard's
live view. A person must persist across several frames before it counts.
"""

from __future__ import annotations

import collections
import logging
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
        self.status = {"running": False, "fps": 0.0, "error": None, "people": 0}
        self._hist: collections.deque[bool] = collections.deque(maxlen=self.cfg.get("window_frames", 6))
        self.person_classes = {c.lower() for c in self.cfg.get("person_classes", ["person"])}
        self.weapon_classes = {c.lower() for c in self.cfg.get("weapon_classes", [])}

    def stop(self):
        self._stop.set()

    def latest_jpeg(self) -> bytes | None:
        with self._lock:
            return self._jpeg

    def _open(self):
        src = self.cfg.get("source", 0)
        cap = cv2.VideoCapture(src)
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
        while not self._stop.is_set():
            ok, frame = cap.read()
            if not ok:
                if isinstance(self.cfg.get("source", 0), str):  # video file: loop
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                time.sleep(0.2)
                continue
            n += 1
            if n % every == 0:
                boxes, weapon = self._detect(model, frame, conf)
                self._hist.append(bool(boxes))
                self.status["people"] = len(boxes)
                if sum(self._hist) >= need and boxes:
                    try:
                        self.engine.on_person(self._annotate(frame, boxes),
                                              boxes, weapon)
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
