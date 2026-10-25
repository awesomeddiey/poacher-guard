"""Optional Telegram push so rangers get the alert photo and map pin on their phones."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger("notify")


def telegram_sender(cfg: dict[str, Any], snapshot_dir: Path):
    t = cfg.get("notify", {}).get("telegram", {})
    if not (t.get("enabled") and t.get("bot_token") and t.get("chat_id")):
        return None
    base = f"https://api.telegram.org/bot{t['bot_token']}"

    def send(ev: dict[str, Any]) -> None:
        if ev["severity"] != "critical":
            return
        text = f"🚨 {ev['title']}\n{cfg['site']['name']}\nhttps://maps.google.com/?q={ev['lat']},{ev['lon']}"
        try:
            snap = ev.get("snapshot")
            if snap and (snapshot_dir / snap).exists():
                with open(snapshot_dir / snap, "rb") as f:
                    httpx.post(f"{base}/sendPhoto", data={"chat_id": t["chat_id"], "caption": text},
                               files={"photo": f}, timeout=15)
            else:
                httpx.post(f"{base}/sendMessage", data={"chat_id": t["chat_id"], "text": text}, timeout=15)
        except Exception:  # noqa: BLE001
            log.exception("telegram send failed")

    return send
