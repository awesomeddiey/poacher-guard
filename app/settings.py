"""Settings changed from the dashboard: SMS phone numbers and gunshot tuning.

Saved in data/settings.json on this PC (never uploaded to GitHub, kept by the auto-update). Values not set here
come from config.yaml. Changes apply at once: the microphone worker reads the tuning on every scored window,
and the phone numbers are sent to the sensor node over its link (it stores them, so fire texts work without the PC).
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any, Callable

# Zimbabwe mobile numbers: Econet 077/078, NetOne 071, Telecel 073 (10 digits starting 07)
_ZW_LOCAL = re.compile(r"^07[1378]\d{7}$")


def normalize_phone(raw: str) -> str:
    """'0772109787', '0772 109 787', '+263772109787', '263772109787' -> '+263772109787'. ValueError if not a mobile."""
    p = re.sub(r"[\s\-()]", "", str(raw))
    if p.startswith("+263"):
        p = "0" + p[4:]
    elif p.startswith("263") and len(p) == 12:
        p = "0" + p[3:]
    if not _ZW_LOCAL.match(p):
        raise ValueError(f"'{raw}' is not a Zimbabwe mobile number. Use the format 0772109787")
    return "+263" + p[1:]


def local_format(intl: str) -> str:
    """'+263772109787' -> '0772109787' (how people write it)."""
    return "0" + intl[4:] if intl.startswith("+263") else intl


TUNING_LIMITS = {                       # name: (min, max)
    "threshold": (0.05, 0.95),          # YAMNet gunshot score that raises an alert
    "min_db": (-50.0, -3.0),            # loud-bang: how loud (dBFS)
    "rise_db": (5.0, 45.0),             # loud-bang: how much louder than the room just before
    "voice_veto": (0.05, 1.01),         # loud-bang: ignore when a voice scores at least this (1.01 = never ignore)
}
DETECTORS = ("model", "loudness", "either")


class Settings:
    def __init__(self, path: Path, cfg: dict[str, Any]):
        self.path = Path(path)
        a, b = cfg.get("audio", {}), cfg.get("audio", {}).get("bang", {})
        self.defaults = {
            "phones": [],
            "gunshot": {"detector": a.get("detector", "either"), "threshold": float(a.get("threshold", 0.35)),
                        "min_db": float(b.get("min_db", -20)), "rise_db": float(b.get("rise_db", 15)),
                        "voice_veto": float(b.get("voice_veto", 0.3))},
        }
        self._lock = threading.Lock()
        self._listeners: list[Callable[[dict[str, Any]], None]] = []
        self.data = json.loads(json.dumps(self.defaults))
        if self.path.exists():
            try:
                saved = json.loads(self.path.read_text())
                self.data["phones"] = [normalize_phone(p) for p in saved.get("phones", [])]
                self.data["gunshot"].update({k: v for k, v in saved.get("gunshot", {}).items() if k in self.data["gunshot"]})
            except Exception:  # noqa: BLE001  - a damaged file must not stop the app
                pass

    # ---- reading -------------------------------------------------------------------------------
    @property
    def phones(self) -> list[str]:
        return list(self.data["phones"])

    @property
    def gunshot(self) -> dict[str, Any]:
        return dict(self.data["gunshot"])

    def public(self) -> dict[str, Any]:
        """For the dashboard: numbers in the 07... format, plus the limits and defaults for the sliders."""
        return {"phones": [local_format(p) for p in self.data["phones"]], "gunshot": self.gunshot,
                "limits": TUNING_LIMITS, "detectors": DETECTORS, "defaults": self.defaults["gunshot"]}

    # ---- changing ------------------------------------------------------------------------------
    def on_change(self, fn: Callable[[dict[str, Any]], None]) -> None:
        self._listeners.append(fn)

    def update(self, patch: dict[str, Any]) -> dict[str, Any]:
        """Validate and apply a change from the dashboard. ValueError with a readable message if anything is wrong."""
        with self._lock:
            new = json.loads(json.dumps(self.data))
            if "phones" in patch:
                raw = patch["phones"]
                items = raw if isinstance(raw, list) else re.split(r"[,;\n]", str(raw))
                phones = []
                for item in items:
                    if str(item).strip():
                        p = normalize_phone(item)
                        if p not in phones:
                            phones.append(p)
                if len(phones) > 5:
                    raise ValueError("At most 5 phone numbers")
                new["phones"] = phones
            if patch.get("reset_gunshot"):
                new["gunshot"] = dict(self.defaults["gunshot"])
            for k, v in (patch.get("gunshot") or {}).items():
                if k == "detector":
                    if v not in DETECTORS:
                        raise ValueError(f"detector must be one of {', '.join(DETECTORS)}")
                    new["gunshot"][k] = v
                elif k in TUNING_LIMITS:
                    lo, hi = TUNING_LIMITS[k]
                    v = float(v)
                    if not lo <= v <= hi:
                        raise ValueError(f"{k} must be between {lo} and {hi}")
                    new["gunshot"][k] = round(v, 3)
            self.data = new
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(new, indent=1))
            tmp.replace(self.path)
        for fn in self._listeners:
            try:
                fn(self.data)
            except Exception:  # noqa: BLE001
                pass
        return self.public()
