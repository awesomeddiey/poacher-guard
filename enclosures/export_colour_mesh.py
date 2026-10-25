"""Coloured mesh exports that CAD programs understand, standing upright, millimetres.
    python export_colour_mesh.py -> stl/field_node_full_assembly_colour.stl  (binary STL, per-facet colour in the attribute bytes, VisCAM/SolidView convention)
                                    stl/field_node_full_assembly_colour.3mf  (3MF with one named, coloured object per part)
Run make_field_node.py and make_components.py first."""
import json, struct, zipfile
from pathlib import Path
from xml.sax.saxutils import quoteattr

import numpy as np
import trimesh

HERE = Path(__file__).parent; STL = HERE / "stl"
UP = np.array([[0, -1, 0, 0], [0, 0, -1, 0], [1, 0, 0, 2.6], [0, 0, 0, 1.0]])      # same pose as the STEP file: x up, front towards -Y, bottom end on Z = 0


def parts():
    man = json.loads((STL / "components" / "manifest.json").read_text())
    items = [("casing_shell", STL / "field_node_shell.stl", "#eef2f9"), ("casing_base", STL / "field_node_base.stl", "#2563eb")]
    items += [(n, STL / "components" / f"{n}.stl", m["color"]) for n, m in man.items()]
    out = []
    for n, f, c in items:
        m = trimesh.load(f, process=True); m.apply_transform(UP); out.append((n, m, c))
    return out


def rgb(h): h = h.lstrip("#"); return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def write_stl(ps, path):
    tris = []
    for _, m, c in ps:
        r, g, b = (v >> 3 for v in rgb(c)); attr = 0x8000 | (r << 10) | (g << 5) | b      # bit 15 = colour valid, then 5 bits each: R (10-14), G (5-9), B (0-4)
        v = m.vertices[m.faces]; n = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0]); n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        tris.append((n.astype("<f4"), v.astype("<f4"), np.full(len(m.faces), attr, "<u2")))
    N = sum(len(t[2]) for t in tris)
    rec = np.zeros(N, dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    i = 0
    for n, v, a in tris: k = len(a); rec["n"][i:i + k] = n; rec["v"][i:i + k] = v; rec["a"][i:i + k] = a; i += k
    with open(path, "wb") as f: f.write(b"Poacher Guard field node, coloured (VisCAM attribute colours)".ljust(80, b" ")); f.write(struct.pack("<I", N)); f.write(rec.tobytes())
    return N


def write_3mf(ps, path):
    cols = sorted({c for _, _, c in ps}); cid = {c: i for i, c in enumerate(cols)}
    x = ['<?xml version="1.0" encoding="UTF-8"?>', '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">', " <resources>",
         '  <basematerials id="1">'] + [f'   <base name="c{i}" displayColor="{c.upper()}FF"/>' for i, c in enumerate(cols)] + ["  </basematerials>"]
    for k, (n, m, c) in enumerate(ps):
        oid = k + 2
        x.append(f'  <object id="{oid}" name={quoteattr(n)} type="model" pid="1" pindex="{cid[c]}"><mesh><vertices>')
        x += [f'<vertex x="{a:.4f}" y="{b:.4f}" z="{d:.4f}"/>' for a, b, d in m.vertices]; x.append("</vertices><triangles>")
        x += [f'<triangle v1="{a}" v2="{b}" v3="{d}"/>' for a, b, d in m.faces]; x.append("</triangles></mesh></object>")
    x += [" </resources>", " <build>"] + [f'  <item objectid="{k + 2}"/>' for k in range(len(ps))] + [" </build>", "</model>"]
    ct = '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>'
    rels = '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>'
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z: z.writestr("[Content_Types].xml", ct); z.writestr("_rels/.rels", rels); z.writestr("3D/3dmodel.model", "\n".join(x))


if __name__ == "__main__":
    ps = parts(); n = write_stl(ps, STL / "field_node_full_assembly_colour.stl"); write_3mf(ps, STL / "field_node_full_assembly_colour.3mf")
    print("coloured STL:", n, "triangles;", len({c for _, _, c in ps}), "colours; 3MF written")
