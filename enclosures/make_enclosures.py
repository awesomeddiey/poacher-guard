"""Parametric 3D-printable cases for Poacher Guard (millimetres).

    python make_enclosures.py          # writes stl/*.stl and previews/*.png

Two cases, each a base and a lid:
  flame_node   weatherproof box for an ESP32 DevKit (30-pin) and a 4-pin flame sensor module, with a sensor window
               and sun hood, a USB cable slot, screw lid with a rain skirt, and two wall-mount ears.
  ranger_tag   small wearable box for an ESP32-C3 SuperMini, a TP4056 charger and a 502030 LiPo cell, with USB-C
               cut-outs, lanyard ears and a screw lid.
Edit the numbers in the PARAMETERS block to match your own boards (measure them with callipers), then re-run.
"""
from pathlib import Path

import numpy as np
import trimesh
from trimesh.creation import box, cylinder

OUT = Path(__file__).parent
(OUT / "stl").mkdir(exist_ok=True); (OUT / "previews").mkdir(exist_ok=True)

# ----------------------------------------------------------------- PARAMETERS
WALL, FLOOR, LID_T = 2.4, 2.4, 2.4          # wall, floor and lid-plate thickness
FIT = 0.5                                   # clearance around parts that must fit together
SCREW_PILOT, SCREW_CLEAR = 2.6, 3.4         # M3 self-tapping screw: hole in boss / hole in lid
SKIRT_T, SKIRT_H = 1.6, 6.0                 # lid rain skirt
ESP = dict(L=51.5, W=28.5, T=1.6, pin_clear=10.0, comp_h=5.0)           # ESP32 DevKit V1, pins down
FLAME = dict(L=32.0, W=14.0, T=1.6, post=6.0, sensor_z=4.0, hole=10.0)  # 4-pin flame module, sensor facing front
C3 = dict(L=22.5, W=18.0, T=1.2, comp_h=4.0)                            # ESP32-C3 SuperMini
TP = dict(L=26.0, W=17.0, T=1.2, comp_h=4.5)                            # TP4056 charger board
LIPO = dict(L=30.0, W=20.0, T=5.2)                                      # 502030 LiPo
# ---------------------------------------------------------------------------


def B(x0, x1, y0, y1, z0, z1):
    return box(extents=[x1 - x0, y1 - y0, z1 - z0], transform=trimesh.transformations.translation_matrix([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2]))


def Cz(x, y, z0, z1, r, n=48):      # cylinder along z
    return cylinder(radius=r, height=z1 - z0, sections=n, transform=trimesh.transformations.translation_matrix([x, y, (z0 + z1) / 2]))


def Cy(x, y0, y1, z, r, n=48):      # cylinder along y
    m = trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])
    m[:3, 3] = [x, (y0 + y1) / 2, z]
    return cylinder(radius=r, height=y1 - y0, sections=n, transform=m)


def union(parts): return trimesh.boolean.union(parts, engine="manifold")
def diff(a, parts): return trimesh.boolean.difference([a] + parts, engine="manifold")


def case(Xin, Yin, Zin, boss_xy, feature_fn, ears=True, ear_hole=5.0, ear_len=14.0):
    """Base: floor + walls + screw bosses at boss_xy (inside the cavity) + features. Cavity origin is (0,0,0) at the inner floor corner."""
    Xo, Yo = Xin + 2 * WALL, Yin + 2 * WALL
    outer = B(-WALL, Xin + WALL, -WALL, Yin + WALL, -FLOOR, Zin)
    cav = B(0, Xin, 0, Yin, 0, Zin + 1)
    bosses = [Cz(x, y, 0, Zin, 3.6) for x, y in boss_xy]
    pilots = [Cz(x, y, Zin - 12, Zin + 0.1, SCREW_PILOT / 2, 24) for x, y in boss_xy]
    base = diff(union([diff(outer, [cav])] + bosses), pilots)
    if ears:
        e = []
        for s in (-1, 1):
            x0 = -WALL - ear_len if s < 0 else Xin + WALL
            tab = B(x0, x0 + ear_len, Yin / 2 - 7, Yin / 2 + 7, -FLOOR, 0.0)
            hole = Cz(x0 + ear_len / 2 + (-1 if s < 0 else 1) * 0.5, Yin / 2, -FLOOR - 1, 1, ear_hole / 2)
            e.append(diff(tab, [hole]))
        base = union([base] + e)
    base = feature_fn(base)
    # lid: plate + rain skirt around the outside of the walls + screw holes with countersink
    ox0, ox1, oy0, oy1 = -WALL - FIT, Xin + WALL + FIT, -WALL - FIT, Yin + WALL + FIT
    plate = B(ox0 - SKIRT_T, ox1 + SKIRT_T, oy0 - SKIRT_T, oy1 + SKIRT_T, 0, LID_T)
    skirt = diff(B(ox0 - SKIRT_T, ox1 + SKIRT_T, oy0 - SKIRT_T, oy1 + SKIRT_T, -SKIRT_H, 0), [B(ox0, ox1, oy0, oy1, -SKIRT_H - 1, 1)])
    holes = [Cz(x, y, -1, LID_T + 1, SCREW_CLEAR / 2, 24) for x, y in boss_xy]
    csk = [trimesh.creation.cone(radius=3.3, height=1.8, sections=24, transform=trimesh.transformations.translation_matrix([x, y, LID_T - 1.8])) for x, y in boss_xy]
    lid = diff(union([plate, skirt]), holes + csk)
    return base, lid


