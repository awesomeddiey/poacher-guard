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
WALL, PLATE, R, FIT = 2.6, 4.5, 7.0, 0.35        # wall, base plate, outer corner/edge radius, fit clearance
OUT_X, OUT_Y, OUT_Z = 150.0, 100.0, 45.0         # requested outer size of the casing (width, depth including the sun brow, height including the base plate)
BROW = 4.0                                       # how far the sun brow sticks out of the front wall
XIN, YIN, ZIN = OUT_X - 2 * WALL, OUT_Y - BROW - 2 * WALL, OUT_Z - PLATE - WALL   # inner cavity: 144.8 x 90.8 x 37.9
ESP = dict(L=51.5, W=28.5, T=1.6, pins=10.0)     # ESP32 DevKit V1: pins point down, board sits on 10 mm blocks
FLAME = dict(L=32.0, W=14.0, T=1.6, post=14.0, sensor_z=4.5, poke=6.0)   # post lifts the module; the IR sensor pokes "poke" mm out of the front wall
SENSOR_HOLE_R = 3.4                              # hole for the 5 mm IR sensor head
ESP_X0 = 12.0                                    # ESP32 left edge (rear left of the cavity, USB end at the rear wall)
CAM_PORT_W = 14.0
PAD = (52.0, 32.0, 0.8)                          # camera deck: width, depth, recess
WORDMARK = "POACHER GUARD"
# ---------------------------------------------------------------------------
HS = ZIN + WALL                                  # shell height above the opening plane (z = 0)
XO0, XO1, YO0, YO1 = -WALL, XIN + WALL, -WALL, YIN + WALL
ESP_CX = ESP_X0 + ESP["W"] / 2; FL_X0 = XIN / 2 - FLAME["W"] / 2; FL_CX = XIN / 2
CAM_HX = XIN / 2 + 12                            # where the webcam cable goes through the deck
CORN = [(XO0 + R, YO0 + R), (XO1 - R, YO0 + R), (XO0 + R, YO1 - R), (XO1 - R, YO1 - R)]


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
    m.apply_transform(np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1.0]]))      # text (u, v, depth) -> world (depth along x, u along y, v along z)
    return m


def shell():
    outer, inner = pebble(R, 0.0), pebble(R - WALL, -1.0)
    # sun brow: a smooth full-width overhang above the sensor slit
    xc = FL_CX                                                      # centre of the flame module
    ball = lambda x, y, z: icosphere(subdivisions=2, radius=3.2).apply_translation([x, y, z])
    xs = (XO0 + R, XO1 - R)
    vis = hull([ball(x, YO1 + BROW - 3.2, HS - 3.4) for x in xs] + [ball(x, YO1 - 7, HS - 3.4) for x in xs] + [ball(x, YO1 - 7, HS - 13) for x in xs])
    sh = D(U([outer, vis]), [inner])
    # round hole for the IR flame sensor head, which pokes out of the front wall (soft bevel on the outside), under the brow
    zs = FLAME["post"] + FLAME["T"] + FLAME["sensor_z"]
    sh = D(sh, [Cy(xc, YIN - 3, YO1 + 3, zs, SENSOR_HOLE_R), hull([Cy(xc, YO1 - 0.9, YO1 - 0.89, zs, SENSOR_HOLE_R + 1.6), Cy(xc, YO1 - 0.9 + 1.6, YO1 - 0.89 + 1.6, zs, SENSOR_HOLE_R)])])
    # rear ports: ESP32 USB (aligned with the board's micro-USB socket) and the webcam lead
    sh = D(sh, [stadium_y(ESP_CX, 12.5, 22.0, 9.0, YO0 - 1, 1.0), stadium_y(CAM_HX - 1, 12.6, CAM_PORT_W, 9.0, YO0 - 1, 1.0)])
    # vents on the left side: 11 vertical slots
    sh = D(sh, [B(XO0 - 1, 1.0, YIN / 2 + (i - 5) * 6.0 - 1.0, YIN / 2 + (i - 5) * 6.0 + 1.0, 6.0, 30.0) for i in range(11)])
    # camera deck: shallow recess, four zip-tie slots, cable hole
    cx, cy = XIN / 2, YIN / 2 - 3.0; pw, pd, pr = PAD   # deck sits centred over the flame sensor
    sh = D(sh, [B(cx - pw / 2, cx + pw / 2, cy - pd / 2, cy + pd / 2, HS - pr, HS + 1)])
    ties = [B(cx + sx * (pw / 2 - 3.0) - 1.6, cx + sx * (pw / 2 - 3.0) + 1.6, cy + sy * (pd / 2 - 3.0) - 1.9, cy + sy * (pd / 2 - 3.0) + 1.9, HS - WALL - 1, HS + 1) for sx in (-1, 1) for sy in (-1, 1)]   # 3.2 x 3.8 mm slots for 2.5 mm cable ties
    sh = D(sh, ties + [B(CAM_HX - 7, CAM_HX + 7, cy - pd / 2 - 5.2, cy - pd / 2 + 0.2, HS - WALL - 1, HS + 1)])
    # engraved wordmark on the right side
    wm = wordmark_mesh(); wm.apply_translation([XO1 - 0.6 + 0.0, YIN / 2, 20.0]); sh = D(sh, [wm])
    # screw bosses hanging from the roof, ending above the base ring
    bosses = [(0.4, YIN * 0.25), (0.4, YIN * 0.75), (XIN - 0.4, YIN * 0.25), (XIN - 0.4, YIN * 0.75)]
    ztop = HS - R - 0.3                                           # stop below the rounded roof edge so nothing shows outside
    sh = U([sh] + [Cz(x, y, 3.2, ztop, 2.5) for x, y in bosses]); sh = D(sh, [Cz(x, y, 3.2, ztop - 3, 1.3, 24) for x, y in bosses])
    return sh, bosses


