"""The text protocol spoken between the PC and the ESP32 sensor node, the same over USB cable and Bluetooth.

Every protocol line starts with "@" and ends with a newline (other lines the node prints are ignored):

  node -> PC   @HELLO,<node>,gsm=<0|1>        at start, when the GSM state changes, and every 20 s
               @FLAME,<0|1>                   flame state: on change, on connect, and as a heartbeat every few seconds
               @SMS,<ok|fail|skipped>,<kind>  result of a text the PC asked for
  PC -> node   @SMS,<poacher|gunshot>,<text>  "send this text to the rangers" (the node adds its own repeat limit)
"""

from __future__ import annotations

import logging
import time
from typing import Any

log = logging.getLogger("node-link")


def new_status(**extra: Any) -> dict[str, Any]:
    return {"running": False, "error": "starting", "mode": None, "port": None, "gsm": None, "fire": False,
            "last_seen": None, "texts_asked": 0, "texts_sent": 0, **extra}


class NodeProtocolMixin:
    """Needs self.engine, self.node_id and self.status (see new_status)."""

    def on_line(self, line: str) -> None:
        parts = line.strip()[1:].split(",")
        cmd = parts[0].upper()
        self.status["last_seen"] = time.time()
        self.status["error"] = None
        if cmd == "FLAME" and len(parts) >= 2:
            fire = parts[1].strip() == "1"
            self.status["fire"] = fire
            self.engine.on_flame(self.node_id, fire, 0 if fire else 4095)
        elif cmd == "HELLO":
            self.status["gsm"] = "gsm=1" in line
            log.info("node says hello: %s", line.strip())
        elif cmd == "SMS" and len(parts) >= 3:
            ok = parts[1].strip().lower() == "ok"
            self.status["texts_sent"] += int(ok)
            log.info("node SMS %s (%s)", parts[1], parts[2])


def ascii_line(kind: str, text: str) -> bytes:
    """The PC -> node text command as one ASCII line."""
    text = "".join(c if 32 <= ord(c) < 127 else " " for c in text)
    return f"@SMS,{kind},{text[:160]}\n".encode("ascii")
