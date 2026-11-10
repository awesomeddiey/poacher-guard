"""Poacher Guard self-update. run-poacher-guard.bat runs it before every start:

    .venv\\Scripts\\python.exe tools\\update.py --skip run-poacher-guard.bat

* Asks GitHub for the newest commit. Offline, or nothing new: does nothing and the app starts as before.
* A git clone is updated with `git pull`. A ZIP / GET-POACHER-GUARD install downloads the newest ZIP and copies it over.
* Never touched: .venv, data, install.log, tools\\node-settings.json, tools\\arduino-cli and the batch file that is
  running right now (Windows cannot safely rewrite it while it runs).
* config.yaml: replaced only if you have not changed it since the last update; otherwise yours is kept and the new
  default settings are saved next to it as config.yaml.new.
* If requirements.txt changed the packages are installed again. If the ESP32 sketch changed it says so: the node has to be
  re-programmed with UPLOAD-ESP32-NODE.bat (the PC cannot do that by itself).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

REPO, BRANCH = "awesomeddiey/poacher-guard", "main"
ROOT = Path(__file__).resolve().parent.parent
NEVER = (".git/", ".venv/", "data/", "tools/arduino-cli/")
NEVER_FILES = {"install.log", "tools/node-settings.json", ".version", "config.yaml.new"}
SKETCH = "firmware/flame_gsm_node/flame_gsm_node.ino"
UA = {"User-Agent": "poacher-guard-updater"}


def sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def fetch(url: str, timeout: float, headers: dict[str, str] | None = None) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers={**UA, **(headers or {})}), timeout=timeout) as r:
        return r.read()


def update(root: Path, api_url: str, zip_url: str, skip: tuple[str, ...] = (), run_pip: bool = True, say=print) -> str:
    """Returns 'offline', 'current' or 'updated'."""
    ver_file = root / ".version"
    ver = json.loads(ver_file.read_text()) if ver_file.exists() else {}
    is_git = (root / ".git").exists() and shutil.which("git")
    try:
        remote = fetch(api_url, 8, {"Accept": "application/vnd.github.sha"}).decode().strip()
    except Exception as e:  # noqa: BLE001
        say(f"Update check skipped (no internet or GitHub unreachable: {str(e)[:60]}). Starting the copy on this PC.")
        return "offline"

    if is_git:
        local = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        if local == remote:
            say("Poacher Guard is up to date.")
            return "current"
        say("Updating from GitHub (git pull)...")
        before = {k: sha256(root / k) for k in ("requirements.txt", SKETCH)}
        r = subprocess.run(["git", "-C", str(root), "pull", "--ff-only", "-q"], capture_output=True, text=True)
        if r.returncode:
            say("Could not update (you have local changes in the project folder). Starting the copy on this PC.\n  " + r.stderr.strip()[:200])
            return "offline"
        _after(root, before, run_pip, say)
        return "updated"

    if ver.get("sha") == remote:
        say("Poacher Guard is up to date.")
        return "current"
    say("A newer Poacher Guard is available. Downloading (about 75 MB)...")
    try:
        data = fetch(zip_url, 180)
        z = zipfile.ZipFile(io.BytesIO(data))
    except Exception as e:  # noqa: BLE001
        say(f"Download failed ({str(e)[:60]}). Starting the copy on this PC.")
        return "offline"
    names = [n for n in z.namelist() if not n.endswith("/")]
    top = names[0].split("/", 1)[0] + "/"
    before = {k: sha256(root / k) for k in ("requirements.txt", SKETCH)}
    new_cfg = None
    for n in names:
        rel = n[len(top):]
        if not rel or rel in NEVER_FILES or rel in skip or rel.startswith(NEVER):
            continue
        if rel == "config.yaml":
            new_cfg = z.read(n)
            continue
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(z.read(n))
    cfg_note = ""
    if new_cfg is not None:
        cfg, new_hash = root / "config.yaml", hashlib.sha256(new_cfg).hexdigest()
        if not cfg.exists() or sha256(cfg) == ver.get("config_sha256") or sha256(cfg) == new_hash:
            cfg.write_bytes(new_cfg)
        else:
            (root / "config.yaml.new").write_bytes(new_cfg)
            cfg_note = "config.yaml has your own changes, so it was kept. New default settings: config.yaml.new"
        ver["config_sha256"] = new_hash
    ver["sha"] = remote
    ver_file.write_text(json.dumps(ver))
    _after(root, before, run_pip, say)
    if cfg_note:
        say(cfg_note)
    return "updated"


def _after(root: Path, before: dict[str, str | None], run_pip: bool, say) -> None:
    say("Updated.")
    if sha256(root / "requirements.txt") != before["requirements.txt"] and run_pip:
        say("New packages are needed: installing (a few minutes)...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", str(root / "requirements.txt"), "--disable-pip-version-check"])
    if sha256(root / SKETCH) != before[SKETCH]:
        say("NOTE: the ESP32 node program changed. Plug the node in by USB and run UPLOAD-ESP32-NODE.bat to update it.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip", action="append", default=[], help="file that must not be replaced (the running batch file)")
    a = ap.parse_args()
    api = os.environ.get("PG_UPDATE_API", f"https://api.github.com/repos/{REPO}/commits/{BRANCH}")
    zip_url = os.environ.get("PG_UPDATE_ZIP", f"https://github.com/{REPO}/archive/refs/heads/{BRANCH}.zip")
    try:
        update(ROOT, api, zip_url, tuple(a.skip))
    except Exception as e:  # noqa: BLE001  - an update problem must never stop the app from starting
        print(f"Update skipped ({e}). Starting the copy on this PC.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
