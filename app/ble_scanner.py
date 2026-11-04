"""Passive BLE scan on the laptop: feeds ranger-tag advertisements to the registry."""

from __future__ import annotations

import asyncio
import logging
import threading
import time

log = logging.getLogger("ble")


class BleWorker(threading.Thread):
    def __init__(self, registry, publish=lambda msg: None):
        super().__init__(daemon=True, name="ble")
        self.registry = registry
        self.publish = publish
        self._last_push = 0.0
        self._stop_evt = threading.Event()
        self.status = {"running": False, "error": None, "seen_tags": 0}

    def stop(self):
        self._stop_evt.set()

    def run(self):
        try:
            asyncio.run(self._scan())
        except Exception as e:  # noqa: BLE001
            self.status.update(running=False, error=f"BLE scan failed: {e}")
            log.exception("BLE failed")

    async def _scan(self):
        from bleak import BleakScanner

        def on_adv(device, adv):
            name = adv.local_name or device.name
            if self.registry.observe(name, device.address, adv.rssi):
                self.status["seen_tags"] += 1
                tag = self.registry.match(name, device.address)
                now = time.time()
                # A tag that just came into range goes out immediately; otherwise refresh RSSI at most once a second.
                if (tag and self.registry.just_arrived(tag["id"])) or now - self._last_push >= 1.0:
                    self._last_push = now
                    self.publish({"kind": "rangers", "rangers": self.registry.status()})

        # Restart the scanner if the adapter hiccups (common on Windows).
        while not self._stop_evt.is_set():
            try:
                async with BleakScanner(on_adv):
                    self.status.update(running=True, error=None)
                    while not self._stop_evt.is_set():
                        await asyncio.sleep(1)
            except Exception as e:  # noqa: BLE001
                self.status.update(running=False, error=f"BLE adapter error: {e}")
                await asyncio.sleep(5)
