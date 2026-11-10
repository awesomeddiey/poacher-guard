"""Bluetooth link to the ESP32 sensor node: no cable, no Wi-Fi, no pairing.

The node is a Bluetooth Low Energy peripheral that advertises its name (NODE_ID, e.g. "SIM8008") and speaks the
standard Nordic UART service (a text pipe). This PC finds it, connects, and then both sides exchange the lines
described in node_protocol.py. Lines are cut into 20-byte pieces on the air (the smallest Bluetooth packet) and
joined again at the newline, so nothing depends on the negotiated packet size.

The node works on its own: it texts fire alerts without this PC. The link carries the flame state to the dashboard and
the poacher / gunshot alerts (found by the camera and microphone models here) back to the node to text.
If the node goes out of range the PC keeps searching and reconnects by itself.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any

from .node_protocol import NodeProtocolMixin, ascii_line, new_status

log = logging.getLogger("node-ble")

NUS_SERVICE = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_RX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"   # PC writes here  (node receives)
NUS_TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"   # node notifies here (PC receives)
CHUNK = 20


class BleNodeWorker(NodeProtocolMixin, threading.Thread):
    def __init__(self, cfg: dict[str, Any], engine, node_id: str):
        super().__init__(daemon=True, name="node-ble")
        self.cfg, self.engine, self.node_id = cfg, engine, node_id
        self.name = str(cfg.get("name") or node_id)
        self._stop_evt = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue | None = None
        self._connected = False
        self._rx = ""
        self.status = new_status(mode="ble", device=None, rssi=None)

    def stop(self):
        self._stop_evt.set()

    # ---- called from other threads ------------------------------------------------------------
    def send_sms(self, kind: str, text: str) -> bool:
        """Ask the node to text `text`. False when the node is not connected right now."""
        loop, q = self._loop, self._queue
        if not (loop and q and self._connected):
            return False
        loop.call_soon_threadsafe(q.put_nowait, ascii_line(kind, text))
        self.status["texts_asked"] += 1
        return True

    # ---- receiving ---------------------------------------------------------------------------------
    def _on_notify(self, _sender, data: bytearray) -> None:
        self._rx += bytes(data).decode("utf-8", "ignore")
        while "\n" in self._rx:
            line, self._rx = self._rx.split("\n", 1)
            if line.strip().startswith("@"):
                try:
                    self.on_line(line)
                except Exception:  # noqa: BLE001
                    log.exception("bad line from the node: %r", line)

    # ---- connection loop ------------------------------------------------------------------------
    def run(self):
        try:
            asyncio.run(self._main())
        except Exception as e:  # noqa: BLE001
            self.status.update(running=False, error=f"Bluetooth link failed: {e}")
            log.exception("BLE node link failed")

    async def _main(self):
        self._loop, self._queue = asyncio.get_running_loop(), asyncio.Queue()
        from bleak import BleakScanner

        def match(device, adv) -> bool:      # by the node's Bluetooth name, so several nodes can have different names
            return self.name in (adv.local_name, device.name)

        while not self._stop_evt.is_set():
            try:
                dev = await BleakScanner.find_device_by_filter(match, timeout=8.0)
            except Exception as e:  # noqa: BLE001
                self.status.update(running=False, error=f"Bluetooth adapter error: {e}")
                await asyncio.sleep(5)
                continue
            if dev is None:
                self.status.update(running=False, device=None,
                                   error=f"node '{self.name}' not found: is it powered, in range, and not connected to a phone?")
                continue
            self.status["device"] = dev.address
            try:
                await self._session(dev)
            except Exception as e:  # noqa: BLE001
                log.warning("node link dropped: %s", e)
            finally:
                self._connected = False
                self.status.update(running=False, error="node disconnected: searching again")
            await asyncio.sleep(2)

    async def _session(self, dev) -> None:
        from bleak import BleakClient
        gone = asyncio.Event()
        loop = asyncio.get_running_loop()
        silent_after = float(self.cfg.get("silent_after_s", 20))
        async with BleakClient(dev, disconnected_callback=lambda _c: loop.call_soon_threadsafe(gone.set), timeout=15.0) as client:
            self._rx = ""
            await client.start_notify(NUS_TX, self._on_notify)
            self._connected = True
            self.status.update(running=True, error=None, last_seen=time.time())
            log.info("connected to node %s (%s)", self.name, dev.address)
            while not gone.is_set() and not self._stop_evt.is_set():
                try:
                    line = await asyncio.wait_for(self._queue.get(), 1.0)
                except asyncio.TimeoutError:
                    if time.time() - (self.status["last_seen"] or 0) > silent_after:
                        log.warning("node silent for %s s: reconnecting", silent_after)
                        return
                    continue
                for i in range(0, len(line), CHUNK):
                    await client.write_gatt_char(NUS_RX, line[i:i + CHUNK], response=True)
