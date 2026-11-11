"""One-click "Set up node": writes the ready-made sensor node program onto an ESP32 plugged in by USB.

The program (firmware/build/flame_gsm_node.ino.merged.bin) is compiled by GitHub Actions from
firmware/flame_gsm_node every time the sketch changes, and reaches every PC with the auto-update, so nobody needs the
Arduino tools. It holds no personal settings: the phone numbers are sent to the node over its link afterwards.
Writing uses esptool (pip package) at 460800 baud and takes about 30 seconds.
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("flasher")
ROOT = Path(__file__).resolve().parent.parent
FIRMWARE = ROOT / "firmware" / "build" / "flame_gsm_node.ino.merged.bin"
ESP_VIDS = {0x10C4, 0x1A86, 0x303A, 0x0403, 0x067B}   # CP210x, CH340/CH9102, Espressif USB, FTDI, Prolific


def find_esp32_port() -> str | None:
    from serial.tools import list_ports
    ports = [p for p in list_ports.comports() if p.vid in ESP_VIDS]
    return ports[0].device if len(ports) >= 1 else None


class Flasher:
    def __init__(self, firmware: Path = FIRMWARE):
        self.firmware = Path(firmware)
        self._lock = threading.Lock()
        self.status: dict[str, Any] = {"state": "idle", "progress": 0, "message": "", "port": None, "ts": None,
                                       "firmware": self.firmware.exists()}

    def start(self, before=None, after=None) -> dict[str, Any]:
        """Start writing in the background. `before`/`after` let the caller release and re-take the node link."""
        with self._lock:
            if self.status["state"] in ("finding", "writing"):
                return self.status
            self.status.update(state="finding", progress=0, message="Looking for the ESP32 on USB...", port=None, ts=time.time())
        threading.Thread(target=self._run, args=(before, after), daemon=True, name="flasher").start()
        return self.status

    def _fail(self, msg: str) -> None:
        self.status.update(state="error", message=msg, ts=time.time())
        log.warning("flash failed: %s", msg)

    def _run(self, before, after) -> None:
        if not self.firmware.exists():
            return self._fail("The node program is not on this PC yet. Restart Poacher Guard with internet so it can update, then try again.")
        try:
            port = find_esp32_port()
        except Exception as e:  # noqa: BLE001
            return self._fail(f"Could not list the USB ports: {e}")
        if not port:
            return self._fail("No ESP32 found. Plug it in with a USB DATA cable (charge-only cables do not work). If it still "
                              "is not found, install the USB driver for the chip next to its USB socket: CP2102 (Silicon Labs "
                              "CP210x) or CH340 (WCH CH341SER), then try again.")
        self.status.update(state="writing", port=port, message=f"Writing the node program to the ESP32 on {port}...")
        if before:
            before()
        cmd = [sys.executable, "-m", "esptool", "--chip", "esp32", "--port", port, "--baud", "460800",
               "write_flash", "-z", "0x0", str(self.firmware)]
        lines: list[str] = []
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in p.stdout:
                line = line.strip()
                if not line:
                    continue
                lines.append(line)
                m = re.search(r"\((\d+)\s*%\)", line)
                if m:
                    self.status["progress"] = int(m.group(1))
                elif "Connecting" in line:
                    self.status["message"] = f"Connecting to the ESP32 on {port}... (if this takes long, hold its BOOT button)"
            code = p.wait()
        except Exception as e:  # noqa: BLE001
            code, lines = -1, lines + [str(e)]
        finally:
            if after:
                after()
        if code == 0:
            self.status.update(state="done", progress=100, ts=time.time(),
                               message="Done. The node restarts and connects over Bluetooth by itself; unplug the USB cable and power it normally.")
        else:
            tail = " | ".join(lines[-3:])[:300]
            hint = ("Close the Arduino IDE / Serial Monitor and anything else using the port, hold the ESP32's BOOT button, "
                    "and try again.")
            self._fail(f"Writing failed. {hint} ({tail})")
