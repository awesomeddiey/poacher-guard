"""Orthographic drawings with dimensions, generated from the same model that is printed (millimetres).  python make_drawings.py
Writes docs/chapter3/figures/fig_enclosure_ortho_1.png (front and left views) and fig_enclosure_ortho_2.png (top-end and back views)."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle
from shapely.geometry import Polygon
from shapely.ops import unary_union

import make_field_node as C

HERE = Path(__file__).parent; OUTD = HERE.parent / "docs" / "chapter3" / "figures"
INK, DIM, FILL, CAM = "#111827", "#1d4ed8", "#ffffff", "#e5e7eb"
XB = C.XO0                                     # bottom end face (x of the flat bottom)
sh = trimesh.load(HERE / "stl" / "field_node_shell.stl"); bs = trimesh.load(HERE / "stl" / "field_node_base.stl")
cam = trimesh.util.concatenate([trimesh.load(HERE / "stl" / "components" / f"webcam_{k}.stl") for k in ("base", "neck", "head", "lens_ring", "lens")])
body = trimesh.util.concatenate([sh, bs])


def silhouette(mesh, proj):
    """Union of the projected triangles; proj maps (N,3) world points to (N,2) drawing coordinates."""
    P = proj(mesh.vertices); polys = []
    for f in mesh.faces:
        t = P[f]
        a, b = t[1] - t[0], t[2] - t[0]
        if abs(a[0] * b[1] - a[1] * b[0]) > 1e-6: polys.append(Polygon(t).buffer(0.02))
    return unary_union(polys)


def draw_poly(ax, geom, fc=FILL, lw=1.1, z=2):
    for g in (geom.geoms if hasattr(geom, "geoms") else [geom]):
        ax.fill(*g.exterior.xy, fc=fc, ec=INK, lw=lw, zorder=z)
        for h in g.interiors: ax.fill(*h.xy, fc="white", ec=INK, lw=lw * 0.8, zorder=z + 0.1)


def dim(ax, p0, p1, off, txt, side=1, fs=8, rot=None):
    """Dimension line between p0 and p1 drawn at distance off from them (perpendicular), with extension lines and arrowheads."""
    p0, p1 = np.array(p0, float), np.array(p1, float); d = p1 - p0; L = np.linalg.norm(d); u = d / L; n = np.array([-u[1], u[0]]) * side
    a, b = p0 + n * off, p1 + n * off
    for p, q in ((p0, a), (p1, b)): ax.plot(*zip(p + n * 1.2, q + n * 1.5), color=DIM, lw=0.5, zorder=1)
    ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="<|-|>", color=DIM, lw=0.7, mutation_scale=6, shrinkA=0, shrinkB=0), zorder=5)
    m = (a + b) / 2 + n * 1.8; ang = np.degrees(np.arctan2(u[1], u[0])); ang = ang if abs(ang) <= 90 else ang + 180
    ax.text(*m, txt, color=DIM, fontsize=fs, ha="center", va="bottom" if rot is None else "center", rotation=rot if rot is not None else (ang if abs(ang) > 1 else 0), rotation_mode="anchor", zorder=6, bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.9))


def label(ax, xy, txt, xytext, fs=8):
    ax.annotate(txt, xy=xy, xytext=xytext, fontsize=fs, color=INK, ha="center", va="center", arrowprops=dict(arrowstyle="-", color=INK, lw=0.5), zorder=6, bbox=dict(fc="white", ec="none", pad=0.8))


def setup(ax, title, xl, yl):
    ax.set_aspect("equal"); ax.set_xlim(*xl); ax.set_ylim(*yl); ax.axis("off"); ax.set_title(title, fontsize=9.5, fontweight="bold", color=INK, pad=4)


# ---- projections: drawing coordinates (u, v), all in mm -------------------------------------------------------------
Y_R, Y_L = C.YO1, C.YO0
front = lambda V: np.c_[Y_R - V[:, 1], V[:, 0] - XB]                  # seen from the weather side (+z): left of the picture = right wall (USB port side); v = height above the bottom end
leftv = lambda V: np.c_[V[:, 2] + C.PLATE, V[:, 0] - XB]              # seen from the USB port wall (+y): front (+z) on the right
topv = lambda V: np.c_[Y_R - V[:, 1], -(V[:, 2] - C.HS)]              # seen from the top end (+x): front (+z) at the bottom
backv = lambda V: np.c_[V[:, 1] - Y_L, V[:, 0] - XB]                  # seen from the tree side (-z)
H, W, D = C.OUT_X, C.OUT_Y, C.OUT_Z                                   # 150 x 100 x 45
HC = float(np.asarray(front(cam.vertices))[:, 1].max())               # height including the webcam stand-in
LUGW = W + 2 * C.LUG["out"]


def view_front(ax):
    setup(ax, "FRONT (weather side, +z)", (-C.LUG["out"] - 38, W + C.LUG["out"] + 8), (-42, HC + 16))
    draw_poly(ax, silhouette(cam, front), fc=CAM, lw=0.8, z=1); draw_poly(ax, silhouette(body, front))
    hx = Y_R - (C.YC); hv = C.XH - XB
    ax.add_patch(Circle((W / 2, hv), C.SENSOR_HOLE_R, fc="white", ec=INK, lw=0.9, zorder=3)); ax.add_patch(Circle((W / 2, hv), C.SENSOR_HOLE_R + 1.8, fc="none", ec=INK, lw=0.6, ls="--", zorder=3))
    ax.add_patch(Circle((W / 2, hv), 2.5, fc=INK, ec=INK, zorder=4))
    label(ax, (W / 2 + 2, hv + 2), "IR sensor head Ø6.8 hole\n(Ø5 head pokes out 6)", (W / 2 + 30, hv + 22))
    dim(ax, (0, 0), (W, 0), 10, f"{W:.0f}", side=-1); dim(ax, (-C.LUG["out"], 0), (W + C.LUG["out"], 0), 21, f"{LUGW:.0f} over strap lugs", side=-1)
    dim(ax, (0, 0), (0, H), 14, f"{H:.0f}", side=1); dim(ax, (0, 0), (0, HC), 26, f"≈{HC:.0f} with webcam stand-in", side=1)
    dim(ax, (W / 2, 0), (W / 2, hv), 7, f"{hv:.1f}", side=-1)
    xs = [x - XB for x in C.LUG["xs"]]
    for xc in xs[:1]: dim(ax, (W, xc - C.LUG["L"] / 2), (W, xc + C.LUG["L"] / 2), 8 + C.LUG["out"], f"{C.LUG['L']:.0f}", side=-1)
    dim(ax, (W, 0), (W + C.LUG["out"], 0), 0, "", side=-1)
    ax.text(W + C.LUG["out"] / 2, xs[0] - 28, f"{C.LUG['out']:.0f}", color=DIM, fontsize=8, ha="center")
    ax.annotate("", xy=(W, xs[0] - 24), xytext=(W + C.LUG["out"], xs[0] - 24), arrowprops=dict(arrowstyle="<|-|>", color=DIM, lw=0.7, mutation_scale=6))
    ax.text(W / 2, -37, f"strap lug centres {xs[0]:.1f} and {xs[1]:.1f} from the bottom end; corner and roof-edge radius R{C.R:.0f}", fontsize=7.5, ha="center", color=INK)


def view_left(ax):
    setup(ax, "LEFT (USB port wall, +y)", (-12, D + 4 + 38), (-26, HC + 16))
    draw_poly(ax, silhouette(cam, leftv), fc=CAM, lw=0.8, z=1); draw_poly(ax, silhouette(body, leftv))
    pc = 20.0 - XB; z0 = C.PLATE + 8.0; z1 = C.PLATE + 17.0                                  # port: x centre ESP_XC, z 8..17, 22 x 9
    ax.add_patch(FancyBboxPatch((z0 + 2.25, pc - 11 + 2.25), 4.5, 17.5, boxstyle="round,pad=2.25,rounding_size=4.5", fc="white", ec=INK, lw=1.0, zorder=3))
    label(ax, (z1, pc), "USB port 22×9\n(ESP32 micro-USB)", (D + 24, pc + 20))
    dim(ax, (0, 0), (D, 0), 10, f"{D:.0f}", side=-1); dim(ax, (0, 0), (0, H), 8, f"{H:.0f}", side=1)
    dim(ax, (z1 + 5, 0), (z1 + 5, pc - 11), -3, f"{pc - 11:.1f}", side=1) if False else None
    dim(ax, (D, 0), (D, pc - 11), 8, f"{pc - 11:.1f}", side=1)
    dim(ax, (0, pc), (z0, pc), 0, "", side=1)
    ax.annotate("", xy=(0, pc - 17), xytext=(z0, pc - 17), arrowprops=dict(arrowstyle="<|-|>", color=DIM, lw=0.7, mutation_scale=6)); ax.text(z0 / 2, pc - 22, f"{z0:.1f}", color=DIM, fontsize=8, ha="center")
    ax.text(-4, H + 6, "back (tree)", fontsize=7.5, ha="left", color=INK); ax.text(D + 2, H + 6, "front", fontsize=7.5, ha="right", color=INK)


def view_top(ax):
    setup(ax, "TOP END (+x)", (-C.LUG["out"] - 8, W + C.LUG["out"] + 24), (-D - 38, 22))
    top = lambda V: np.c_[Y_R - V[:, 1], V[:, 2] - C.HS]                                       # front (+z) at the top of this view for readability
    draw_poly(ax, silhouette(body, top))
    pw, pd, pr = C.PAD; zc = C.PAD_CZ - C.HS
    ax.add_patch(Rectangle((W / 2 - pw / 2, zc - pd / 2), pw, pd, fc="white", ec=INK, lw=0.9, ls="--", zorder=3))
    for sx in (-1, 1):
        for sz in (-1, 1): ax.add_patch(Rectangle((W / 2 + sx * (pw / 2 - 3) - 1.6, zc + sz * (pd / 2 - 3) - 1.9), 3.2, 3.8, fc="white", ec=INK, lw=0.7, zorder=4))
    draw_poly(ax, silhouette(cam, top), fc=CAM, lw=0.6, z=3.5)
    label(ax, (W / 2 - pw / 2 + 2, zc - pd / 2 + 1), "camera deck 50×26, 0.8 deep\n4 tie slots 3.2×3.8\n(webcam stand-in shaded)", (W / 2, 14))
    dim(ax, (0, -D + C.HS - C.HS + (-C.PLATE - C.HS)), (W, -C.PLATE - C.HS), 0, "", side=1) if False else None
    ax.text(W / 2, -D - 33, "front (+z) at the top, tree side at the bottom", fontsize=7.5, ha="center", color=INK)
    dim(ax, (0, -D), (W, -D), 10, f"{W:.0f}", side=-1)
    dim(ax, (W, -D), (W, 0), 8 + C.LUG["out"], f"{D:.0f}", side=-1)
    dim(ax, (W / 2 + pw / 2, zc - pd / 2), (W / 2 + pw / 2, zc + pd / 2), 7, f"{pd:.0f}", side=-1)
    dim(ax, (W / 2 - pw / 2, zc - pd / 2), (W / 2 + pw / 2, zc - pd / 2), 5, f"{pw:.0f}", side=1)
    dim(ax, (W / 2 - pw / 2, zc + pd / 2), (W / 2 - pw / 2, 0), 6, f"{-(zc + pd / 2):.0f}", side=-1)
    dim(ax, (W / 2 - pw / 2 - 0.0, 0), (W / 2 - pw / 2, zc + pd / 2), 6 + 8, f"{-(zc + pd / 2):.0f}", side=1) if False else None


def view_back(ax):
    setup(ax, "BACK (tree side, -z)", (-C.LUG["out"] - 10, W + C.LUG["out"] + 10), (-26, H + 16))
    draw_poly(ax, silhouette(bs, backv))
    t = lambda x: x - XB
    for xc in C.LUG["xs"]:
        for side in (-1, 1):
            yw = (C.YO0 + side * (C.LUG["out"] - 6 - C.LUG["win_w"] / 2 - 1)) - Y_L if side < 0 else (C.YO1 + side * (C.LUG["out"] - 6 - C.LUG["win_w"] / 2 - 1)) - Y_L
            ax.add_patch(FancyBboxPatch((yw - C.LUG["win_w"] / 2 + 2.5, t(xc) - C.LUG["win_l"] / 2 + 2.5), 0.01, C.LUG["win_l"] - 5, boxstyle="round,pad=2.5,rounding_size=2.5", fc="white", ec=INK, lw=0.9, zorder=3))
    for (x, y) in C.BOSSES:
        ax.add_patch(Circle((y - Y_L, t(x)), 1.75, fc="white", ec=INK, lw=0.8, zorder=4)); ax.add_patch(Circle((y - Y_L, t(x)), 3.9, fc="none", ec=INK, lw=0.5, ls="--", zorder=4))
    for (x, y) in C.CORN: ax.add_patch(Circle((y - Y_L, t(x)), 5.2, fc="none", ec=INK, lw=0.7, ls="-.", zorder=4))
    bx = [t(C.BOSSES[0][0]), t(C.BOSSES[1][0])]; by = [C.BOSSES[0][1] - Y_L, C.BOSSES[2][1] - Y_L]
    dim(ax, (0, 0), (W, 0), 10, f"{W:.0f}", side=-1); dim(ax, (-C.LUG["out"], 0), (W + C.LUG["out"], 0), 21, f"{LUGW:.0f}", side=-1); dim(ax, (0, 0), (0, H), 26, f"{H:.0f}", side=1)
    dim(ax, (by[0], bx[0]), (by[1], bx[0]), 6, f"{by[1] - by[0]:.0f} (screw columns)", side=1)
    dim(ax, (by[1], bx[0]), (by[1], bx[1]), 12, f"{bx[1] - bx[0]:.1f}", side=-1)
    xl = t(C.LUG["xs"][0]); dim(ax, (W, xl - C.LUG["L"] / 2), (W, xl + C.LUG["L"] / 2), 8 + C.LUG["out"], f"{C.LUG['L']:.0f}", side=-1)
    ax.text(W / 2, H * 0.52, f"strap windows {C.LUG['win_l']:.0f}×{C.LUG['win_w']:.0f} (25 mm strap)\nlug thickness {C.LUG['T']:.0f}, plate {C.PLATE}", fontsize=7.5, ha="center", va="center", color=INK)
    label(ax, (by[0], bx[1]), "4× Ø3.5 screw hole\n(Ø7.8 countersink)", (W / 2 - 10, bx[1] + 25))
    label(ax, (C.CORN[0][1] - Y_L, t(C.CORN[0][0])), "4× Ø10.4 foot pocket", (W / 2 - 20, 14))


def sheet(views, name, size, rows, cols, ratios=None):
    fig, axs = plt.subplots(rows, cols, figsize=size, gridspec_kw=dict(width_ratios=ratios) if ratios else None); axs = np.atleast_1d(axs).ravel()
    for ax, v in zip(axs, views): v(ax)
    fig.suptitle("Poacher Guard field node, orthographic views (millimetres)", fontsize=10, fontweight="bold", y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.985)); OUTD.mkdir(parents=True, exist_ok=True); fig.savefig(OUTD / name, dpi=240, facecolor="white", bbox_inches="tight", pad_inches=0.08); plt.close(fig)


if __name__ == "__main__":
    sheet([view_front, view_left], "fig_enclosure_ortho_1.png", (7.4, 7.0), 1, 2, [1.85, 1.0])
    sheet([view_top, view_back], "fig_enclosure_ortho_2.png", (7.4, 5.4), 1, 2, [1.0, 1.0])
    print("drawings written to", OUTD)
