"""The USB link, tested against a simulated ESP32 on a virtual serial port (pty). Linux/macOS only."""
import os
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
pty = pytest.importorskip("pty")
pytest.importorskip("serial")
from fastapi.testclient import TestClient  # noqa: E402

from app.config import load_config  # noqa: E402
from app.server import create_app  # noqa: E402


class FakeNode:
    """Plays the ESP32 sketch: says hello, sends flame heartbeats, records the texts the PC asks for."""
    def __init__(self):
        self.master, slave = pty.openpty()
        self.path = os.ttyname(slave)
        self.slave = slave
        self.fire, self.got, self._run = False, [], True
        threading.Thread(target=self._rx, daemon=True).start()
        threading.Thread(target=self._tx, daemon=True).start()

    def _tx(self):
        n = 0
        while self._run:
            if n % 5 == 0:
                os.write(self.master, b"@HELLO,SIM8008,gsm=1\n")
            n += 1
            os.write(self.master, b"debug line that the PC must ignore\n")
            os.write(self.master, f"@FLAME,{1 if self.fire else 0}\n".encode())
            time.sleep(0.3)

    def _rx(self):
        buf = b""
        while self._run:
            try:
                buf += os.read(self.master, 256)
            except OSError:
                return
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                self.got.append(line.decode())

    def close(self):
        self._run = False


def wait(cond, secs=8):
    t0 = time.time()
    while time.time() - t0 < secs:
        if cond():
            return True
        time.sleep(0.1)
    return False


def test_usb_node_reports_flame_and_receives_poacher_texts(tmp_path):
    node = FakeNode()
    cfg = load_config()
    cfg["storage"]["db_path"] = str(tmp_path / "e.db"); cfg["storage"]["snapshot_dir"] = str(tmp_path / "s")
    cfg["vision"]["enabled"] = cfg["audio"]["enabled"] = cfg["ble"]["enabled"] = False
    cfg["node_link"] = {"mode": "usb", "node_id": "SIM8008", "usb": {"port": node.path, "baud": 115200, "probe_s": 3}}
    with TestClient(create_app(cfg, start_workers=True)) as c:
        st = lambda: c.get("/api/status").json()
        assert wait(lambda: st()["node_link"]["running"]), st()["node_link"]
        assert wait(lambda: st()["node_link"]["gsm"] is True)
        n = [x for x in st()["nodes"] if x["id"] == "SIM8008"][0]
        assert n["online"] and not n["fire"]                         # heartbeats reach the dashboard

        node.fire = True                                              # the flame sensor trips
        assert wait(lambda: [x for x in st()["nodes"] if x["id"] == "SIM8008"][0]["fire"])
        assert any(e["type"] == "fire" for e in c.get("/api/events").json())

        c.post("/api/simulate/poacher")                               # the PC's models see a poacher
        assert wait(lambda: any(g.startswith("@SMS,poacher,THREAT: POACHER ALERT") for g in node.got)), node.got
        line = [g for g in node.got if g.startswith("@SMS,poacher,")][0]
        assert "| NODE: SIM8008 |" in line and len(line.split(",", 2)[2]) <= 160
        assert st()["node_link"]["texts_asked"] >= 1
    node.close()


def test_no_esp32_is_reported_not_crashed(tmp_path):
    cfg = load_config()
    cfg["storage"]["db_path"] = str(tmp_path / "e.db"); cfg["storage"]["snapshot_dir"] = str(tmp_path / "s")
    cfg["vision"]["enabled"] = cfg["audio"]["enabled"] = cfg["ble"]["enabled"] = False
    cfg["node_link"] = {"mode": "usb", "usb": {"port": "/dev/does-not-exist", "probe_s": 1}}
    with TestClient(create_app(cfg, start_workers=True)) as c:
        assert wait(lambda: "no ESP32 found" in (c.get("/api/status").json()["node_link"]["error"] or ""))