# ------------------------------------------------------------------ FLAME NODE
def flame_node():
    Xin = 4.5 + ESP["W"] + 4.0 + FLAME["W"] + 4.0 + 3.5          # left boss gap + ESP + gap + module + gap + right boss gap
    Yin = ESP["L"] + 2 * FIT + 6.0
    Zin = ESP["pin_clear"] + ESP["T"] + ESP["comp_h"] + 5.5
    esp_x0 = 4.5 + FIT; esp_x1 = esp_x0 + ESP["W"]
    fl_x0 = esp_x1 + 4.0; fl_x1 = fl_x0 + FLAME["W"]
    bosses = [(1.0, Yin * 0.25), (1.0, Yin * 0.75), (Xin - 1.0, Yin * 0.25), (Xin - 1.0, Yin * 0.75)]

    def feats(base):
        add = []
        # ESP32 corner blocks: pcb rests on 4 blocks, side-located by their inner faces; USB end at back wall (y = 0)
        y0 = 1.5; y1 = y0 + ESP["L"] + 2 * FIT
        for (xa, xb) in ((esp_x0 - 3, esp_x0 - FIT / 2 + 0.0), (esp_x1 + FIT / 2, esp_x1 + 3)):
            for (ya, yb) in ((y0 - 0.0, y0 + 5), (y1 - 5, y1 + 0.0)):
                add.append(B(xa, xb, ya, yb, 0, ESP["pin_clear"]))
        # flame module posts: one with screw pilot (module hole), one rib at the sensor end
        sy_front = Yin - 2.0
        post_z = FLAME["post"]; mod_y0 = sy_front - FLAME["L"]
        add.append(Cz(fl_x0 + 2.5, mod_y0 + 3.0, 0, post_z, 3.6)); add.append(B(fl_x0, fl_x1, sy_front - 6, sy_front - 3, 0, post_z))
        # hood tube on the front wall, outside
        zc = post_z + FLAME["T"] + FLAME["sensor_z"]; xc = (fl_x0 + fl_x1) / 2
        add.append(Cy(xc, Yin + WALL - 0.1, Yin + WALL + 9.0, zc, FLAME["hole"] / 2 + 3.0))
        base = union([base] + add)
        cuts = [Cy(xc, Yin - 1, Yin + WALL + 10, zc, FLAME["hole"] / 2)]                                                     # sensor window through wall and hood
        cuts.append(B(fl_x0 - 0.1, fl_x0 + 0, 0, 0, 0, 0)) if False else None
        zusb = ESP["pin_clear"] + ESP["T"] + 1.6
        cuts.append(B((esp_x0 + esp_x1) / 2 - 7, (esp_x0 + esp_x1) / 2 + 7, -WALL - 1, 1, zusb - 4.5, zusb + 4.5))            # USB cable slot in back wall
        pilot_cut = Cz(fl_x0 + 2.5, mod_y0 + 3.0, post_z - 8, post_z + 0.1, SCREW_PILOT / 2 - 0.3, 24)
        base = diff(base, [c for c in cuts if c is not None] + [pilot_cut])
        return base

    b, l = case(Xin, Yin, Zin, bosses, feats)
    # lid pressure ribs over the ESP32 board edges
    rib_h = Zin - (ESP["pin_clear"] + ESP["T"]) - 0.4
    ribs = [B(esp_x0 + 0.3, esp_x0 + 2.3, Yin / 2 - 8, Yin / 2 + 8, -rib_h, 0.0), B(esp_x1 - 2.3, esp_x1 - 0.3, Yin / 2 - 8, Yin / 2 + 8, -rib_h, 0.0)]
    l = union([l] + ribs)
    info = dict(inner=(round(Xin, 1), round(Yin, 1), round(Zin, 1)), esp_pocket=(round(esp_x0, 1), round(esp_x1, 1)), flame_x=(round(fl_x0, 1), round(fl_x1, 1)))
    return b, l, info


