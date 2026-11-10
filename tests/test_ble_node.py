"""The Bluetooth link against a fake Bluetooth stack (bleak replaced by a scripted node)."""
import asyncio
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.ble_node import CHUNK, NUS_RX, NUS_TX, BleNodeWorker  # noqa: E402


class FakeEngine:
    def __init__(self): self.flame = []
    def on_flame(self, node, fire, raw): self.flame.append((node, fire, raw))


def install_fake_bleak(monkeypatch, node):
    class Dev:
        address, name = "AA:BB:CC:DD:EE:01", "SIM8008"

    class Adv:
        local_name, service_uuids = "SIM8008", []

    class Scanner:
        @staticmethod
        async def find_device_by_filter(match, timeout=8.0):
            await asyncio.sleep(0.05)
            return Dev() if match(Dev(), Adv()) and node["visible"] else None

    class Client:
        def __init__(self, dev, disconnected_callback=None, timeout=10.0):
            self.cb = disconnected_callback; node["client"] = self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def start_notify(self, uuid, handler):
            assert uuid == NUS_TX
            self.notify = handler
            asyncio.get_running_loop().create_task(node["script"](self))

        async def write_gatt_char(self, uuid, data, response=False):
            assert uuid == NUS_RX and len(data) <= CHUNK
            node["written"].append(bytes(data))

    monkeypatch.setitem(sys.modules, "bleak", types.SimpleNamespace(BleakScanner=Scanner, BleakClient=Client))


def wait_until(cond, secs=5.0):
    import time
    t0 = time.time()
    while time.time() - t0 < secs:
        if cond():
            return True
        time.sleep(0.05)
    return False


def test_ble_link_flame_text_and_reconnect(monkeypatch):
    async def script(client):                                       # the node: notifications are cut into 20-byte pieces
        for msg in (b"@HELLO,SIM8008,gsm=1\n", b"@FLAME,0\n", b"@FLAME,1\n"):
            for i in range(0, len(msg), CHUNK):
                client.notify(None, bytearray(msg[i:i + CHUNK]))
                await asyncio.sleep(0.01)
            await asyncio.sleep(0.1)

    node = {"visible": True, "written": [], "script": script}
    install_fake_bleak(monkeypatch, node)
    eng = FakeEngine()
    w = BleNodeWorker({"silent_after_s": 20}, eng, "SIM8008")
    w.start()
    try:
        assert wait_until(lambda: w.status["running"]), w.status
        assert wait_until(lambda: ("SIM8008", True, 0) in eng.flame), eng.flame
        assert eng.flame[0] == ("SIM8008", False, 4095) and w.status["gsm"] is True    # HELLO arrived in 2 pieces

        text = "THREAT: POACHER ALERT - 1 unauthorised person, no ranger tag | NODE: SIM8008 | 21:12 | maps.google.com/?q=-17.82920,31.05220"
        assert w.send_sms("poacher", text)
        assert wait_until(lambda: b"".join(node["written"]).endswith(b"31.05220\n"))
        sent = b"".join(node["written"]).decode()
        assert sent == f"@SMS,poacher,{text}\n" and all(len(p) <= CHUNK for p in node["written"])

        node["client"].cb(node["client"])                            # the link drops
        assert wait_until(lambda: not w.status["running"] or w.status["error"])
        assert not w.send_sms("poacher", "x") or w.status["running"] is True       # no sending into a dead link
        assert wait_until(lambda: w.status["running"], 8), w.status                 # found again and reconnected
    finally:
        w.stop()


def test_node_not_found_is_reported(monkeypatch):
    node = {"visible": False, "written": [], "script": None}
    install_fake_bleak(monkeypatch, node)
    w = BleNodeWorker({}, FakeEngine(), "SIM8008")
    w.start()
    try:
        assert wait_until(lambda: "not found" in (w.status["error"] or ""))
        assert w.send_sms("poacher", "x") is False
    finally:
        w.stop()
