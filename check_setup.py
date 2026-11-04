"""Pre-flight check for Poacher Guard. Run it before the demo:   python check_setup.py [--ble] [--mic [name]]

  * Python packages and model files
  * cameras (index, size) and a saved test picture per camera in data/camera_N.jpg
  * microphones
  * Bluetooth: with --ble it scans for 8 s and lists nearby devices with their address, name and signal, so you can copy the
    address of your ranger beacon into config.yaml (ble.tags[].address)
  * Microphone: with --mic it lists every input device, then listens for 15 s on the one the app would use (or the one
    named after --mic) and prints the sound level, the gunshot score and what the model thinks it hears. Play a
    gunshot recording near the microphone while it runs.
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

def mic_test():
    import time
    import numpy as np
    import sounddevice as sd
    sys.path.insert(0, str(ROOT))
    from app.audio import SR, WIN, GunshotScorer, pick_microphone
    from app.config import load_config
    cfg = load_config()
    apis = sd.query_hostapis()
    print("\nInput devices (index, driver, name):")
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            print(f"   {i:>3}  {apis[d['hostapi']]['name'][:12]:<12} {d['name']}{'   <- Windows default' if i == sd.default.device[0] else ''}")
    k = sys.argv.index("--mic")
    want = sys.argv[k + 1] if len(sys.argv) > k + 1 else cfg["audio"].get("device")
    want = int(want) if isinstance(want, str) and want.isdigit() else want
    dev, name = pick_microphone(want)
    print(f"\nListening on: [{dev}] {name}")
    a = dict(cfg["audio"]); a["use_custom_head"] = False
    zero = GunshotScorer({**cfg, "audio": a})
    a2 = dict(cfg["audio"]); a2["use_custom_head"] = True
    try: head = GunshotScorer({**cfg, "audio": a2}); head = head if head.head else None
    except Exception: head = None
    rate = SR
    try: sd.check_input_settings(device=dev, samplerate=SR, channels=1)
    except Exception: rate = int(sd.query_devices(dev, "input")["default_samplerate"])
    print(f"Recording at {rate} Hz. PLAY A GUNSHOT SOUND NEAR THE MICROPHONE NOW (15 s)...\n")
    print("  time  level              gunshot  trained   what the model hears")
    buf = sd.rec(int(15 * rate), samplerate=rate, channels=1, dtype="float32", device=dev); best = (0, 0, None)
    t0 = time.time()
    for step in range(1, 30):
        while time.time() - t0 < step * 0.5 + 0.05: time.sleep(0.02)
        end = int(step * 0.5 * rate); seg = buf[max(0, end - int(rate * WIN / SR)):end, 0]
        if rate != SR:
            from scipy.signal import resample_poly
            from math import gcd
            g = gcd(SR, rate); seg = resample_poly(seg, SR // g, rate // g).astype(np.float32)
        lvl = float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0
        z, _ = zero.score(seg); h = head.score(seg)[0] if head else None
        top = ", ".join(f"{l} {p:.2f}" for l, p in zero.explain(seg))
        flag = "  <== GUNSHOT" if z >= cfg["audio"].get("threshold", 0.35) else ""
        print(f"  {step * 0.5:4.1f}s {'#' * min(16, int(lvl * 160)):<16}  {z:6.2f}  {'' if h is None else f'{h:6.2f}':>7}   {top}{flag}")
        if z > best[0]: best = (z, step * 0.5, top)
    sd.wait()
    thr = cfg["audio"].get("threshold", 0.35)
    if best[0] >= thr: say(OK, f"gunshot heard (score {best[0]:.2f} at {best[1]} s, threshold {thr})")
    else:
        say(WARN, f"no gunshot above the threshold {thr} (best {best[0]:.2f}).")
        print("       If the level bars stayed empty, this is the wrong microphone: run  python check_setup.py --mic <index>  with")
        print("       another index from the list, then put that name in config.yaml -> audio.device.")
        print("       If the level moved but the score stayed low, play the sound louder and closer, from a speaker rather than a phone.")


if "--mic" in sys.argv:
    try: mic_test()
    except Exception as e: say(BAD, f"microphone test failed: {e}")

if "--ble" in sys.argv:
    print("\nScanning for Bluetooth devices for 8 seconds (hold your beacon close to the PC)...")
    try:
        seen = asyncio.run(scan())
        for addr, (name, rssi) in sorted(seen.items(), key=lambda kv: -kv[1][1])[:15]: print(f"   {addr}   {rssi:>4} dBm   {name or '(no name)'}")
        print("\nCopy the address of your beacon (strongest while held close) into config.yaml -> ble.tags[].address")
        if platform.system() == "Darwin": say(WARN, "macOS hides real Bluetooth addresses (you see long IDs, not MACs). Match by name instead, or ask for iBeacon matching")
    except Exception as e: say(BAD, f"bluetooth scan failed: {e}. Turn Bluetooth on in Windows settings")
else:
    print("\n(Run  python check_setup.py --ble  to scan for your ranger beacon's address,")
    print(" or  python check_setup.py --mic  to test gunshot detection on the microphone)")
print("\n" + ("All checks passed." if not problems else f"{problems} problem(s) found. Fix the [FAIL] lines above, then run again."))
