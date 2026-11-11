"""The text protocol spoken between the PC and the ESP32 sensor node, the same over USB cable and Bluetooth.

Every protocol line starts with "@" and ends with a newline (other lines the node prints are ignored):

  node -> PC   @HELLO,<node>,gsm=<0|1>,phones=<n>  at start, when the GSM state changes, and every 20 s
               @CFG,phones=<n>                after it saved the phone numbers the PC sent
               @FLAME,<0|1>                   flame state: on change, on connect, and as a heartbeat every few seconds
               @SMS,<ok|fail|skipped>,<kind>  result of a text the PC asked for
  PC -> node   @SMS,<poacher|gunshot>,<text>  "send this text to the rangers" (the node adds its own repeat limit)
               @PHONES,<+2637...;+2637...>    the numbers to text (set on the dashboard); the node stores them
               @TEST                          send a test text to every number now
"""

from __future__ import annotations

import logging
import time
from typing import Any

log = logging.getLogger("node-link")


def new_status(**extra: Any) -> dict[str, Any]:
    return {"running": False, "error": "starting", "mode": None, "port": None, "gsm": None, "fire": False,
            "last_seen": None, "texts_asked": 0, "texts_sent": 0, "phones_on_node": None, "last_sms": None, **extra}


def _field(line: str, key: str) -> str | None:
    for part in line.split(","):
        if part.strip().startswith(key + "="):
            return part.split("=", 1)[1].strip()
    return None


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
            n = _field(line, "phones")
            if n is not None and n.isdigit():
                self.status["phones_on_node"] = int(n)
            log.info("node says hello: %s", line.strip())
        elif cmd == "CFG":
            n = _field(line, "phones")
            if n is not None and n.isdigit():
                self.status["phones_on_node"] = int(n)
        elif cmd == "SMS" and len(parts) >= 3:
            ok = parts[1].strip().lower() == "ok"
            self.status["texts_sent"] += int(ok)
            self.status["last_sms"] = {"result": parts[1].strip().lower(), "kind": parts[2].strip(), "ts": time.time()}
            log.info("node SMS %s (%s)", parts[1], parts[2])

    # ---- PC -> node (each transport implements send_raw) --------------------------------------
    def send_sms(self, kind: str, text: str) -> bool:
        """Ask the node to text `text`. False when the node is not connected right now."""
        ok = self.send_raw(ascii_line(kind, text))
        if ok:
            self.status["texts_asked"] += 1
        return ok

    def push_phones(self, phones: list[str]) -> bool:
        return self.send_raw(phones_line(phones))

    def test_sms(self) -> bool:
        return self.send_raw(b"@TEST\n")


def phones_line(phones: list[str]) -> bytes:
    return ("@PHONES," + ";".join(p for p in phones if p) + "\n").encode("ascii")


def ascii_line(kind: str, text: str) -> bytes:
    """The PC -> node text command as one ASCII line."""
    text = "".join(c if 32 <= ord(c) < 127 else " " for c in text)
    return f"@SMS,{kind},{text[:160]}\n".encode("ascii")