def base(bosses):
    rr = lambda r, z0, z1: hull([Cz(x, y, z0, z1, r) for x, y in CORN])
    plate = rr(R, -PLATE, 0.0)
    ring = D(rr(R - WALL - FIT, 0.0, 3.0), [rr(R - WALL - FIT - 1.6, -1, 4.0)])                        # locating lip inside the shell
    esp_x0 = ESP_X0; esp_x1 = esp_x0 + ESP["W"]; fl_x0 = FL_X0; fl_x1 = fl_x0 + FLAME["W"]
    y0 = 1.5; y1 = y0 + ESP["L"] + 2 * FIT
    parts = [plate, ring]
    for xa, xb in ((esp_x0 - 3, esp_x0 - FIT / 2), (esp_x1 + FIT / 2, esp_x1 + 3)):
        for ya, yb in ((y0, y0 + 5), (y1 - 5, y1)): parts.append(B(xa, xb, ya, yb, 0, ESP["pins"]))
    sy = YIN - 2.0; my0 = sy - FLAME["L"]
    parts += [Cz(fl_x0 + 2.5, my0 + 3.0, 0, FLAME["post"], 3.6), B(fl_x0, fl_x1, sy - 6, sy - 3, 0, FLAME["post"])]
    tx, ty = XIN / 2 + 30.0, YIN / 2 - 8.0                                                                      # tripod boss
    parts.append(Cz(tx, ty, 0, 6.0, 6.2))
    b = U(parts)
    cuts = [Cz(x, y, -PLATE - 1, 3.4, 1.75, 24) for x, y in bosses]   # also pierces the locating lip                                    # screw holes
    cuts += [hull([Cz(x, y, -PLATE - 0.5, -PLATE - 0.49, 3.9, 32), Cz(x, y, -PLATE + 1.8, -PLATE + 1.81, 1.6, 32)]) for x, y in bosses]   # countersink: wide at the bottom face, seats a flat-head M3
    cuts += [Cz(tx, ty, -PLATE - 1, 6.0, 3.2, 40)]                                                     # 1/4-20 tripod hole (self-tapping, or press in a nut)
    cuts += [Cz(x, y, -PLATE - 0.01, -PLATE + 1.0, 5.2, 40) for x, y in CORN]                          # rubber-foot pockets
    cuts += [Cz(fl_x0 + 2.5, my0 + 3.0, FLAME["post"] - 8, FLAME["post"] + 0.1, 1.2, 20)]              # flame module screw pilot
    return D(b, cuts), dict(esp=(esp_x0, esp_x1), flame=(fl_x0, fl_x1), tripod=(round(tx, 1), ty))


def main():
    sh, bosses = shell(); bs, info = base(bosses)
    sh.export(OUT / "stl" / "field_node_shell.stl"); bs.export(OUT / "stl" / "field_node_base.stl")
    sp = sh.copy(); sp.apply_transform(rot(np.pi, [1, 0, 0])); sp.apply_translation([0, 0, -sp.bounds[0][2]]); sp.export(OUT / "stl" / "field_node_shell_print_orientation.stl")
    rep = {}
    for n, m in (("shell", sh), ("base", bs)): rep[n] = dict(watertight=bool(m.is_watertight), size_mm=[round(x, 1) for x in m.extents], volume_cm3=round(m.volume / 1000, 1))
    # fit check: dummy ESP32 and flame module placed as designed must not touch the shell, and shell and base must not overlap
    ex0, ex1 = info["esp"]; fx0, fx1 = info["flame"]; y0 = 1.5 + FIT; zb = ESP["pins"]
    esp = U([B(ex0, ex1, y0, y0 + ESP["L"], zb, zb + ESP["T"]), B(ex0 + 4, ex1 - 4, y0 + 8, y0 + 40, zb + ESP["T"], zb + ESP["T"] + 4.5), B(ex0 + 9, ex1 - 9, y0 - 1.5, y0 + 6, zb + ESP["T"], zb + ESP["T"] + 3.0)])
    sy = YIN - 2.0; zf = FLAME["post"]
    fl = U([B(fx0, fx1, sy - FLAME["L"], sy, zf, zf + FLAME["T"]), Cy((fx0 + fx1) / 2, sy - 4, YO1 + FLAME["poke"], zf + FLAME["T"] + FLAME["sensor_z"], 2.5)])
    ov = lambda a, b: trimesh.boolean.intersection([a, b], engine="manifold").volume
    rep["fit_check_mm3"] = dict(shell_vs_base=round(ov(sh, bs), 2), esp_vs_shell=round(ov(esp, sh), 2), flame_vs_shell=round(ov(fl, sh), 2), esp_vs_base=round(ov(esp, bs), 2), flame_vs_base=round(ov(fl, bs), 2))
    tot = trimesh.util.concatenate([sh, bs]); rep["assembled_mm"] = [round(x, 1) for x in tot.extents]; rep["layout"] = info
    (OUT / "report.json").write_text(json.dumps(rep, indent=1)); print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
