import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ble_registry import RangerRegistry
from app.config import load_config
from app.engine import AlertEngine
from app.store import EventStore


class Clock:
    t = 1000.0
    def __call__(self): return self.t


def make(tmp_path):
    cfg = load_config()
    clock = Clock()
    reg = RangerRegistry(cfg["ble"]["tags"], presence_window_s=15, min_rssi=-90, clock=clock)
    published = []
    eng = AlertEngine(cfg, EventStore(tmp_path / "e.db"), reg, publish=published.append, clock=clock)
    return eng, reg, clock, published

BOX = [{"label": "person", "conf": 0.9, "xyxy": [0, 0, 10, 10]}]


def test_person_without_tag_is_poacher(tmp_path):
    eng, reg, clock, pub = make(tmp_path)
    ev = eng.on_person(None, BOX)
    assert ev["type"] == "poacher" and ev["severity"] == "critical"


def test_person_with_ranger_tag_is_not_an_alarm(tmp_path):
    eng, reg, clock, pub = make(tmp_path)
    assert reg.observe("RANGER-R001", None, -60)
    ev = eng.on_person(None, BOX)
    assert ev["type"] == "ranger" and ev["severity"] == "info"
    assert "Moyo" in ev["title"]


def test_tag_expires(tmp_path):
    eng, reg, clock, pub = make(tmp_path)
    reg.observe("RANGER-R001", None, -60)
    clock.t += 16
    assert eng.on_person(None, BOX)["type"] == "poacher"


def test_unknown_tag_and_weak_signal_ignored(tmp_path):
    eng, reg, clock, pub = make(tmp_path)
    assert not reg.observe("RANGER-EVIL", "11:22:33:44:55:66", -50)
    assert not reg.observe("RANGER-R001", None, -95)  # below min_rssi
    assert eng.on_person(None, BOX)["type"] == "poacher"


def test_address_match(tmp_path):
    cfg = load_config()
    reg = RangerRegistry([{"id": "X", "address": "aa:bb:cc:dd:ee:ff"}])
    assert reg.observe(None, "AA:BB:CC:DD:EE:FF", -50)


def test_weapon_overrides_ranger_tag(tmp_path):
    eng, reg, clock, pub = make(tmp_path)
    reg.observe("RANGER-R001", None, -60)
    ev = eng.on_person(None, BOX, weapon=True)
    assert ev["type"] == "poacher" and "ARMED" in ev["title"]


def test_cooldown(tmp_path):
    eng, reg, clock, pub = make(tmp_path)
    assert eng.on_person(None, BOX)
    assert eng.on_person(None, BOX) is None
    clock.t += 31
    assert eng.on_person(None, BOX)


def test_gunshot_then_poacher_escalates(tmp_path):
    eng, reg, clock, pub = make(tmp_path)
    eng.on_gunshot(0.8, "Gunshot, gunfire")
    clock.t += 5
    ev = eng.on_person(None, BOX)
    assert "ARMED" in ev["title"]


def test_poacher_then_gunshot_escalates(tmp_path):
    eng, reg, clock, pub = make(tmp_path)
    eng.on_person(None, BOX)
    clock.t += 5
    ev = eng.on_gunshot(0.8, "Gunshot, gunfire")
    assert ev["detail"]["with_poacher"] and "ARMED" in ev["title"]


def test_flame_alert_uses_node_location_and_offline(tmp_path):
    eng, reg, clock, pub = make(tmp_path)
    assert eng.on_flame("FLAME-01", False) is None
    ev = eng.on_flame("FLAME-01", True, 120)
    assert ev["type"] == "fire" and ev["lat"] == -17.8301
    assert eng.node_status()[0]["fire"] is True
    clock.t += 31
    st = eng.node_status()[0]
    assert st["online"] is False and st["fire"] is False
