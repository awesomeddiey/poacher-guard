"""FastAPI app: dashboard, live video, WebSocket alert feed, ESP32 sensor endpoint."""

from __future__ import annotations

import asyncio
import os
import random
import shutil
import logging
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import cv2
from fastapi import Body, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .ble_registry import RangerRegistry
from .config import ROOT, load_config, resolve
from .engine import AlertEngine
from .flasher import Flasher
from .settings import Settings
from .notify import telegram_sender
from .store import EventStore

log = logging.getLogger("server")


class FlamePayload(BaseModel):
    node: str
    fire: bool
    raw: int | None = None
    key: str | None = None


class HeartbeatPayload(BaseModel):
    node: str
    battery: float | None = None      # percent
    rssi: int | None = None           # uplink signal, dBm
    temp: float | None = None         # deg C
    humidity: float | None = None     # %
    people: int | None = None
    seeing: list[str] | None = None   # e.g. ["person 0.91", "elephant 0.88"]
    lat: float | None = None
    lon: float | None = None
    key: str | None = None


def create_app(cfg: dict[str, Any] | None = None, start_workers: bool = True) -> FastAPI:
    cfg = cfg or load_config()
    snap_dir = resolve(cfg["storage"]["snapshot_dir"])
    snap_dir.mkdir(parents=True, exist_ok=True)
    store = EventStore(resolve(cfg["storage"]["db_path"]))
    registry = RangerRegistry(cfg["ble"]["tags"], cfg["ble"].get("presence_window_s", 15),
                              cfg["ble"].get("min_rssi", -90),
                              absent_after_missed=cfg["ble"].get("absent_after_missed", 5),
                              min_absent_s=cfg["ble"].get("min_absent_s", 3))

    clients: set[WebSocket] = set()
    loop_holder: dict[str, asyncio.AbstractEventLoop] = {}
    notifier = telegram_sender(cfg, snap_dir)

    def publish(msg: dict[str, Any]) -> None:
        """Called from worker threads; hops onto the event loop to fan out."""
        loop = loop_holder.get("loop")
        if loop and clients:
            asyncio.run_coroutine_threadsafe(_broadcast(msg), loop)
        if notifier and msg.get("kind") == "event":
            threading.Thread(target=notifier, args=(msg["event"],), daemon=True).start()
        if msg.get("kind") == "event":
            usb, ev = workers.get("node_link"), msg["event"]
            if usb and ev.get("severity") == "critical" and ev.get("type") in ("poacher", "gunshot"):
                try:
                    usb.send_sms(ev["type"], sms_text(ev, usb.node_id))
                except Exception:  # noqa: BLE001
                    log.exception("could not hand the alert to the USB node")

    async def _broadcast(msg: dict[str, Any]) -> None:
        for ws in list(clients):
            try:
                await ws.send_json(msg)
            except Exception:  # noqa: BLE001
                clients.discard(ws)

    def save_snapshot(frame, tag: str) -> str | None:
        try:
            name = f"{int(time.time() * 1000)}_{tag}.jpg"
            cv2.imwrite(str(snap_dir / name), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return name
        except Exception:  # noqa: BLE001
            log.exception("snapshot failed")
            return None

    engine = AlertEngine(cfg, store, registry, publish=publish, save_snapshot=save_snapshot)
    workers: dict[str, Any] = {}
    # dashboard settings (SMS numbers, gunshot tuning) live next to the event database, outside git
    settings = Settings(resolve(cfg["storage"]["db_path"]).parent / "settings.json", cfg)
    flasher = Flasher()

    def _push_phones(data: dict[str, Any]) -> None:
        link = workers.get("node_link")
        if link:
            link.push_phones(data["phones"])
    settings.on_change(_push_phones)
    started = time.time()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        loop_holder["loop"] = asyncio.get_running_loop()
        if start_workers:
            if cfg["vision"].get("enabled", True):
                from .vision import VisionWorker
                workers["vision"] = VisionWorker(cfg, engine)
            if cfg["audio"].get("enabled", True):
                from .audio import AudioWorker
                workers["audio"] = AudioWorker(cfg, engine, settings)
            if cfg["ble"].get("enabled", True):
                from .ble_scanner import BleWorker
                workers["ble"] = BleWorker(registry, publish)
            nl = cfg.get("node_link", {})
            node_id = nl.get("node_id") or (cfg["flame"]["nodes"] or [{"id": "SIM8008"}])[0]["id"]
            if nl.get("mode", "ble") == "ble":
                from .ble_node import BleNodeWorker
                workers["node_link"] = BleNodeWorker(nl.get("ble", {}), engine, node_id, phones=lambda: settings.phones)
            elif nl.get("mode") == "usb":
                from .serial_node import SerialNodeWorker
                workers["node_link"] = SerialNodeWorker(nl.get("usb", {}), engine, node_id, phones=lambda: settings.phones)
            for w in workers.values():
                w.start()
        yield
        for w in workers.values():
            w.stop()

    app = FastAPI(title="Poacher Guard", lifespan=lifespan)
    app.state.engine, app.state.store, app.state.registry = engine, store, registry

    def system_status() -> dict[str, Any]:
        def w(name):
            x = workers.get(name)
            if not x:
                return {"running": False, "error": "disabled" if start_workers else "not started"}
            return dict(x.status)
        try:
            load1 = round(os.getloadavg()[0], 2)
        except (AttributeError, OSError):
            load1 = None
        disk = shutil.disk_usage(ROOT)
        system = {"uptime_s": int(time.time() - started), "load1": load1,
                  "disk_free_gb": round(disk.free / 1e9, 1), "cpus": os.cpu_count()}
        return {"system": system, "activity_24h": store.activity_24h(time.time()),
                "site": cfg["site"], "vision": w("vision"), "audio": w("audio"), "ble": w("ble"), "node_link": w("node_link"),
                "rangers": registry.status(), "verdict": engine.verdict, "nodes": engine.node_status(),
                "simulation": bool(cfg["server"].get("allow_simulation", False)),
                "sms_phones": len(settings.phones), "flash": dict(flasher.status),
                "counts_24h": store.counts_since(time.time() - 86400)}

    @app.get("/api/status")
    def status():
        return system_status()

    @app.get("/api/events")
    def events(limit: int = 100):
        return store.recent(min(limit, 500))

    def sms_text(e: dict[str, Any], node: str = "") -> str:
        """The text message for an alert: 'THREAT: <alert> | NODE: <node> | HH:MM | map link', at most 160 ASCII chars."""
        title = e["title"].encode("ascii", "replace").decode().replace("?", "-")
        name = "".join(ch for ch in (node or cfg["site"]["name"]) if ch.isascii() and ch.isprintable())[:20]
        tail = (f" | NODE: {name} | {time.strftime('%H:%M', time.localtime(e['ts']))}"
                f" | maps.google.com/?q={e['lat']:.5f},{e['lon']:.5f}")
        return "THREAT: " + title[:160 - len("THREAT: ") - len(tail)] + tail

    # ---- settings from the dashboard (only on this PC: other devices on the network can look, not change) ----
    def _local(request: Request) -> bool:
        host = request.client.host if request.client else ""
        return host in ("127.0.0.1", "::1", "localhost") or bool(cfg["server"].get("settings_from_any_device", False))

    def _require_local(request: Request) -> None:
        if not _local(request):
            raise HTTPException(403, "Settings can only be changed on the PC running Poacher Guard (open http://localhost:8000 there).")

    @app.get("/api/settings")
    def get_settings(request: Request):
        return {**settings.public(), "can_edit": _local(request)}

    @app.post("/api/settings")
    def set_settings(request: Request, patch: dict = Body(...)):
        _require_local(request)
        try:
            out = settings.update(patch)
        except (ValueError, TypeError) as e:
            raise HTTPException(400, str(e))
        link = workers.get("node_link")
        return {**out, "can_edit": True, "node_updated": bool(link and link.status.get("running"))}

    @app.post("/api/node/test-sms")
    def node_test_sms(request: Request):
        _require_local(request)
        if not settings.phones:
            raise HTTPException(400, "Set a phone number first.")
        link = workers.get("node_link")
        if not (link and link.status.get("running")):
            raise HTTPException(409, "The sensor node is not connected. Power it on and keep it within Bluetooth range of this PC.")
        link.push_phones(settings.phones)
        link.test_sms()
        return {"ok": True, "message": f"Asked the node to text {', '.join(settings.public()['phones'])}. It takes up to 30 seconds."}

    @app.post("/api/node/flash")
    def node_flash(request: Request):
        _require_local(request)
        link = workers.get("node_link")
        usb = link is not None and getattr(link, "status", {}).get("mode") == "usb"
        # a USB link holds the serial port: release it while writing (the Bluetooth link needs nothing)
        return flasher.start(before=(lambda: link.stop()) if usb else None)

    @app.get("/api/sms", response_class=PlainTextResponse)
    def sms_feed(after: int = -1, types: str = "poacher,gunshot", node: str = ""):
        """Alerts for the ESP32 GSM node, as plain text it can parse without a JSON library.
        Line 1: the newest event id (the node sends it back as `after` next time).
        Then one line per new critical alert:  <id> TAB <type> TAB <SMS text, at most 160 plain ASCII chars>.
        after=-1 (node just booted) returns only the id, so old alerts are not texted again.
        Text: "THREAT: <alert> | NODE: <node> | <HH:MM> | maps.google.com/?q=<lat,lon>"; `node` is the GSM node's name."""
        rows = store.recent(50)
        top = max((e["id"] for e in rows), default=0)
        if after < 0:
            return f"{top}\n"
        want = {t.strip() for t in types.split(",") if t.strip()}
        out = [str(top)]
        for e in sorted(rows, key=lambda e: e["id"]):
            if e["id"] <= after or e["type"] not in want or e["severity"] != "critical" or time.time() - e["ts"] > 600:
                continue
            out.append(f"{e['id']}\t{e['type']}\t{sms_text(e, node)}")
        return "\n".join(out) + "\n"

    @app.post("/api/events/{event_id}/ack")
    def ack(event_id: int):
        if not store.acknowledge(event_id):
            raise HTTPException(404, "no such event")
        return {"ok": True}

    @app.post("/api/sensors/flame")
    def flame(p: FlamePayload):
        want = cfg["flame"].get("api_key")
        if want and p.key != want:
            raise HTTPException(401, "bad key")
        ev = engine.on_flame(p.node, p.fire, p.raw)
        return {"ok": True, "alert": bool(ev)}

    @app.post("/api/nodes/heartbeat")
    def heartbeat(p: HeartbeatPayload):
        want = cfg["flame"].get("api_key")
        if want and p.key != want:
            raise HTTPException(401, "bad key")
        engine.on_heartbeat(p.node, {"battery": p.battery, "rssi": p.rssi, "temp": p.temp,
                                     "humidity": p.humidity, "people": p.people, "seeing": p.seeing},
                            p.lat, p.lon)
        return {"ok": True}

    @app.post("/api/simulate/{kind}")
    def simulate(kind: str):
        if not cfg["server"].get("allow_simulation", False):
            raise HTTPException(403, "simulation disabled")
        fake = [{"label": "person", "conf": 0.9, "xyxy": [0, 0, 1, 1]}]
        if kind == "poacher":
            ev = engine.on_person(None, fake, decide_now=True)
        elif kind == "ranger":
            first = cfg["ble"]["tags"][0]
            registry.observe(first.get("name"), first.get("address"), -55)
            ev = engine.on_person(None, fake)
        elif kind == "gunshot":
            ev = engine.on_gunshot(0.9, "Gunshot, gunfire")
        elif kind == "nodes":
            for n in engine.node_status():
                if n["kind"] == "camera":
                    engine.on_heartbeat(n["id"], {"battery": random.randint(55, 98), "rssi": random.randint(-95, -62),
                                                  "temp": round(random.uniform(18, 34), 1), "humidity": random.randint(25, 70),
                                                  "people": 0, "seeing": ["clear - no humans"]})
                else:
                    engine.on_flame(n["id"], False, random.randint(2500, 3900))
            ev = None
        elif kind == "fire":
            node = (cfg["flame"]["nodes"] or [{"id": "SIM8008"}])[0]["id"]
            ev = engine.on_flame(node, True, 100)
        else:
            raise HTTPException(404, "unknown kind")
        return {"ok": True, "alert": bool(ev), "note": None if ev or kind == "nodes" else "suppressed by cooldown"}

    @app.get("/video")
    def video():
        v = workers.get("vision")
        if not v:
            raise HTTPException(503, "vision disabled")

        def gen():
            last = None
            while True:
                jpg = v.latest_jpeg()
                if jpg is not None and jpg is not last:
                    last = jpg
                    yield b"--f\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
                time.sleep(0.05)
        return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=f")

    @app.websocket("/ws")
    async def ws(sock: WebSocket):
        await sock.accept()
        clients.add(sock)
        try:
            await sock.send_json({"kind": "hello", "status": system_status(), "events": store.recent(50)})
            while True:
                await asyncio.sleep(2)
                await sock.send_json({"kind": "status", "status": system_status()})
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            clients.discard(sock)

    app.mount("/snapshots", StaticFiles(directory=str(snap_dir)), name="snapshots")
    # browser flasher (ESP Web Tools): http://localhost:8000/web-flasher/ writes the node program over Web Serial
    if (ROOT / "web-flasher").exists():
        (ROOT / "firmware" / "build").mkdir(parents=True, exist_ok=True)
        app.mount("/firmware/build", StaticFiles(directory=str(ROOT / "firmware" / "build")), name="firmware")
        app.mount("/web-flasher", StaticFiles(directory=str(ROOT / "web-flasher"), html=True), name="web-flasher")

    @app.get("/")
    def index():
        return FileResponse(ROOT / "dashboard" / "index.html")

    app.mount("/", StaticFiles(directory=str(ROOT / "dashboard")), name="dashboard")
    return app
