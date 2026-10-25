"""Laptop-mic gunshot detector.

Streams 16 kHz mono audio, scores each ~1 s window with YAMNet (TFLite), and
raises a gunshot alert when the gunshot-class score crosses the threshold.

Two scoring modes:
  * zero-shot  - max score over YAMNet's own gunshot classes (works out of the box)
  * custom head - a small classifier trained on YAMNet's 521 class scores with your own
                  recordings (training/train_gunshot.py). Used automatically
                  when models/gunshot_head.joblib exists.
"""

from __future__ import annotations

import logging
import threading
import time
import zipfile
from typing import Any

import numpy as np

from .config import resolve

log = logging.getLogger("audio")

SR = 16000
WIN = 15600  # YAMNet frame: 0.975 s


class YamNet:
    """Thin wrapper over the YAMNet TFLite model (waveform -> scores, embedding)."""

    def __init__(self, path):
        try:
            from ai_edge_litert.interpreter import Interpreter
        except ImportError:  # older environments
            from tflite_runtime.interpreter import Interpreter  # type: ignore
        self.it = Interpreter(model_path=str(path))
        self.it.allocate_tensors()
        self.inp = self.it.get_input_details()[0]
        self.outs = self.it.get_output_details()
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.endswith(".txt"))
            self.labels = [l.strip() for l in z.read(name).decode().splitlines() if l.strip()]

    def run(self, wav: np.ndarray) -> tuple[np.ndarray, np.ndarray | None]:
        wav = np.asarray(wav, dtype=np.float32)
        if len(wav) < WIN:
            wav = np.pad(wav, (0, WIN - len(wav)))
        wav = wav[:WIN]
        self.it.resize_tensor_input(self.inp["index"], [len(wav)], strict=False)
        self.it.allocate_tensors()
        self.it.set_tensor(self.inp["index"], wav)
        self.it.invoke()
        scores, emb = None, None
        for o in self.outs:
            t = self.it.get_tensor(o["index"])
            if t.shape[-1] == len(self.labels):
                scores = t.reshape(-1, len(self.labels)).mean(0)
            elif t.shape[-1] == 1024:
                emb = t.reshape(-1, 1024).mean(0)
        return scores, emb


class GunshotScorer:
    def __init__(self, cfg: dict[str, Any]):
        a = cfg["audio"]
        self.yam = YamNet(resolve(a.get("model", "models/yamnet.tflite")))
        wanted = set(a.get("gunshot_labels", ["Gunshot, gunfire"]))
        self.idx = [i for i, l in enumerate(self.yam.labels) if l in wanted]
        if not self.idx:
            raise RuntimeError("none of audio.gunshot_labels exist in the YAMNet label list")
        self.head = None
        hp = resolve(a.get("custom_head"))
        if hp and hp.exists():
            import joblib
            self.head = joblib.load(hp)
            log.info("using custom gunshot head %s", hp)

    def score(self, wav: np.ndarray) -> tuple[float, str]:
        scores, _ = self.yam.run(wav)
        if self.head is not None:
            return float(self.head.predict_proba(scores[None])[0][1]), "custom"
        i = max(self.idx, key=lambda k: scores[k])
        return float(scores[i]), self.yam.labels[i]


class AudioWorker(threading.Thread):
    HOP = 0.5  # seconds between scored windows

    def __init__(self, cfg: dict[str, Any], engine):
        super().__init__(daemon=True, name="audio")
        self.cfg = cfg["audio"]
        self.engine = engine
        self.cfg_all = cfg
        self._stop = threading.Event()
        self.status = {"running": False, "level": 0.0, "score": 0.0, "error": None}

    def stop(self):
        self._stop.set()

    def run(self):
        try:
            import sounddevice as sd
            scorer = GunshotScorer(self.cfg_all)
        except Exception as e:  # noqa: BLE001
            self.status["error"] = f"audio init failed: {e}"
            log.exception("audio init failed")
            return
        threshold = self.cfg.get("threshold", 0.35)
        ring = np.zeros(SR * 2, dtype=np.float32)
        lock = threading.Lock()

        def cb(indata, frames, t, status):  # runs on the audio thread
            nonlocal ring
            x = indata[:, 0].astype(np.float32)
            with lock:
                ring = np.concatenate([ring, x])[-SR * 2:]

        try:
            with sd.InputStream(samplerate=SR, channels=1, dtype="float32",
                                device=self.cfg.get("device"), callback=cb, blocksize=1600):
                self.status.update(running=True, error=None)
                while not self._stop.is_set():
                    time.sleep(self.HOP)
                    with lock:
                        win = ring[-WIN:].copy()
                    self.status["level"] = float(np.sqrt(np.mean(win ** 2)))
                    score, label = scorer.score(win)
                    self.status["score"] = round(score, 3)
                    if score >= threshold:
                        try:
                            self.engine.on_gunshot(score, label)
                        except Exception:  # noqa: BLE001
                            log.exception("engine.on_gunshot failed")
        except Exception as e:  # noqa: BLE001
            self.status.update(running=False, error=f"microphone error: {e}")
            log.exception("microphone error")
