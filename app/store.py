"""SQLite event log. One row per alert; snapshots live on disk beside it."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


class EventStore:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(db_path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    title TEXT NOT NULL,
                    lat REAL, lon REAL,
                    snapshot TEXT,
                    detail TEXT,
                    acknowledged INTEGER NOT NULL DEFAULT 0
                )"""
            )
            self._db.commit()

    def add(self, ev: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO events (ts,type,severity,title,lat,lon,snapshot,detail) VALUES (?,?,?,?,?,?,?,?)",
                (ev["ts"], ev["type"], ev["severity"], ev["title"], ev.get("lat"), ev.get("lon"),
                 ev.get("snapshot"), json.dumps(ev.get("detail", {}))),
            )
            self._db.commit()
            return {**ev, "id": cur.lastrowid, "acknowledged": False}

    @staticmethod
    def _row(r: sqlite3.Row) -> dict[str, Any]:
        d = dict(r)
        d["detail"] = json.loads(d["detail"] or "{}")
        d["acknowledged"] = bool(d["acknowledged"])
        return d

    def recent(self, limit: int = 100, types: list[str] | None = None) -> list[dict[str, Any]]:
        q, args = "SELECT * FROM events", []
        if types:
            q += " WHERE type IN (%s)" % ",".join("?" * len(types))
            args += types
        q += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            return [self._row(r) for r in self._db.execute(q, args).fetchall()]

    def acknowledge(self, event_id: int) -> bool:
        with self._lock:
            cur = self._db.execute("UPDATE events SET acknowledged=1 WHERE id=?", (event_id,))
            self._db.commit()
            return cur.rowcount > 0

    def counts_since(self, since_ts: float) -> dict[str, int]:
        with self._lock:
            rows = self._db.execute(
                "SELECT type, COUNT(*) c FROM events WHERE ts>=? GROUP BY type", (since_ts,)
            ).fetchall()
        return {r["type"]: r["c"] for r in rows}
