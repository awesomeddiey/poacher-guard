import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.config import load_config
from app.server import create_app


def client(tmp_path):
    cfg = load_config()
    cfg["storage"]["db_path"] = str(tmp_path / "e.db")
    cfg["storage"]["snapshot_dir"] = str(tmp_path / "snaps")
    return TestClient(create_app(cfg, start_workers=False))


def test_flame_endpoint_creates_fire_event(tmp_path):
    with client(tmp_path) as c:
        assert c.post("/api/sensors/flame", json={"node": "FLAME-01", "fire": False, "raw": 900}).json()["alert"] is False
        assert c.post("/api/sensors/flame", json={"node": "FLAME-01", "fire": True, "raw": 80}).json()["alert"] is True
        evs = c.get("/api/events").json()
        assert evs[0]["type"] == "fire"
        st = c.get("/api/status").json()
        assert st["nodes"][0]["fire"] is True


def test_simulate_and_ack_and_ws(tmp_path):
    with client(tmp_path) as c:
        assert c.post("/api/simulate/poacher").json()["alert"]
        assert c.post("/api/simulate/gunshot").json()["alert"]
        evs = c.get("/api/events").json()
        assert {e["type"] for e in evs} == {"poacher", "gunshot"}
        assert c.post(f"/api/events/{evs[0]['id']}/ack").json()["ok"]
        with c.websocket_connect("/ws") as ws:
            hello = ws.receive_json()
            assert hello["kind"] == "hello" and len(hello["events"]) == 2
            c.post("/api/simulate/fire")
            assert ws.receive_json()["kind"] in ("nodes", "event")


def test_ranger_simulation(tmp_path):
    with client(tmp_path) as c:
        c.post("/api/simulate/ranger")
        assert c.get("/api/events").json()[0]["type"] == "ranger"
        assert any(r["present"] for r in c.get("/api/status").json()["rangers"])


def test_dashboard_served(tmp_path):
    with client(tmp_path) as c:
        assert c.get("/api/status").status_code == 200
