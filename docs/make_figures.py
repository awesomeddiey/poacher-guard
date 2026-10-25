"""Draws Figure 3.1 (system architecture) and Figure 3.2 (alert decision logic) for Chapter 3."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = Path(__file__).parent / "chapter3" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams["font.family"] = "DejaVu Serif"


def box(ax, x, y, w, h, text, fc="#ffffff", ec="#1e293b", fs=9, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec=ec, lw=1.2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, fontweight="bold" if bold else "normal", wrap=True)


def arrow(ax, a, b, text=None, off=(0, 0.08)):
    ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="->", lw=1.2, color="#1e293b"))
    if text:
        ax.text((a[0] + b[0]) / 2 + off[0], (a[1] + b[1]) / 2 + off[1], text, fontsize=8, ha="center")


# ---- Figure 3.1 architecture ----
fig, ax = plt.subplots(figsize=(10, 5.6)); ax.set_xlim(0, 10); ax.set_ylim(0, 5.6); ax.axis("off")
ax.add_patch(FancyBboxPatch((3.2, 0.3), 4.1, 5.0, boxstyle="round,pad=0.02,rounding_size=0.1", fc="#eff6ff", ec="#1d4ed8", lw=1.5))
ax.text(5.25, 5.05, "Base station (laptop)", ha="center", fontsize=10, fontweight="bold", color="#1d4ed8")
box(ax, 3.45, 3.75, 3.6, 0.8, "Poacher detection model\n(YOLO11n, person and weapon)")
box(ax, 3.45, 2.75, 3.6, 0.8, "Gunshot detection model\n(YAMNet scores + classifier)")
box(ax, 3.45, 1.75, 3.6, 0.8, "BLE scanner\n(ranger tag registry)")
box(ax, 3.45, 0.55, 3.6, 0.95, "Alert engine\n(fusion rules, cooldowns)", fc="#dbeafe", bold=True)
inputs = [("Webcam", 4.15), ("Laptop microphone", 3.15), ("Ranger tag\n(ESP32, BLE advertising)", 2.15)]
for t, y in inputs:
    box(ax, 0.2, y - 0.3, 2.3, 0.75, t, fs=8.5)
    arrow(ax, (2.5, y + 0.08), (3.45, y + 0.08))
box(ax, 0.2, 0.55, 2.3, 0.95, "Flame node\n(ESP32 + flame sensor)", fs=8.5)
arrow(ax, (2.5, 1.0), (3.45, 1.0), "Wi-Fi POST", off=(0, 0.1))
for y in (4.15, 3.15, 2.15): pass
arrow(ax, (5.25, 1.75), (5.25, 1.5))
box(ax, 7.9, 3.6, 1.9, 0.8, "SQLite event log\nand snapshots", fs=8.5)
box(ax, 7.9, 2.3, 1.9, 0.8, "Web dashboard\n(browser, WebSocket)", fs=8.5, fc="#dbeafe")
box(ax, 7.9, 1.0, 1.9, 0.8, "Telegram alert\n(optional)", fs=8.5)
for y in (4.0, 2.7, 1.4): arrow(ax, (7.05, 1.0 + 0.2), (7.9, y))
fig.savefig(OUT / "fig3_1_architecture.png", dpi=220, bbox_inches="tight"); plt.close(fig)

# ---- Figure 3.2 decision logic ----
fig, ax = plt.subplots(figsize=(10, 5.8)); ax.set_xlim(0, 10); ax.set_ylim(0, 5.8); ax.axis("off")
box(ax, 0.2, 4.7, 2.4, 0.8, "Person confirmed\n(3 of last 6 frames)", fc="#dbeafe")
box(ax, 3.2, 4.7, 2.2, 0.8, "Weapon class\nin frame?")
box(ax, 6.0, 4.7, 3.6, 0.8, "ARMED INTRUDER\n(critical alert)", fc="#fee2e2")
box(ax, 3.2, 3.2, 2.6, 0.9, "Ranger tag heard in\nlast 15 s and RSSI\n≥ -90 dBm?")
box(ax, 6.4, 3.2, 3.2, 0.9, "Ranger sighting\n(information, no alarm)", fc="#eff6ff")
box(ax, 3.2, 1.7, 2.6, 0.9, "Gunshot in the last\n120 s?")
box(ax, 6.4, 1.7, 3.2, 0.9, "ARMED POACHER\n(critical alert)", fc="#fee2e2")
box(ax, 3.2, 0.2, 2.6, 0.9, "POACHER ALERT\n(critical alert)", fc="#fee2e2")
arrow(ax, (2.6, 5.1), (3.2, 5.1)); arrow(ax, (5.4, 5.1), (6.0, 5.1), "yes")
arrow(ax, (4.5, 4.7), (4.5, 4.1), "no", off=(0.25, 0)); arrow(ax, (5.8, 3.65), (6.4, 3.65), "yes")
arrow(ax, (4.5, 3.2), (4.5, 2.6), "no", off=(0.25, 0)); arrow(ax, (5.8, 2.15), (6.4, 2.15), "yes")
arrow(ax, (4.5, 1.7), (4.5, 1.1), "no", off=(0.25, 0))
ax.text(6.4, 0.65, "Separate triggers: a gunshot alone raises a\ngunshot alert and a flame node reading below\nthreshold raises a fire alert. Every alert type\nhas its own cooldown period.", fontsize=8.5, va="center")
fig.savefig(OUT / "fig3_2_alert_logic.png", dpi=220, bbox_inches="tight"); plt.close(fig)
print("figures done")