# ------------------------------------------------------------------ RANGER TAG
def ranger_tag():
    """Battery lies on the floor and is installed first. The two boards then bridge over it: each rests on one end block and
    on the battery top (fix with double-sided foam tape). Nothing is sealed in, so every part can be fitted from above."""
    Xin = 4.0 + C3["L"] + 3.0 + TP["L"] + 3.0 + 3.5
    Yin = max(C3["W"], TP["W"], LIPO["W"]) + 4.0
    z_batt = LIPO["T"] + 0.6                                   # top of the battery = underside of both boards
    Zin = z_batt + max(C3["comp_h"] + C3["T"], TP["comp_h"] + TP["T"]) + 2.5
    bosses = [(1.0, 1.0), (1.0, Yin - 1.0), (Xin - 1.0, 1.0), (Xin - 1.0, Yin - 1.0)]
    c3_x0 = 4.0; tp_x0 = c3_x0 + C3["L"] + 3.0; tp_x1 = tp_x0 + TP["L"]

    def feats(base):
        blocks = [B(c3_x0 - 1.5, c3_x0 + 3.0, Yin / 2 - 7, Yin / 2 + 7, 0, z_batt),            # supports the free end of the ESP32-C3
                  B(tp_x1 - 3.0, tp_x1 + 1.5, Yin / 2 - 7, Yin / 2 + 7, 0, z_batt)]            # supports the free end of the TP4056
        guides = [B(c3_x0 - 1.5, c3_x0 - 0.2, Yin / 2 - 7, Yin / 2 + 7, z_batt, z_batt + 2.0),   # lips that locate the board ends
                  B(tp_x1 + 0.2, tp_x1 + 1.5, Yin / 2 - 7, Yin / 2 + 7, z_batt, z_batt + 2.0)]
        base = union([base] + blocks + guides)
        zb = z_batt + 0.2
        cuts = [B(-WALL - 1, 1, Yin / 2 - 5, Yin / 2 + 5, zb, zb + 5.0),                 # USB-C of the ESP32-C3 (left wall)
                B(Xin - 1, Xin + WALL + 1, Yin / 2 - 5, Yin / 2 + 5, zb, zb + 5.0)]      # USB of the TP4056 (right wall)
        return diff(base, cuts)
    b, l = case(Xin, Yin, Zin, bosses, feats, ears=True, ear_hole=4.5, ear_len=10.0)
    return b, l, dict(inner=(round(Xin, 1), round(Yin, 1), round(Zin, 1)))


# -------------------------------------------------------------- checks + render
def preview(meshes, name, explode=0.0):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    fig = plt.figure(figsize=(7.2, 5.4)); ax = fig.add_subplot(111, projection="3d"); allv = []
    for k, (m, col) in enumerate(meshes):
        m = m.copy(); m.apply_translation([0, 0, k * explode]); allv.append(m.vertices)
        tri = m.triangles; n = m.face_normals; light = np.array([0.4, -0.6, 0.7]); light /= np.linalg.norm(light)
        sh = 0.45 + 0.55 * np.clip(n @ light, 0, 1); c = np.array(plt.matplotlib.colors.to_rgb(col))[None] * sh[:, None]
        pc = Poly3DCollection(tri, facecolors=c, edgecolors="none", linewidths=0); ax.add_collection3d(pc)
    v = np.concatenate(allv); mn, mx = v.min(0), v.max(0); c = (mn + mx) / 2; r = (mx - mn).max() / 2
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r); ax.set_box_aspect((1, 1, 1)); ax.view_init(28, -55); ax.set_axis_off()
    fig.tight_layout(); fig.savefig(OUT / "previews" / f"{name}.png", dpi=170); plt.close(fig)


def main():
    report = {}
    for name, fn in (("flame_node", flame_node), ("ranger_tag", ranger_tag)):
        base, lid, info = fn()
        for part, m in (("base", base), ("lid", lid)):
            m.export(OUT / "stl" / f"{name}_{part}.stl")
            report[f"{name}_{part}"] = dict(watertight=bool(m.is_watertight), size_mm=[round(x, 1) for x in m.extents], volume_cm3=round(m.volume / 1000, 1), **({"inner_mm": info["inner"]} if part == "base" else {}))
        lid_up = lid.copy(); lid_up.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0]))   # lid printed top-down
        preview([(base, "#2563eb"), (lid, "#93c5fd")], f"{name}_assembly", explode=14)
        preview([(base, "#2563eb")], f"{name}_base"); preview([(lid, "#93c5fd")], f"{name}_lid")
        lid.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0])); lid.apply_translation([0, 0, -lid.bounds[0][2]]); lid.export(OUT / "stl" / f"{name}_lid_print_orientation.stl")
    import json; (OUT / "report.json").write_text(json.dumps(report, indent=1)); print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
