import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient  # noqa: E402

from app.config import load_config  # noqa: E402
from app.server import create_app  # noqa: E402
from app.settings import local_format, normalize_phone  # noqa: E402


@pytest.mark.parametrize("raw", ["0772109787", "077 210 9787", "+263772109787", "263772109787", "0772-109-787"])
def test_phone_formats(raw):
    assert normalize_phone(raw) == "+263772109787" and local_format("+263772109787") == "0772109787"


@pytest.mark.parametrize("raw", ["772109787", "0242123456", "07721097", "hello", "+27821234567"])
def test_bad_phones_rejected(raw):
    with pytest.raises(ValueError):
        normalize_phone(raw)


def app_client(tmp_path, any_device=True):
    cfg = load_config()
    cfg["storage"]["db_path"] = str(tmp_path / "e.db"); cfg["storage"]["snapshot_dir"] = str(tmp_path / "s")
    cfg["server"]["settings_from_any_device"] = any_device
    return TestClient(create_app(cfg, start_workers=False))


def test_settings_saved_validated_and_kept(tmp_path):
    with app_client(tmp_path) as c:
        s = c.get("/api/settings").json()
        assert s["phones"] == [] and s["can_edit"] and s["gunshot"]["detector"] in ("model", "loudness", "either")
        r = c.post("/api/settings", json={"phones": "0772109787, 0712 345 678", "gunshot": {"threshold": 0.5, "min_db": -25}})
        assert r.status_code == 200 and r.json()["phones"] == ["0772109787", "0712345678"]
        assert c.get("/api/status").json()["sms_phones"] == 2
        bad = c.post("/api/settings", json={"phones": "12345"})
        assert bad.status_code == 400 and "0772109787" in bad.json()["detail"]
        assert c.post("/api/settings", json={"gunshot": {"threshold": 3}}).status_code == 400
        assert c.post("/api/settings", json={"gunshot": {"detector": "magic"}}).status_code == 400
    with app_client(tmp_path) as c:                                         # restart: still there
        s = c.get("/api/settings").json()
        assert s["phones"] == ["0772109787", "0712345678"] and s["gunshot"]["threshold"] == 0.5 and s["gunshot"]["min_db"] == -25
        r = c.post("/api/settings", json={"reset_gunshot": True}).json()
        assert r["gunshot"] == r["defaults"]


def test_only_this_pc_can_change(tmp_path):
    with app_client(tmp_path, any_device=False) as c:                       # TestClient is "another device"
        assert c.get("/api/settings").json()["can_edit"] is False
        assert c.post("/api/settings", json={"phones": "0772109787"}).status_code == 403
        assert c.post("/api/node/test-sms").status_code == 403
        assert c.post("/api/node/flash").status_code == 403


def test_test_sms_and_flash_without_hardware(tmp_path):
    with app_client(tmp_path) as c:
        assert c.post("/api/node/test-sms").status_code == 400                  # no number yet
        c.post("/api/settings", json={"phones": "0772109787"})
        r = c.post("/api/node/test-sms")
        assert r.status_code == 409 and "not connected" in r.json()["detail"]
        c.post("/api/node/flash")
        for _ in range(50):
            f = c.get("/api/status").json()["flash"]
            if f["state"] == "error":
                break
            time.sleep(0.1)
        assert f["state"] == "error" and ("No ESP32 found" in f["message"] or "not on this PC" in f["message"])
