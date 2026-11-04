import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.audio import pick_microphone  # noqa: E402

# Device list shaped like the Windows laptop in the field test (MME + WASAPI copies, a Bluetooth headset).
DEVS = [
    {"name": "Microsoft Sound Mapper - Input", "max_input_channels": 2, "hostapi": 0},
    {"name": "Headset (SKY Fit Vibe)", "max_input_channels": 1, "hostapi": 0},
    {"name": "Microphone (C-Media(R) Audio)", "max_input_channels": 1, "hostapi": 0},
    {"name": "Speakers (Realtek)", "max_input_channels": 0, "hostapi": 0},
    {"name": "Microphone (C-Media(R) Audio)", "max_input_channels": 1, "hostapi": 1},
    {"name": "Headset (SKY Fit Vibe)", "max_input_channels": 1, "hostapi": 1},
]


def fake_sd(monkeypatch, devs=DEVS):
    sd = types.SimpleNamespace(query_devices=lambda: devs, query_hostapis=lambda: [{"name": "MME"}, {"name": "Windows WASAPI"}])
    monkeypatch.setitem(sys.modules, "sounddevice", sd)


def test_auto_picks_usb_mic_not_bluetooth_headset(monkeypatch):
    fake_sd(monkeypatch)
    assert pick_microphone("auto") == (2, "Microphone (C-Media(R) Audio)")   # MME copy, accepts 16 kHz
    assert pick_microphone(None)[0] == 2


def test_name_and_index(monkeypatch):
    fake_sd(monkeypatch)
    assert pick_microphone("sky fit")[0] == 1
    assert pick_microphone(5) == (5, "Headset (SKY Fit Vibe)")
    assert pick_microphone("nonexistent")[0] == 2                          # falls back to automatic choice


def test_falls_back_to_default_when_only_virtual_devices(monkeypatch):
    fake_sd(monkeypatch, DEVS[:2])
    assert pick_microphone("auto") == (None, "system default")
