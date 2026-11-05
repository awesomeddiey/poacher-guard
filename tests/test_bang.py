import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.audio import SR, BangDetector  # noqa: E402

rng = np.random.default_rng(0)


def run(x):
    d, found = BangDetector(min_db=-15, rise_db=20, jump_db=12), []
    for i in range(0, len(x), 1600): found += d.feed(x[i:i + 1600])
    return found


def room(seconds):
    return rng.normal(0, 10 ** (-50 / 20), int(seconds * SR)).astype(np.float32)


def test_sudden_loud_bang_fires():
    t = np.arange(int(0.3 * SR)) / SR
    shot = (rng.normal(0, 1, len(t)) * np.exp(-t / 0.04) * 0.6).astype(np.float32)   # instant attack, fast decay
    assert len(run(np.concatenate([room(1), shot, room(1)]))) == 1


def test_loud_sound_that_builds_up_does_not_fire():
    t = np.arange(int(0.6 * SR)) / SR
    env = np.minimum(1, t / 0.08)                                                    # 80 ms ramp, like a voice
    voice = (np.sin(2 * np.pi * 220 * t) * env * 0.6).astype(np.float32)
    assert run(np.concatenate([room(1), voice, room(1)])) == []


def test_quiet_click_does_not_fire():
    t = np.arange(int(0.2 * SR)) / SR
    click = (rng.normal(0, 1, len(t)) * np.exp(-t / 0.02) * 0.02).astype(np.float32)  # sudden but quiet (-34 dB)
    assert run(np.concatenate([room(1), click, room(1)])) == []
