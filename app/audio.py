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

import json
import logging
import math
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
        self.head = None          # sklearn head (joblib) or the Chapter 3 logistic head exported as JSON
        hp = resolve(a.get("custom_head")) if a.get("use_custom_head") else None
        if hp and hp.exists():
            if hp.suffix == ".json":
                h = json.loads(hp.read_text())
                self.head = ("json", np.asarray(h["coef"], np.float32), float(h["intercept"]))
            else:
                import joblib
                self.head = ("sk", joblib.load(hp))
            log.info("using trained gunshot head %s", hp)

    def head_score(self, scores: np.ndarray) -> float:
        if self.head[0] == "json":
            return 1 / (1 + math.exp(-(float(scores @ self.head[1]) + self.head[2])))
        return float(self.head[1].predict_proba(scores[None])[0][1])

    def score(self, wav: np.ndarray) -> tuple[float, str]:
        scores, _ = self.yam.run(wav)
        if self.head is not None:
            return self.head_score(scores), "trained head"
        i = max(self.idx, key=lambda k: scores[k])
        return float(scores[i]), self.yam.labels[i]

    def explain(self, wav: np.ndarray, k: int = 3) -> list[tuple[str, float]]:
        """Top YAMNet classes for a window, for the microphone test."""
        scores, _ = self.yam.run(wav)
        top = np.argsort(scores)[::-1][:k]
        return [(self.yam.labels[i], float(scores[i])) for i in top]


SKIP_MICS = ("hands-free", "headset", "bluetooth", "sound mapper", "primary sound capture", "stereo mix", "what u hear")
PREFER_MICS = ("c-media", "usb", "webcam", "camera")


def pick_microphone(want=None):
    """Choose the input device. `want` = None/"auto": the USB microphone on the node (often the webcam's C-Media mic),
    skipping Bluetooth headsets and Windows' virtual mappers; otherwise a device index or part of its name.
    On Windows the MME copy of a device is preferred because it accepts 16 kHz directly. Returns (index or None, name)."""
    import sounddevice as sd
    devs, apis = sd.query_devices(), sd.query_hostapis()
    mics = [(i, d) for i, d in enumerate(devs) if d["max_input_channels"] > 0]
    rank_api = lambda d: 0 if apis[d["hostapi"]]["name"] == "MME" else 1
    if isinstance(want, int):
        return want, devs[want]["name"]
    if isinstance(want, str) and want.lower() != "auto":
        hits = [(i, d) for i, d in mics if want.lower() in d["name"].lower()]
        if hits:
            i, d = min(hits, key=lambda x: rank_api(x[1])); return i, d["name"]
        log.warning("microphone %r not found, using the automatic choice", want)
    usable = [(i, d) for i, d in mics if not any(s in d["name"].lower() for s in SKIP_MICS)]
    pref = [(i, d) for i, d in usable if any(p in d["name"].lower() for p in PREFER_MICS)]
    for group in (pref, usable):
        if group:
            i, d = min(group, key=lambda x: rank_api(x[1])); return i, d["name"]
    return None, "system default"


class AudioWorker(threading.Thread):
    HOP = 0.5  # seconds between scored windows

    def __init__(self, cfg: dict[str, Any], engine):
        super().__init__(daemon=True, name="audio")
        self.cfg = cfg["audio"]
        self.engine = engine
        self.cfg_all = cfg
        self._stop = threading.Event()
        self.status = {"running": False, "level": 0.0, "score": 0.0, "error": None, "device": None, "peak": 0.0}

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
        threshold = self.cfg.get("head_threshold", 0.99) if scorer.head else self.cfg.get("threshold", 0.35)
        dev, dev_name = pick_microphone(self.cfg.get("device"))
        ring = np.zeros(SR * 2, dtype=np.float32)
        lock = threading.Lock()

        rate = SR

        def cb(indata, frames, t, status):  # runs on the audio thread
            nonlocal ring
            x = indata[:, 0].astype(np.float32)
            if rate != SR:   # device would not open at 16 kHz: resample its native rate
                from scipy.signal import resample_poly
                g = math.gcd(SR, int(rate)); x = resample_poly(x, SR // g, int(rate) // g).astype(np.float32)
            with lock:
                ring = np.concatenate([ring, x])[-SR * 2:]

        def open_stream():
            nonlocal rate
            try:
                return sd.InputStream(samplerate=SR, channels=1, dtype="float32", device=dev, callback=cb, blocksize=1600)
            except Exception:  # noqa: BLE001
                rate = int(sd.query_devices(dev, "input")["default_samplerate"])
                log.info("microphone does not take 16 kHz, recording at %d Hz and resampling", rate)
                return sd.InputStream(samplerate=rate, channels=1, dtype="float32", device=dev, callback=cb,
                                      blocksize=int(rate // 10))

        try:
            with open_stream():
                log.info("microphone: %s", dev_name)
                self.status.update(running=True, error=None, device=dev_name)
                while not self._stop.is_set():
                    time.sleep(self.HOP)
                    with lock:
                        win = ring[-WIN:].copy()
                    self.status["level"] = float(np.sqrt(np.mean(win ** 2)))
                    score, label = scorer.score(win)
                    self.status["score"] = round(score, 3)
                    self.status["peak"] = round(max(score, self.status["peak"] * 0.9), 3)   # decays, so a short spike stays visible
                    if score >= threshold:
                        try:
                            self.engine.on_gunshot(score, label)
                        except Exception:  # noqa: BLE001
                            log.exception("engine.on_gunshot failed")
        except Exception as e:  # noqa: BLE001
            self.status.update(running=False, error=f"microphone error: {e}")
            log.exception("microphone error")
