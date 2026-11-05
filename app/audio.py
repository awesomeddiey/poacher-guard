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

    VOICE = ("Speech", "Male speech, man speaking", "Female speech, woman speaking", "Child speech, kid speaking",
             "Conversation", "Narration, monologue", "Babbling", "Shout", "Yell", "Children shouting", "Screaming",
             "Laughter", "Singing", "Whispering", "Cough", "Sneeze", "Throat clearing")

    def score(self, wav: np.ndarray) -> tuple[float, str]:
        g, label, _ = self.score_all(wav)
        return g, label

    def score_all(self, wav: np.ndarray) -> tuple[float, str, float]:
        """Gunshot score and label, plus how strongly the window sounds like a human voice (used to veto loud bangs)."""
        scores, _ = self.yam.run(wav)
        if not hasattr(self, "_voice_idx"):
            self._voice_idx = [i for i, l in enumerate(self.yam.labels) if l in self.VOICE]
        voice = float(max(scores[i] for i in self._voice_idx)) if self._voice_idx else 0.0
        if self.head is not None:
            return self.head_score(scores), "trained head", voice
        i = max(self.idx, key=lambda k: scores[k])
        return float(scores[i]), self.yam.labels[i], voice

    def explain(self, wav: np.ndarray, k: int = 3) -> list[tuple[str, float]]:
        """Top YAMNet classes for a window, for the microphone test."""
        scores, _ = self.yam.run(wav)
        top = np.argsort(scores)[::-1][:k]
        return [(self.yam.labels[i], float(scores[i])) for i in top]


class BangDetector:
    """Loudness-based gunshot detector: fires on a sudden, loud bang.

    Works on 10 ms frames of the 16 kHz stream. A bang is a frame that is (1) loud in absolute terms (min_db, dBFS),
    (2) much louder than the room a moment before (rise_db over the median of the previous 50-300 ms) and (3) reached
    almost instantly (jump_db over the louder of the two frames just before it). Condition 3 is what separates a
    gunshot from speech, which also gets loud but ramps up over several frames. Claps, door slams and dropped objects
    can still trigger it, so alerts from this detector are labelled "loud bang"."""

    FRAME = SR // 100

    def __init__(self, min_db: float = -15, rise_db: float = 20, jump_db: float = 12, refractory_s: float = 0.5):
        self.min_db, self.rise_db, self.jump_db = min_db, rise_db, jump_db
        self.refractory = int(refractory_s * 100)
        self.hist: list[float] = []
        self.rest = np.zeros(0, np.float32)
        self.quiet = 0
        self.last = {"db": -120.0, "rise": 0.0, "jump": 0.0}   # loudest frame of the latest block, for the mic test

    def feed(self, x: np.ndarray) -> list[dict[str, float]]:
        """Feed 16 kHz samples; returns the bangs found in them."""
        x = np.concatenate([self.rest, np.asarray(x, np.float32)])
        n = len(x) // self.FRAME; self.rest = x[n * self.FRAME:]
        bangs, loudest = [], {"db": -120.0, "rise": 0.0, "jump": 0.0}
        for f in x[:n * self.FRAME].reshape(n, self.FRAME):
            db = 20 * math.log10(float(np.sqrt(np.mean(f * f))) + 1e-9)
            h = self.hist
            if len(h) >= 30:
                base = float(np.median(h[-30:-5])); jump = db - max(h[-1], h[-2]); rise = db - base
                if db > loudest["db"]: loudest = {"db": db, "rise": rise, "jump": jump}
                if self.quiet <= 0 and db >= self.min_db and rise >= self.rise_db and jump >= self.jump_db:
                    bangs.append({"db": db, "rise": rise, "jump": jump}); self.quiet = self.refractory
            self.quiet -= 1
            h.append(db); del h[:-40]
        self.last = loudest
        return bangs


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
        mode = self.cfg.get("detector", "either")          # model | loudness | either
        b = self.cfg.get("bang", {})
        bang = BangDetector(b.get("min_db", -15), b.get("rise_db", 20), b.get("jump_db", 12)) if mode in ("loudness", "either") else None
        bangs: list[dict[str, float]] = []
        voice_veto = b.get("voice_veto", 0.3)
        recent_voice: list[float] = []      # voice score of the last few windows (about 1 s of context)
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
                if bang is not None:
                    bangs.extend(bang.feed(x))

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
                        found, bangs[:] = list(bangs), []
                    self.status["level"] = float(np.sqrt(np.mean(win ** 2)))
                    score, label, voice_now = scorer.score_all(win)
                    recent_voice = (recent_voice + [voice_now])[-max(1, int(round(1.0 / self.HOP)) + 1):]
                    voice = max(recent_voice)       # a voice in the bang's window or the second before it
                    if found:
                        top = max(found, key=lambda d: d["rise"])
                        self.status["last_bang"] = {**{k: round(v, 1) for k, v in top.items()}, "voice": round(voice, 2)}
                        if voice >= voice_veto:     # loud, but the model hears a voice: talking or shouting, not a shot
                            self.status["bangs_ignored"] = self.status.get("bangs_ignored", 0) + 1
                            log.info("loud bang ignored: sounds like a voice (%.2f)", voice)
                        else:
                            try:
                                self.engine.on_gunshot(min(1.0, top["rise"] / 40), f"Loud bang (+{top['rise']:.0f} dB)")
                            except Exception:  # noqa: BLE001
                                log.exception("engine.on_gunshot failed")
                    self.status["score"] = round(score, 3)
                    self.status["peak"] = round(max(score, self.status["peak"] * 0.9), 3)   # decays, so a short spike stays visible
                    if mode != "loudness" and score >= threshold:
                        try:
                            self.engine.on_gunshot(score, label)
                        except Exception:  # noqa: BLE001
                            log.exception("engine.on_gunshot failed")
        except Exception as e:  # noqa: BLE001
            self.status.update(running=False, error=f"microphone error: {e}")
            log.exception("microphone error")
