# Poacher Guard

Laptop-based anti-poaching detection: **webcam person detector + microphone gunshot detector + BLE ranger-tag check + ESP32 flame sensor**, all feeding one **live web dashboard**.

```
 webcam ──► YOLO person model ─┐
 laptop mic ► YAMNet gunshot ──┤                 ┌─► dashboard (browser, any device on the Wi-Fi)
 BLE scan ► ranger tag? ───────┼─► Alert engine ─┼─► SQLite log + snapshots
 ESP32 flame ── Wi-Fi POST ────┘                 └─► optional Telegram push (photo + map pin)
```

## The decision rule

| Camera sees a person | Ranger BLE tag heard (≤15 s, RSSI ≥ -90) | Result |
|---|---|---|
| yes | yes | `ranger` – info only, **no alarm** |
| yes | no | **`poacher` – critical alarm** + snapshot + GPS |
| yes + weapon class | yes or no | **`poacher` – ARMED** (a tag can't excuse a visible weapon) |
| gunshot ≤120 s from a poacher sighting | – | escalates to **ARMED POACHER** |
| flame sensor trips | – | `fire` alarm at that node's coordinates |

## Run it

```bash
cd poacher-guard
python -m venv .venv && source .venv/bin/activate     # Windows: run-poacher-guard.bat does all of this
pip install -r requirements.txt
python run.py                                          # open http://localhost:8000
```

Phones/tablets on the same Wi-Fi can open `http://<laptop-ip>:8000`. Click **Enable alarm sound** once in the browser (browsers block audio until you do).

No hardware yet? Use the **Test alerts** buttons on the dashboard, or set `vision.source` in `config.yaml` to a video file path.

## Hardware setup

1. **Webcam** – plug in; `vision.source: 0` (try 1 for a USB cam).
2. **Ranger tag** – flash `firmware/ranger_tag/ranger_tag.ino` to a spare ESP32, change `TAG_NAME` per ranger, and add the same name under `ble.tags` in `config.yaml`. (Any BLE beacon works if you put its MAC in `address`.) Needs a laptop with Bluetooth 4.0+.
3. **Flame node** – wire the flame sensor (see header of `firmware/flame_node/flame_node.ino`), set Wi-Fi + the laptop's IP, flash. Put its real GPS in `flame.nodes`.
4. **Site GPS** – set `site.lat/lon` in `config.yaml`. Camera alerts are stamped with this fixed position (a laptop has no GPS).

## Dashboard

Blue/white, single page. Click any card, KPI, sensor, node pin or alert and it zooms into a detail dialog (live camera with what it is seeing, node telemetry, alert snapshot, 24 h activity, map). The map shows every node, with **this node pulsing and highlighted**, plus pins for unacknowledged alerts. Map tiles need internet (CARTO/OpenStreetMap); everything else works offline on the LAN.

Other field nodes (`nodes:` in `config.yaml`) report in by `POST /api/nodes/heartbeat` with JSON like
`{"node":"NODE-02","battery":81,"rssi":-70,"temp":27.5,"humidity":40,"people":0,"seeing":["clear"]}`.
A node shows offline after `flame.offline_after_s` seconds of silence. Use **Demo tools → Populate nodes** to fill them with simulated readings.

## The two models

**Poacher (vision)** – out of the box uses pretrained YOLO11n (`person`). To make it a real poacher model: label images, `python training/train_poacher.py data.yaml`, then point `vision.model` at `runs/poacher/weights/best.pt` (see the docstring).

**Gunshot (audio)** – out of the box YAMNet's built-in "Gunshot, gunfire / Machine gun / Fusillade / Artillery fire / Cap gun" scores (zero-shot, threshold 0.35). To make it yours: drop WAVs into `data/gunshot_audio/{gunshot,other}/` and run `python training/train_gunshot.py`; it's picked up automatically.

## Honest limitations (read before demoing as "finished")

- **Neither model is field-validated.** Zero-shot YAMNet will confuse some bangs/fireworks/door slams with gunshots and will miss distant shots; tune `audio.threshold` on real recordings and train the custom head. COCO `person` finds *any* human; it does not know who is a poacher — that's the BLE tag's job.
- **BLE tag = trust by possession.** Anyone who steals a tag (or clones its name) passes as a ranger. Fine for a prototype; for production use rotating/signed beacons.
- Laptop mic hears maybe tens of metres; real deployment needs outdoor mics per node.
- GSM/LoRa uplink, solar power, and ESP32-CAM edge nodes from the full project brief are **not** in this build — this is the laptop-centric stage.
- The dashboard has no login. Don't expose port 8000 to the internet; put it behind a VPN/reverse proxy with auth first.

## Tests

`pytest -q tests` – alert-engine logic (ranger/poacher/armed/cooldown/fire) and the HTTP/WebSocket API.
