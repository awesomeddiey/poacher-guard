"""3D models of the parts that go inside and on the field node casing, placed exactly where the casing expects them.
Coordinates are the casing's (cavity corner = origin, base plate top = z 0). Run:  python make_components.py  -> stl/components/*.stl
These are visual stand-ins sized from typical boards, good enough to check fit and to animate the assembly."""
import json
from pathlib import Path

import numpy as np
import trimesh
from trimesh.convex import convex_hull
from trimesh.creation import box, cylinder, icosphere
from trimesh.transformations import rotation_matrix as rot, translation_matrix as tr

import make_field_node as C

OUT = Path(__file__).parent / "stl" / "components"; OUT.mkdir(parents=True, exist_ok=True)
B, Cz, Cy = C.B, C.Cz, C.Cy
U = C.U
hull = C.hull


def Cx(y, x0, x1, z, r, n=32): return cylinder(radius=r, height=x1 - x0, sections=n, transform=tr([(x0 + x1) / 2, y, z]) @ rot(np.pi / 2, [0, 1, 0]))
def rbox(x0, x1, y0, y1, z0, z1, r):
    r = min(r, (x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2); pts = []
    for x in (x0 + r, x1 - r):
        for y in (y0 + r, y1 - r):
            for z in (z0 + r, z1 - r): pts.append(icosphere(subdivisions=2, radius=r).apply_translation([x, y, z]).vertices)
    return convex_hull(np.vstack(pts))
CENTER = {}
def tube(points, r, n=10, name=None):
    """Smooth cable: Catmull-Rom spline through points, built from short cylinders."""
    P = np.array(points, float); out = []
    ext = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-1]); out = np.array(out); segs = []
    if name: CENTER[name] = (out, r)
    for a, b in zip(out[:-1], out[1:]):
        d = b - a; L = np.linalg.norm(d)
        if L < 1e-6: continue
        m = trimesh.creation.cylinder(radius=r, height=L, sections=14); z = np.array([0, 0, 1.0]); v = d / L
        ax = np.cross(z, v); s = np.linalg.norm(ax)
        T = np.eye(4)
        if s > 1e-8: T = rot(np.arctan2(s, z @ v), ax / s)
        elif v[2] < 0: T = rot(np.pi, [1, 0, 0])
        T[:3, 3] = (a + b) / 2; m.apply_transform(T); segs.append(m)
        segs.append(icosphere(subdivisions=1, radius=r).apply_translation(b))
    return trimesh.util.concatenate(segs)


ESP, FL = C.ESP, C.FLAME
M4 = lambda rows: np.vstack([np.array(rows, float), [0, 0, 0, 1.0]])
# Parts are modelled in a local frame (width = x, length / forward = y, up = z) and then moved to where the portrait casing expects them.
ex0 = 0.0; ex1 = ex0 + ESP["W"]; y0 = 1.5 + C.FIT; zb = ESP["pins"]; ecx = (ex0 + ex1) / 2
TE = M4([[0, 1, 0, 0], [-1, 0, 0, C.ESP_CY + ecx], [0, 0, 1, 0]])                       # local length -> world x (USB end at the bottom wall), local width -> world y
fx0 = 0.0; fx1 = fx0 + FL["W"]; fcx = (fx0 + fx1) / 2; sy = FL["L"]; zf = FL["post"]
TF = M4([[0, 1, 0, C.XH + 3.0 - sy], [-1, 0, 0, C.YC + fcx], [0, 0, 1, 0]])             # module lies flat on its post, head end towards +x
pw, pd, pr = C.PAD; ZD = 0.0                                                          # webcam: local origin = deck centre, up = away from the top wall
TC = M4([[0, 0, 1, C.XO1 - pr], [1, 0, 0, C.YC], [0, 1, 0, C.PAD_CZ]])                  # local width -> world y, local forward -> world z (away from the tree)

parts = {}
# ---- ESP32 DevKit V1 ----
pcb = B(ex0, ex1, y0, y0 + ESP["L"], zb, zb + ESP["T"])
parts["esp32_pcb"] = (U([pcb, B(ecx - 4.5, ecx + 4.5, y0 - 1.6, y0 + 3.5, zb + ESP["T"], zb + ESP["T"] + 2.6),                      # micro-USB
                         B(ex0 + 2, ex0 + 6, y0 + 5, y0 + 9, zb + ESP["T"], zb + ESP["T"] + 1.8), B(ex1 - 6, ex1 - 2, y0 + 5, y0 + 9, zb + ESP["T"], zb + ESP["T"] + 1.8),   # EN / BOOT
                         B(ecx - 2.5, ecx + 2.5, y0 + 10, y0 + 15, zb + ESP["T"], zb + ESP["T"] + 1.0)]), "#111827", TE)
