"""Poacher Guard field node casing (millimetres). Run:  python make_field_node.py   ->  stl/*.stl, report.json

One casing, two printed parts:
  field_node_shell.stl   white "pebble" shell: sensor slit with sun visor (front), camera deck with zip-tie slots (top),
                         vent slots (left), engraved wordmark (right), one cable port (rear). Print upside down (roof on the bed).
  field_node_base.stl    blue base plate: 4 hidden screws from below, board supports, 1/4-20 tripod thread, rubber-foot pockets.
Inside: ESP32 DevKit V1 (30 pin) and a 4-pin flame sensor module. The USB webcam sits on the deck; its cable and the
ESP32 cable leave through the rear port. Edit PARAMETERS to match your boards.
"""
import json
from pathlib import Path

import numpy as np
import trimesh
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from shapely.geometry import MultiPolygon, Polygon
from trimesh.convex import convex_hull
from trimesh.creation import box, cylinder, extrude_polygon, icosphere
from trimesh.transformations import rotation_matrix as rot, translation_matrix as tr

OUT = Path(__file__).parent; (OUT / "stl").mkdir(exist_ok=True)
# ---------------------------------------------------------------- PARAMETERS
# Tree-mounted, portrait: x runs UP the trunk (150 mm), y is the width (100 mm), z points away from the tree (45 mm).
# The base plate lies against the bark and carries the boards and four strap lugs; the shell is the weather side.
WALL, PLATE, R, FIT = 2.6, 4.5, 7.0, 0.35        # wall, base plate, outer corner/edge radius, fit clearance
OUT_X, OUT_Y, OUT_Z = 150.0, 100.0, 45.0         # outer size of the casing body: height, width, depth (lugs and webcam are extra)
XIN, YIN, ZIN = OUT_X - 2 * WALL, OUT_Y - 2 * WALL, OUT_Z - PLATE - WALL   # inner cavity: 144.8 x 94.8 x 37.9
ESP = dict(L=51.5, W=28.5, T=1.6, pins=10.0)     # ESP32 DevKit V1: pins point down, board sits on 10 mm blocks
FLAME = dict(L=32.0, W=14.0, T=1.6, post=25.0, poke=6.0)   # module hangs on a tall post; its IR head points at the roof and pokes "poke" mm out of it
SENSOR_HOLE_R = 3.4                              # hole for the 5 mm IR sensor head
ESP_XC = 20.0                                    # ESP32 centre line (x); its USB end points at the right side wall, where the port is
PAD = (50.0, 26.0, 0.8)                          # camera deck on the TOP END wall: width (y), depth (z), recess
PAD_CZ = 20.5                                    # z of the deck centre
LUG = dict(L=44.0, out=18.0, T=6.0, win_l=30.0, win_w=5.0, xs=(40.0, XIN - 28.0))   # strap lugs: length along the trunk, projection, thickness, strap window (fits a 25 mm strap)
WORDMARK = "POACHER GUARD"
# ---------------------------------------------------------------------------
HS = ZIN + WALL                                  # shell height above the opening plane (z = 0)
XO0, XO1, YO0, YO1 = -WALL, XIN + WALL, -WALL, YIN + WALL
YC = YIN / 2
XH = XIN - 45.0                                  # IR sensor head position (x); y = YC
CORN = [(XO0 + R, YO0 + R), (XO1 - R, YO0 + R), (XO0 + R, YO1 - R), (XO1 - R, YO1 - R)]
BALLAST = dict(x0=4.0, x1=40.0, y0=6.0, y1=38.0, h=18.0)
BOSSES = [(XIN * 0.3, 0.4), (XIN * 0.75, 0.4), (XIN * 0.3, YIN - 0.4), (XIN * 0.75, YIN - 0.4)]


