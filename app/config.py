"""Loads config.yaml and resolves relative paths against the project root."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent


def resolve(path: str | None) -> Path | None:
    if not path:
        return None
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def load_config(path: str | os.PathLike | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else ROOT / "config.yaml"
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    # Fill sections a trimmed-down config may leave out.
    for section in ("site", "server", "storage", "vision", "audio", "ble", "flame", "alerts", "notify"):
        cfg.setdefault(section, {})
    cfg["site"].setdefault("lat", 0.0)
    cfg["site"].setdefault("lon", 0.0)
    cfg["site"].setdefault("name", "Unnamed site")
    cfg["storage"].setdefault("db_path", "data/events.db")
    cfg["storage"].setdefault("snapshot_dir", "data/snapshots")
    cfg["alerts"].setdefault("cooldown_s", {})
    cfg["alerts"].setdefault("correlate_window_s", 120)
    cfg["ble"].setdefault("tags", [])
    cfg["flame"].setdefault("nodes", [])
    return cfg
