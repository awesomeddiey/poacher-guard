"""USB link to the ESP32 sensor node (flame sensor + GSM): no Wi-Fi, firewall or IP address needed.

Plain text lines over the USB-serial cable, 115200 baud, every protocol line starts with "@" (the node's other debug
prints are ignored):

  node -> PC   @HELLO,<node>,gsm=<0|1>      sent at start and when the GSM state changes
               @FLAME,<0|1>                 flame state, on change and as a heartbeat every few seconds
               @SMS,<ok|fail|skipped>,<kind>  result of a text the PC asked for
  PC -> node   @SMS,<poacher|gunshot>,<text>  "send this text" (the node adds its own repeat limit)

The worker finds the ESP32's COM port by itself (USB-serial chips CP210x, CH340, FTDI, ESP32-S3), re-connects if the
cable is pulled out, reports the flame state to the alert engine exactly like POST /api/sensors/flame, and writes the
alert texts the dashboard builds for poacher and gunshot alerts to the node.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from .node_protocol import NodeProtocolMixin, ascii_line, new_status

log = logging.getLogger("node-usb")

# USB vendor ids of the usual ESP32 board chips: Silicon Labs CP210x, WCH CH340/CH9102, Espressif, FTDI, Prolific
ESP_VIDS = {0x10C4, 0x1A86, 0x303A, 0x0403, 0x067B}


class SerialNodeWorker(NodeProtocolMixin, threading.Thread):
    def __init__(self, cfg: dict[str, Any], engine, node_id: str):
        super().__init__(daemon=True, name="node-usb")
        self.cfg, self.engine, self.node_id = cfg, engine, node_id
        self._stop_evt = threading.Event()
        self._ser = None
        self._wlock = threading.Lock()
        self.status = new_status(mode="usb")

    def stop(self):
        self._stop_evt.set()

    # ---- finding and opening the port ------------------------------------------------------------
    def _candidates(self) -> list[str]:
        want = str(self.cfg.get("port", "auto"))
        if want.lower() != "auto":
            return [want]
        from serial.tools import list_ports
        ports = list(list_ports.comports())
        esp = [p.device for p in ports if p.vid in ESP_VIDS]
        other = [p.device for p in ports if p.vid not in ESP_VIDS and p.device not in ("COM1",)]
        return esp + other

    def _open(self, device: str):
        import serial
        s = serial.Serial()
        s.port, s.baudrate, s.timeout = device, int(self.cfg.get("baud", 115200)), 1.0
        s.dtr = s.rts = False          # do not pulse the ESP32's reset/boot pins when the port opens
        s.open()
        return s

    def _probe(self, device: str):
        """Open the port and wait for a protocol line from the node; returns the open port or None."""
        try:
            s = self._open(device)
        except Exception as e:  # noqa: BLE001
            log.info("cannot open %s: %s", device, e)
            return None
        t0 = time.time()
        while time.time() - t0 < float(self.cfg.get("probe_s", 8)) and not self._stop_evt.is_set():
            line = s.readline().decode("utf-8", "ignore").strip()
            if line.startswith("@"):
                self.on_line(line)
                return s
        s.close()
        return None

    def send_sms(self, kind: str, text: str) -> bool:
        """Ask the node to text `text`. Returns False when the cable is not connected."""
        s = self._ser
        if not s or not self.status["running"]:
            return False
        try:
            with self._wlock:
                s.write(ascii_line(kind, text))
            self.status["texts_asked"] += 1
            return True
        except Exception:  # noqa: BLE001
            log.exception("could not write to the node")
            return False

    # ---- main loop ----------------------------------------------------------------------------
    def run(self):
        try:
            import serial  # noqa: F401
        except ImportError:
            self.status.update(running=False, error="pyserial is not installed (run: pip install pyserial)")
            return
        silent_after = float(self.cfg.get("silent_after_s", 30))
        while not self._stop_evt.is_set():
            ser = None
            try:
                for dev in self._candidates():
                    ser = self._probe(dev)
                    if ser:
                        self.status["port"] = dev
                        break
            except Exception as e:  # noqa: BLE001
                log.exception("port search failed")
                self.status["error"] = f"port search failed: {e}"
            if not ser:
                self.status.update(running=False, port=None,
                                   error="no ESP32 found: plug it in with a USB data cable, close the Arduino Serial Monitor, "
                                         "and check it is programmed with the flame_gsm_node sketch")
                self._stop_evt.wait(5)
                continue
            self._ser = ser
            self.status.update(running=True, error=None)
            log.info("ESP32 node on %s", self.status["port"])
            try:
                while not self._stop_evt.is_set():
                    line = ser.readline().decode("utf-8", "ignore").strip()
                    if line.startswith("@"):
                        self.on_line(line)
                    elif time.time() - (self.status["last_seen"] or 0) > silent_after:
                        self.status["error"] = f"node silent for {int(silent_after)} s (programmed with the USB sketch?)"
            except Exception as e:  # noqa: BLE001
                log.warning("lost the ESP32 on %s: %s", self.status["port"], e)
            finally:
                self._ser = None
                try:
                    ser.close()
                except Exception:  # noqa: BLE001
                    pass
                self.status.update(running=False, error="ESP32 unplugged: waiting for it to come back")
            self._stop_evt.wait(2)