def B(x0, x1, y0, y1, z0, z1): return box(extents=[x1 - x0, y1 - y0, z1 - z0], transform=tr([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2]))
def Cz(x, y, z0, z1, r, n=40): return cylinder(radius=r, height=z1 - z0, sections=n, transform=tr([x, y, (z0 + z1) / 2]))
def Cy(x, y0, y1, z, r, n=40): return cylinder(radius=r, height=y1 - y0, sections=n, transform=tr([x, (y0 + y1) / 2, z]) @ rot(np.pi / 2, [1, 0, 0]))
def U(parts): return trimesh.boolean.union(parts, engine="manifold")
def D(a, parts): return trimesh.boolean.difference([a] + list(parts), engine="manifold")
def hull(parts): return convex_hull(np.vstack([p.vertices for p in parts]))
def stadium_y(xc, zc, w, h, y0, y1): return hull([Cy(xc - (w - h) / 2, y0, y1, zc, h / 2), Cy(xc + (w - h) / 2, y0, y1, zc, h / 2)])   # slot cut along y
def stadium_x(yc, zc, w, h, x0, x1): return hull([Cy(0, 0, 1, 0, 0.1)] ) if False else hull([cylinder(radius=h / 2, height=x1 - x0, sections=40, transform=tr([(x0 + x1) / 2, yc + s * (w - h) / 2, zc]) @ rot(np.pi / 2, [0, 1, 0])) for s in (-1, 1)])


def pebble(r_out, z_bottom):
    cyl = [Cz(x, y, z_bottom, z_bottom + 1.0, r_out) for x, y in CORN]
    sph = [icosphere(subdivisions=3, radius=r_out).apply_translation([x, y, HS - R]) for x, y in CORN]
    return hull(cyl + sph)


def wordmark_mesh(depth=1.6):
    tp = TextPath((0, 0), WORDMARK, size=5.2, prop=FontProperties(family="DejaVu Sans", weight="bold"))
    polys = [Polygon(p) for p in tp.to_polygons() if len(p) >= 3]; poly = polys[0]
    for p in polys[1:]: poly = poly.symmetric_difference(p)
    geoms = list(poly.geoms) if isinstance(poly, MultiPolygon) else [poly]
    m = trimesh.util.concatenate([extrude_polygon(g, depth) for g in geoms if g.area > 0.05])
    c = m.bounds.mean(0); m.apply_translation([-c[0], -c[1], 0])
    m.apply_transform(np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1.0]]))      # text (u, v, depth) -> world (u along x, depth along y, v along z)
    return m


def shell():
    outer, inner = pebble(R, 0.0), pebble(R - WALL, -1.0)
    sh = D(outer, [inner])
    # round hole in the roof for the IR flame sensor head, which pokes out; soft bevel on the outside
    sh = D(sh, [Cz(XH, YC, HS - WALL - 1, HS + 1, SENSOR_HOLE_R), hull([Cz(XH, YC, HS - 1.6, HS - 1.59, SENSOR_HOLE_R), Cz(XH, YC, HS - 0.01, HS + 0.5, SENSOR_HOLE_R + 1.8)])])
    # side port on the right wall, lined up with the ESP32 micro-USB socket (the webcam plugs straight into the PC, so it needs no port)
    sh = D(sh, [stadium_y(ESP_XC, 12.5, 22.0, 9.0, YIN - 1.0, YO1 + 1)])
    # vents on the right side wall: 8 slots
    sh = D(sh, [B(60.0 + i * 6.0 - 1.0, 60.0 + i * 6.0 + 1.0, YIN - 1.0, YO1 + 1, 6.0, 30.0) for i in range(8)])
    # camera deck on the TOP END wall: shallow recess and four zip-tie slots
    pw, pd, pr = PAD
    sh = D(sh, [B(XO1 - pr, XO1 + 1, YC - pw / 2, YC + pw / 2, PAD_CZ - pd / 2, PAD_CZ + pd / 2)])
    ties = [B(XO1 - WALL - 1, XO1 + 1, YC + sx * (pw / 2 - 3.0) - 1.6, YC + sx * (pw / 2 - 3.0) + 1.6, PAD_CZ + sz * (pd / 2 - 3.0) - 1.9, PAD_CZ + sz * (pd / 2 - 3.0) + 1.9) for sx in (-1, 1) for sz in (-1, 1)]   # 3.2 x 3.8 mm slots for 2.5 mm cable ties
    sh = D(sh, ties)
    # engraved wordmark on the left side wall (reads along the trunk)
    wm = wordmark_mesh(); wm.apply_translation([XIN / 2, YO0 - 1.0, 20.0]); sh = D(sh, [wm])
    # screw bosses on the side walls, ending below the rounded roof edge
    ztop = HS - R - 0.3
    sh = U([sh] + [Cz(x, y, 3.2, ztop, 2.5) for x, y in BOSSES]); sh = D(sh, [Cz(x, y, 3.2, ztop - 3, 1.3, 24) for x, y in BOSSES])
    return sh, BOSSES