parts["esp32_module"] = (U([B(ecx - 9, ecx + 9, y0 + ESP["L"] - 25.5, y0 + ESP["L"] - 6, zb + ESP["T"], zb + ESP["T"] + 3.2)]), "#cbd5e1", TE)                  # WROOM shield
parts["esp32_headers"] = (U([B(x - 1.27, x + 1.27, y0 + 2.5, y0 + ESP["L"] - 2.5, zb - 2.5, zb) for x in (ex0 + 1.8, ex1 - 1.8)]), "#0b1220", TE)
parts["esp32_pins"] = (U([B(x - 0.3, x + 0.3, y - 0.3, y + 0.3, zb - 9.5, zb - 2.4) for x in (ex0 + 1.8, ex1 - 1.8) for y in np.arange(y0 + 3.8, y0 + ESP["L"] - 3, 2.54)]), "#d4a017", TE)
parts["esp32_antenna"] = (B(ecx - 8, ecx + 8, y0 + ESP["L"] - 5.5, y0 + ESP["L"] - 0.6, zb + ESP["T"], zb + ESP["T"] + 0.15), "#d4a017", TE)
# ---- flame sensor module (flat on a tall post, IR head standing up through the roof) ----
fpcb = B(fx0, fx1, sy - FL["L"], sy, zf, zf + FL["T"])
parts["flame_pcb"] = (U([fpcb, B(fx0 + 1.5, fx1 - 1.5, sy - FL["L"] + 3, sy - FL["L"] + 5.5, zf + FL["T"], zf + FL["T"] + 8 * 0.35)]), "#166534", TF)
parts["flame_pot"] = (B(fcx - 4, fcx + 4, sy - FL["L"] + 8, sy - FL["L"] + 13, zf + FL["T"], zf + FL["T"] + 4.5), "#3b82f6", TF)
parts["flame_chip"] = (B(fcx - 2.5, fcx + 2.5, sy - 14, sy - 8, zf + FL["T"], zf + FL["T"] + 1.5), "#0b1220", TF)
parts["flame_leds"] = (U([B(fcx + 3.5, fcx + 5.0, sy - 20, sy - 18.5, zf + FL["T"], zf + FL["T"] + 0.8), B(fcx - 5.0, fcx - 3.5, sy - 20, sy - 18.5, zf + FL["T"], zf + FL["T"] + 0.8)]), "#ef4444", TF)
parts["flame_header"] = (B(fcx - 5.1, fcx + 5.1, sy - FL["L"] + 0.5, sy - FL["L"] + 3, zf + FL["T"], zf + FL["T"] + 2.5), "#0b1220", TF)
tipz = C.HS + FL["poke"]                                                              # the IR head pokes out through the roof
parts["flame_sensor"] = (U([Cz(C.XH, C.YC, zf + FL["T"], tipz - 2.5, 2.5, 32), icosphere(subdivisions=2, radius=2.5).apply_translation([C.XH, C.YC, tipz - 2.5]),
                            B(C.XH - 2.5, C.XH + 2.5, C.YC - 2.5, C.YC + 2.5, zf + FL["T"], zf + FL["T"] + 4)]), "#111827", None)
# ---- USB cables: ESP32 (micro-B) and webcam (type A), both hang out of the bottom end ----
parts["esp_usb_plug"] = (U([B(ecx - 5.5, ecx + 5.5, y0 - 16, y0 - 1.6, zb + 0.9, zb + 5.0)]), "#0b1220", TE)
ex, ey = 1.5 + C.FIT, C.ESP_CY
parts["esp_usb_cable"] = (tube([(ex - 16, ey, zb + 3.0), (ex - 30, ey, zb + 3.0), (ex - 55, ey, zb + 0.5), (ex - 80, ey + 5, -C.PLATE + 1.8), (ex - 105, ey + 20, -C.PLATE + 1.8)], 1.8, name="esp_usb_cable"), "#e5e7eb", None)
hz = C.PAD_CZ - pd / 2 - 2.5; hx = C.CAM_HY
parts["cam_usb_cable"] = (tube([(C.XO1 - pr + 6, hx, hz), (C.XIN + 0.4, hx, hz), (C.XIN - 10, hx, 7.0), (C.XIN - 30, hx, 9.0), (C.XIN - 70, hx, 12.0), (30.0, hx, 12.6), (8.0, hx - 1, 12.6),
                             (-2.0, hx - 1, 12.6), (-22, hx - 1, 12.6), (-50, hx - 4, 6), (-78, hx + 10, -C.PLATE + 1.8), (-100, hx + 34, -C.PLATE + 1.8)], 2.2, name="cam_usb_cable"), "#111827", None)
