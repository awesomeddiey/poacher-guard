"""Write the ready-made sensor node program to an ESP32 plugged in by USB (same as the dashboard's "Set up node").
    .venv\\Scripts\\python.exe tools\\flash_node.py
Close Poacher Guard first if it uses the USB link (node_link.mode: usb); with Bluetooth it can stay open."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.flasher import Flasher  # noqa: E402

f = Flasher()
f.start()
last = None
while f.status["state"] in ("finding", "writing"):
    s = (f.status["state"], f.status["progress"], f.status["message"])
    if s != last:
        print(f"{s[1]:3d}%  {s[2]}")
        last = s
    time.sleep(0.3)
print(("OK   " if f.status["state"] == "done" else "FAIL ") + f.status["message"])
print("Then set the SMS number on the dashboard: the node gets it over Bluetooth.")
sys.exit(0 if f.status["state"] == "done" else 1)