def lug(xc, side):
    """Strap lug: a tab sticking out of the base plate sideways with a window for a 25 mm strap. side = -1 (left, y < 0) or +1 (right)."""
    ye = (YO0 if side < 0 else YO1)                      # plate edge
    yo = ye + side * LUG["out"]                          # tip of the tab
    z0, z1 = -PLATE, -PLATE + LUG["T"]
    hl = LUG["L"] / 2
    srt = lambda p, q: (min(p, q), max(p, q))
    ya, yb = srt(ye - side * 3.0, yo - side * 5.0); yc_, yd_ = srt(ye + side * 0.4, yo - side * 5.0)
    plan = U([hull([Cz(xc - hl + 5, yo - side * 5, z0, z1, 5), Cz(xc + hl - 5, yo - side * 5, z0, z1, 5)]),
              B(xc - hl, xc + hl, ya, yb, z0, 0.0),                      # merges into the plate, stays below the shell
              B(xc - hl, xc + hl, yc_, yd_, z0, z1)])                    # thickened part, clear of the shell wall by 0.4 mm
    win_y = ye + side * (LUG["out"] - 6.0 - LUG["win_w"] / 2 - 1.0)
    win = hull([Cz(xc - LUG["win_l"] / 2 + LUG["win_w"] / 2, win_y, z0 - 1, z1 + 1, LUG["win_w"] / 2), Cz(xc + LUG["win_l"] / 2 - LUG["win_w"] / 2, win_y, z0 - 1, z1 + 1, LUG["win_w"] / 2)])
    return plan, win


def base(bosses):
    rr = lambda r, z0, z1: hull([Cz(x, y, z0, z1, r) for x, y in CORN])
    plate = rr(R, -PLATE, 0.0)
    ring = D(rr(R - WALL - FIT, 0.0, 2.4), [rr(R - WALL - FIT - 1.6, -1, 4.0)])                        # locating lip inside the shell
    parts = [plate, ring]
    # ESP32 guide blocks. Board frame: u across the width (0..W), v along the length from the USB end; world x = ESP_XC + W/2 - u, y = YIN - v
    v0 = 1.5; v1 = v0 + ESP["L"] + 2 * FIT; Wd = ESP["W"]
    for ua, ub in ((-3, -FIT / 2), (Wd + FIT / 2, Wd + 3)):
        for va, vb in ((v0, v0 + 5), (v1 - 5, v1)): parts.append(B(ESP_XC + Wd / 2 - ub, ESP_XC + Wd / 2 - ua, YIN - vb, YIN - va, 0, ESP["pins"]))
    # tall post for the flame module: a rib under the head end and a pillar at the far end
    fx1 = XH + 3.0; fx0 = fx1 - FLAME["L"]; fy0, fy1 = YC - FLAME["W"] / 2, YC + FLAME["W"] / 2
    parts += [B(fx1 - 11, fx1 - 8, fy0, fy1, 0, FLAME["post"]), Cz(fx0 + 3.0, fy0 + 3.0, 0, FLAME["post"], 3.6), B(fx0, fx0 + 6, fy0, fy0 + 6, 0, 0.5) if False else Cz(fx0 + 3.0, fy0 + 3.0, 0, 1, 6)]
    # ballast tray (bottom end, left of the ESP32): holds about 180 g of steel washers or lead shot so the node stands on its own end
    bx0, bx1, by0, by1, bh, bw = BALLAST["x0"], BALLAST["x1"], BALLAST["y0"], BALLAST["y1"], BALLAST["h"], 1.6
    parts.append(D(B(bx0, bx1, by0, by1, 0, bh), [B(bx0 + bw, bx1 - bw, by0 + bw, by1 - bw, 0.0, bh + 1)]))
    cuts, plans = [], []
    for xc in LUG["xs"]:
        for side in (-1, 1):
            p, w = lug(xc, side); parts.append(p); cuts.append(w)
    b = U(parts)
    cuts += [Cz(x, y, -PLATE - 1, 3.4, 1.75, 24) for x, y in bosses]                                   # screw holes (also pierce the locating lip)
    cuts += [hull([Cz(x, y, -PLATE - 0.5, -PLATE - 0.49, 3.9, 32), Cz(x, y, -PLATE + 1.8, -PLATE + 1.81, 1.6, 32)]) for x, y in bosses]   # countersink: wide at the back face, seats a flat-head M3
    cuts += [Cz(x, y, -PLATE - 0.01, -PLATE + 1.0, 5.2, 40) for x, y in CORN]                          # rubber-foot pockets (grip on the bark)
    cuts += [Cz(fx0 + 3.0, fy0 + 3.0, FLAME["post"] - 8, FLAME["post"] + 0.1, 1.2, 20)]               # flame module screw pilot
    return D(b, cuts), dict(esp_x=(ESP_XC - Wd / 2, ESP_XC + Wd / 2), flame=(fx0, fx1), lugs=LUG["xs"])


