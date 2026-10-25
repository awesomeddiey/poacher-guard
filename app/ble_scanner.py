"""Passive BLE scan on the laptop: feeds ranger-tag advertisements to the registry."""

from __future__ import annotations

import asyncio
import logging
import threading

log = logging.getLogger("ble")


class BleWorker(threading.Thread):
    def __init__(self, registry):
        super().__init__(daemon=True, name="ble")
        self.registry = registry
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
