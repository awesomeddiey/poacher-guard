"""Tracks which authorised ranger tags have been heard recently.

The BLE scanner (ble_scanner.py) feeds `observe()`; the alert engine asks
`ranger_present()` whenever the camera sees a person. Kept free of any
Bluetooth imports so it is trivially testable.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable


class RangerRegistry:
    def __init__(self, tags: list[dict[str, Any]], presence_window_s: float = 15,
                 min_rssi: int = -90, clock: Callable[[], float] = time.time):
        self.tags = tags
        self.window = presence_window_s
        self.min_rssi = min_rssi
        self._clock = clock
        self._lock = threading.Lock()
        self._seen: dict[str, dict[str, Any]] = {}  # tag id -> last sighting

    def match(self, name: str | None, address: str | None) -> dict[str, Any] | None:
        addr = (address or "").upper()
        for t in self.tags:
            if t.get("address") and addr and t["address"].upper() == addr:
                return t
            if t.get("name") and name and t["name"] == name:
                return t
        return None

    def observe(self, name: str | None, address: str | None, rssi: int) -> bool:
        """Record an advertisement. Returns True if it belonged to a known tag."""
        tag = self.match(name, address)
        if not tag or rssi < self.min_rssi:
            return False
        with self._lock:
            self._seen[tag["id"]] = {"tag": tag, "rssi": rssi, "ts": self._clock()}
        return True

    def ranger_present(self) -> list[dict[str, Any]]:
        """Authorised tags heard within the presence window (strongest first)."""
        now = self._clock()
        with self._lock:
            live = [s for s in self._seen.values() if now - s["ts"] <= self.window]
        live.sort(key=lambda s: s["rssi"], reverse=True)
        return [{"id": s["tag"]["id"], "ranger": s["tag"].get("ranger", s["tag"]["id"]),
                 "rssi": s["rssi"], "age_s": round(now - s["ts"], 1)} for s in live]

    def status(self) -> list[dict[str, Any]]:
        """Every configured tag with its last-heard info, for the dashboard."""
        now = self._clock()
        out = []
        with self._lock:
            for t in self.tags:
                s = self._seen.get(t["id"])
                out.append({
                    "id": t["id"], "ranger": t.get("ranger", t["id"]),
                    "present": bool(s and now - s["ts"] <= self.window),
                    "rssi": s["rssi"] if s else None,
                    "age_s": round(now - s["ts"], 1) if s else None,
                })
        return out