# ---- webcam on a clip-style base (generic), standing on the top end wall, lens facing away from the tree ----
fy0, fy1 = -(pd - 2) / 2, (pd - 2) / 2
parts["webcam_base"] = (rbox(-25, 25, fy0, fy1, ZD, ZD + 6, 2.5), "#111827", TC)
parts["webcam_neck"] = (rbox(-7, 7, 2, 12, ZD + 5, ZD + 15, 2), "#1f2937", TC)
hz0 = ZD + 12
parts["webcam_head"] = (rbox(-29, 29, -2, 20, hz0, hz0 + 22, 5), "#111827", TC)
lz = hz0 + 11
parts["webcam_lens_ring"] = (Cy(0, 20, 22.2, lz, 10.5, 48), "#9ca3af", TC)
parts["webcam_lens"] = (Cy(0, 22.0, 23.0, lz, 7.5, 48), "#0f172a", TC)
parts["webcam_led"] = (Cy(15, 20, 20.8, lz + 5, 1.1, 16), "#22c55e", TC)
# ---- zip ties (2 across the base, through the four slots) ----
ties = []
for sy_ in (-1, 1):
    y = sy_ * (pd / 2 - 3.0); xa, xb = -(pw / 2 - 3.0), (pw / 2 - 3.0)
    ties += [B(xa - 0.5, xb + 0.5, y - 1.25, y + 1.25, ZD + 6.0, ZD + 7.0), B(xa - 0.5, xa + 0.5, y - 1.25, y + 1.25, -(C.WALL - pr) - 2.5, ZD + 7.0), B(xb - 0.5, xb + 0.5, y - 1.25, y + 1.25, -(C.WALL - pr) - 2.5, ZD + 7.0)]
parts["zip_ties"] = (U(ties), "#f8fafc", TC)
# ---- screws and feet ----
for i, (x, y) in enumerate(C.BOSSES):
    parts[f"screw_{i + 1}"] = (U([hull([Cz(x, y, -C.PLATE + 0.0, -C.PLATE + 0.1, 3.0, 24), Cz(x, y, -C.PLATE + 1.7, -C.PLATE + 1.8, 1.5, 24)]), Cz(x, y, -C.PLATE + 1.7, -C.PLATE + 18.0, 1.5, 16)]), "#9ca3af", None)
for i, (x, y) in enumerate(C.CORN):
    parts[f"foot_{i + 1}"] = (Cz(x, y, -C.PLATE - 1.5, -C.PLATE + 0.3, 5.0, 32), "#0b1220", None)
for k, (m, c, T) in list(parts.items()):
    if T is not None: m = m.copy(); m.apply_transform(T)
    parts[k] = (m, c)

manifest = {}
for name, (m, color) in parts.items():
    m.export(OUT / f"{name}.stl"); manifest[name] = dict(color=color, triangles=len(m.faces))
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=1)); print(len(manifest), "components written")
# interference report: components against the shell and base (should all be zero except where parts are meant to pass through)
sh = trimesh.load(Path(__file__).parent / "stl" / "field_node_shell.stl", process=True); bs = trimesh.load(Path(__file__).parent / "stl" / "field_node_base.stl", process=True)
ov = lambda a, b: round(trimesh.boolean.intersection([a, b], engine="manifold", check_volume=False).volume, 1)
rep = {}
for k in ("esp32_pcb", "esp32_module", "esp32_headers", "flame_pcb", "flame_sensor", "esp_usb_plug", "esp32_pins", "webcam_base", "webcam_head", "zip_ties", "screw_1", "screw_4", "foot_1"):
    try: rep[k] = dict(shell_mm3=ov(parts[k][0], sh), base_mm3=ov(parts[k][0], bs))
    except Exception as e: rep[k] = f"not checked ({str(e)[:40]})"
for k, (pts, r) in CENTER.items():       # cables: the centre line must stay at least one cable radius from every solid
    both = trimesh.util.concatenate([sh, bs]); d = np.abs(trimesh.proximity.closest_point(both, pts)[1])
    inside = int(sh.contains(pts).sum() + bs.contains(pts).sum())
    rep[k] = dict(points_inside_solid=inside, min_clearance_mm=round(float(d.min()), 2), cable_radius_mm=r)
print(json.dumps(rep, indent=0)); (Path(__file__).parent / "components_report.json").write_text(json.dumps(rep, indent=1))
