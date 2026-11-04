"""Decides what a raw detection means and whether to raise an alert.

Inputs (called from the vision / audio / sensor threads):
  on_person(...)   camera confirmed a human in frame
  on_gunshot(...)  microphone model heard a gunshot
  on_flame(...)    ESP32 flame sensor heartbeat / trigger

The rule the whole project exists for lives in on_person():
  human seen + an authorised ranger BLE tag is nearby  -> RANGER (info, no alarm)
  human seen + no tag                                  -> POACHER (critical)
A gunshot soon after a poacher sighting (or vice versa) escalates to ARMED.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

from .ble_registry import RangerRegistry
from .store import EventStore

SEVERITY = {"info": 0, "warning": 1, "critical": 2}


class AlertEngine:
    def __init__(self, cfg: dict[str, Any], store: EventStore, registry: RangerRegistry,
                 publish: Callable[[dict[str, Any]], None] = lambda e: None,
                 save_snapshot: Callable[[Any, str], str | None] = lambda frame, tag: None,
                 clock: Callable[[], float] = time.time):
        self.cfg = cfg
        self.store = store
        self.registry = registry
        self.publish = publish
        self.save_snapshot = save_snapshot
        self.clock = clock
        self.site = cfg["site"]
        self.cooldown = {"poacher": 30, "suspect": 30, "ranger": 120, "gunshot": 10, "fire": 60,
                         **cfg["alerts"].get("cooldown_s", {})}
        self.correlate_window = cfg["alerts"].get("correlate_window_s", 120)
        # A tag advertises about once a second, so a ranger who has just walked into view may not have been
        # heard yet. Hold the poacher verdict this long (from the first confirmed frame of a sighting) and
        # call it "ranger" the moment the tag is heard. A visible weapon skips the wait.
        self.decision_wait = cfg.get("ble", {}).get("decision_wait_s", 2.0)
        self._sighting_start = -1e9
        self._last_person_call = -1e9
        # Live verdict for whoever is in view right now (clear / checking / ranger / poacher / armed). It is pushed
        # to the dashboard the moment it changes, independent of alert cooldowns.
        self.verdict: dict[str, Any] = {"state": "clear", "ts": clock()}
        self._last_person_type: str | None = None
        self._last: dict[str, float] = {}
        self._last_poacher_ts = -1e9
        self._last_gunshot_ts = -1e9
        self._lock = threading.Lock()
        self.flame_nodes = {n["id"]: {**n, "kind": "flame", "last_seen": None, "fire": False, "raw": None}
                            for n in cfg["flame"].get("nodes", [])}
        self.field_nodes = {n["id"]: {**n, "kind": "camera", "last_seen": None, "fire": False,
                                      "telemetry": {}} for n in cfg.get("nodes", [])}
        self.offline_after = cfg["flame"].get("offline_after_s", 30)

    # ---- helpers -------------------------------------------------------
    def _cooling(self, key: str, kind: str) -> bool:
        now = self.clock()
        if now - self._last.get(key, -1e9) < self.cooldown.get(kind, 30):
            return True
        self._last[key] = now
        return False

    def _set_verdict(self, state: str, **info) -> None:
        new = {"state": state, **info}
        old = {k: v for k, v in self.verdict.items() if k != "ts"}
        if new != old:
            self.verdict = {**new, "ts": self.clock()}
            self.publish({"kind": "verdict", "verdict": self.verdict})

    def _person_cooling(self, kind: str) -> bool:
        """Repeats of the same verdict obey the cooldown; a change (poacher <-> ranger) is reported at once."""
        if kind != self._last_person_type:
            self._last_person_type = kind
            self._last[kind] = self.clock()
            return False
        return self._cooling(kind, kind)

    def on_clear(self) -> None:
        """The camera no longer sees anyone."""
        self._last_person_call = -1e9
        self._set_verdict("clear")

    def _emit(self, type_: str, severity: str, title: str, frame=None,
              lat=None, lon=None, detail: dict | None = None) -> dict[str, Any]:
        ev = {
            "ts": self.clock(), "type": type_, "severity": severity, "title": title,
            "lat": self.site["lat"] if lat is None else lat,
            "lon": self.site["lon"] if lon is None else lon,
            "snapshot": self.save_snapshot(frame, type_) if frame is not None else None,
            "detail": detail or {},
        }
        ev = self.store.add(ev)
        self.publish({"kind": "event", "event": ev})
        return ev

    # ---- camera --------------------------------------------------------
    def on_person(self, frame, boxes: list[dict[str, Any]], weapon: bool = False,
                  latency_s: float | None = None, decide_now: bool = False) -> dict[str, Any] | None:
        """A human was confirmed in view. `boxes` = [{label, conf, xyxy}, ...]."""
        now = self.clock()
        if now - self._last_person_call > 3.0:   # gap in sightings: a new person has come into view
            self._sighting_start = now
        self._last_person_call = now
        rangers = self.registry.ranger_present()
        n = len(boxes)
        if rangers and not weapon:
            r = rangers[0]
            self._set_verdict("ranger", people=n, ranger=r["ranger"], tag=r["id"], rssi=r["rssi"])
            if self._person_cooling("ranger"):
                return None
            return self._emit("ranger", "info", f"Authorised ranger on camera: {r['ranger']}", frame,
                              detail={"people": n, "tag": r["id"], "rssi": r["rssi"], "latency_s": latency_s})
        # No tag in range (or a weapon is visible, which a tag cannot excuse).
        if not (weapon or decide_now) and now - self._sighting_start < self.decision_wait:
            self._set_verdict("checking", people=n)
            return None   # still listening for a tag
        armed = weapon or (self.clock() - self._last_gunshot_ts) <= self.correlate_window
        self._set_verdict("armed" if armed else "poacher", people=n)
        kind = "poacher"
        if self._person_cooling(kind):
            return None
        self._last_poacher_ts = self.clock()
        if armed:
            title = "ARMED INTRUDER - unauthorised person with weapon/gunshot"
        else:
            title = f"POACHER ALERT - {n} unauthorised person{'s' if n != 1 else ''}, no ranger tag"
        detail = {"people": n, "weapon_seen": weapon, "ranger_tags_nearby": len(rangers),
                  "boxes": boxes[:10], "latency_s": latency_s}
        if rangers and weapon:
            detail["note"] = "Ranger tag nearby but weapon detected - verify"
        return self._emit("poacher", "critical", title, frame, detail=detail)

    # ---- microphone ----------------------------------------------------
    def on_gunshot(self, score: float, label: str, frame=None) -> dict[str, Any] | None:
        if self._cooling("gunshot", "gunshot"):
            return None
        self._last_gunshot_ts = self.clock()
        armed = (self.clock() - self._last_poacher_ts) <= self.correlate_window
        title = "GUNSHOT + poacher sighting - ARMED POACHER" if armed else f"Gunshot detected ({score:.0%})"
        return self._emit("gunshot", "critical", title, frame,
                          detail={"score": round(float(score), 3), "label": label,
                                  "with_poacher": armed})

    # ---- flame sensor --------------------------------------------------
    def on_flame(self, node_id: str, fire: bool, raw: int | None = None) -> dict[str, Any] | None:
        node = self.flame_nodes.setdefault(node_id, {"id": node_id, "label": node_id, "kind": "flame",
                                                     "lat": self.site["lat"], "lon": self.site["lon"],
                                                     "last_seen": None, "fire": False, "raw": None})
        node.update(last_seen=self.clock(), fire=bool(fire), raw=raw)
        self.publish({"kind": "nodes", "nodes": self.node_status()})
        if not fire or self._cooling(f"fire:{node_id}", "fire"):
            return None
        return self._emit("fire", "critical", f"FIRE detected at {node.get('label', node_id)}",
                          lat=node.get("lat"), lon=node.get("lon"),
                          detail={"node": node_id, "raw": raw})

    # ---- remote field nodes ---------------------------------------------
    def on_heartbeat(self, node_id: str, telemetry: dict[str, Any],
                     lat: float | None = None, lon: float | None = None) -> None:
        node = self.field_nodes.setdefault(node_id, {"id": node_id, "label": node_id, "kind": "camera",
                                                     "lat": self.site["lat"], "lon": self.site["lon"],
                                                     "last_seen": None, "fire": False, "telemetry": {}})
        if lat is not None and lon is not None:
            node["lat"], node["lon"] = lat, lon
        node["last_seen"] = self.clock()
        node["telemetry"] = {k: v for k, v in telemetry.items() if v is not None}
        self.publish({"kind": "nodes", "nodes": self.node_status()})

    def node_status(self) -> list[dict[str, Any]]:
        now = self.clock()
        out = []
        for n in list(self.flame_nodes.values()) + list(self.field_nodes.values()):
            online = bool(n["last_seen"] and now - n["last_seen"] <= self.offline_after)
            out.append({"id": n["id"], "label": n.get("label", n["id"]), "kind": n.get("kind", "flame"),
                        "lat": n.get("lat"), "lon": n.get("lon"), "online": online,
                        "fire": bool(n["fire"] and online),
                        "raw": n.get("raw"), "telemetry": n.get("telemetry", {}) if online else {},
                        "age_s": round(now - n["last_seen"], 1) if n["last_seen"] else None})
        return out