def main():
    sh, bosses = shell(); bs, info = base(bosses)
    sh.export(OUT / "stl" / "field_node_shell.stl"); bs.export(OUT / "stl" / "field_node_base.stl")
    sp = sh.copy(); sp.apply_transform(rot(np.pi, [1, 0, 0])); sp.apply_translation([0, 0, -sp.bounds[0][2]]); sp.export(OUT / "stl" / "field_node_shell_print_orientation.stl")
    rep = {}
    for n, m in (("shell", sh), ("base", bs)): rep[n] = dict(watertight=bool(m.is_watertight), size_mm=[round(x, 1) for x in m.extents], volume_cm3=round(m.volume / 1000, 1))
    # fit check: dummy ESP32 and flame module placed as designed must not touch the shell, and shell and base must not overlap
    fx0, fx1 = info["flame"]; ex0w, ex1w = info["esp_x"]; zb = ESP["pins"]; yp1 = YIN - (1.5 + FIT); yp0 = yp1 - ESP["L"]
    esp = U([B(ex0w, ex1w, yp0, yp1, zb, zb + ESP["T"]), B(ex0w + 4, ex1w - 4, yp0 + 6, yp0 + 38, zb + ESP["T"], zb + ESP["T"] + 4.5), B(ESP_XC - 4.5, ESP_XC + 4.5, yp1 - 6, yp1 + 1.6, zb + ESP["T"], zb + ESP["T"] + 3.0)])
    zf = FLAME["post"]; fy0, fy1 = YC - FLAME["W"] / 2, YC + FLAME["W"] / 2
    fl = U([B(fx0, fx1, fy0, fy1, zf, zf + FLAME["T"]), Cz(XH, YC, zf + FLAME["T"], HS + FLAME["poke"], 2.5)])
    ov = lambda a, b: trimesh.boolean.intersection([a, b], engine="manifold").volume
    rep["fit_check_mm3"] = dict(shell_vs_base=round(ov(sh, bs), 2), esp_vs_shell=round(ov(esp, sh), 2), flame_vs_shell=round(ov(fl, sh), 2), esp_vs_base=round(ov(esp, bs), 2), flame_vs_base=round(ov(fl, bs), 2))
    tot = trimesh.util.concatenate([sh, bs]); rep["assembled_mm"] = [round(x, 1) for x in tot.extents]; rep["layout"] = info
    (OUT / "report.json").write_text(json.dumps(rep, indent=1)); print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
