"""Pre-flight check for Poacher Guard. Run it before the demo:   python check_setup.py [--ble]

  * Python packages and model files
  * cameras (index, size) and a saved test picture per camera in data/camera_N.jpg
  * microphones
  * Bluetooth: with --ble it scans for 8 s and lists nearby devices with their address, name and signal, so you can copy the
    address of your ranger beacon into config.yaml (ble.tags[].address)
"""
import os
os.environ.setdefault("OPENCV_LOG_LEVEL", "SILENT")   # hide OpenCV probe warnings
import asyncio
import importlib
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OK, BAD, WARN = "[ OK ]", "[FAIL]", "[WARN]"
problems = 0


def say(tag, msg):
    global problems
    problems += tag == BAD
    print(f"{tag} {msg}")


print(f"Poacher Guard setup check  ({platform.system()}, Python {sys.version.split()[0]})\n")
for mod, why in (("cv2", "camera"), ("numpy", "maths"), ("ultralytics", "person detector"), ("ai_edge_litert", "gunshot detector"), ("sounddevice", "microphone"),
                 ("bleak", "bluetooth"), ("fastapi", "dashboard server"), ("yaml", "config")):
    try: importlib.import_module(mod); say(OK, f"{mod} ({why})")
    except Exception as e: say(BAD, f"{mod} ({why}) is not usable: {str(e)[:80]}")
for f in ("models/yolo11n.pt", "models/yamnet.tflite", "config.yaml"):
    say(OK if (ROOT / f).exists() else BAD, f"file {f}")

try:
    import cv2
    backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY
    (ROOT / "data").mkdir(exist_ok=True); found = []
    for i in range(5):
        c = cv2.VideoCapture(i, backend); ok, fr = c.read() if c.isOpened() else (False, None); c.release()
        if ok:
            found.append(i); cv2.imwrite(str(ROOT / "data" / f"camera_{i}.jpg"), fr); say(OK, f"camera {i}: {fr.shape[1]}x{fr.shape[0]} (picture saved to data/camera_{i}.jpg)")
    if not found: say(BAD, "no camera found. Plug in the webcam and close other apps that use it (Zoom, Teams, Camera)")
    elif len(found) > 1: print(f"       {len(found)} cameras: with source: auto the system uses camera {found[-1]}. To force one, set source in config.yaml or run: set PG_CAMERA=0")
except Exception as e: say(BAD, f"camera check failed: {e}")

try:
    import sounddevice as sd
    mics = [d for d in sd.query_devices() if d["max_input_channels"] > 0]
    say(OK if mics else BAD, f"microphones: {', '.join(m['name'][:30] for m in mics[:3]) or 'none found'}")
except Exception as e: say(WARN, f"microphone check skipped: {str(e)[:80]}")


async def scan():
    from bleak import BleakScanner
    seen = {}
    def cb(d, adv): seen[d.address] = (adv.local_name or d.name or "", adv.rssi)
    async with BleakScanner(cb): await asyncio.sleep(8)
    return seen

if "--ble" in sys.argv:
    print("\nScanning for Bluetooth devices for 8 seconds (hold your beacon close to the PC)...")
    try:
        seen = asyncio.run(scan())
        for addr, (name, rssi) in sorted(seen.items(), key=lambda kv: -kv[1][1])[:15]: print(f"   {addr}   {rssi:>4} dBm   {name or '(no name)'}")
        print("\nCopy the address of your beacon (strongest while held close) into config.yaml -> ble.tags[].address")
        if platform.system() == "Darwin": say(WARN, "macOS hides real Bluetooth addresses (you see long IDs, not MACs). Match by name instead, or ask for iBeacon matching")
    except Exception as e: say(BAD, f"bluetooth scan failed: {e}. Turn Bluetooth on in Windows settings")
else:
    print("\n(Run  python check_setup.py --ble  to scan for your ranger beacon's address)")
print("\n" + ("All checks passed." if not problems else f"{problems} problem(s) found. Fix the [FAIL] lines above, then run again."))
