"""Fully coloured STEP of the assembled field node (millimetres, standing upright, front towards -Y).
    python export_step.py   ->  stl/field_node_full_assembly_colour.step
Needs: pip install cadquery-ocp trimesh. Run make_field_node.py and make_components.py first.
Parts are faceted B-reps built from the STL meshes (coplanar faces merged); the USB leads are true swept tubes.
Every part is a named, coloured product in the assembly tree."""
import json, sys
from pathlib import Path

import numpy as np
import trimesh
from OCP.BRep import BRep_Builder
from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeSolid,
                                BRepBuilderAPI_MakeWire, BRepBuilderAPI_Sewing)
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.ShapeFix import ShapeFix_Shape
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipe
from OCP.Geom import Geom_BSplineCurve
from OCP.GeomAPI import GeomAPI_Interpolate
from OCP.IFSelect import IFSelect_RetDone
from OCP.Quantity import Quantity_Color, Quantity_TOC_sRGB
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_AsIs
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCP.TCollection import TCollection_ExtendedString
from OCP.collections import HArray1_gp_Pnt as TColgp_HArray1OfPnt
from OCP.TDataStd import TDataStd_Name
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_SHELL
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Compound
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import XCAFDoc_ColorGen, XCAFDoc_DocumentTool
from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt, gp_Vec

HERE = Path(__file__).parent; STL = HERE / "stl"
# x (up the trunk) -> Z up, z (away from the tree) -> -Y (front view looks at the camera side), y -> -X; bottom end on Z = 0
UP = np.array([[0, -1, 0, 0], [0, 0, -1, 0], [1, 0, 0, 2.6], [0, 0, 0, 1.0]])


def solid_from_mesh(m):
    m = m.copy(); m.apply_transform(UP); sew = BRepBuilderAPI_Sewing(1e-3)
    for f in m.faces:
        a, b, c = (gp_Pnt(*map(float, m.vertices[i])) for i in f)
        poly = BRepBuilderAPI_MakePolygon(a, b, c, True)
        if not poly.IsDone(): continue
        try: sew.Add(BRepBuilderAPI_MakeFace(poly.Wire(), True).Face())
        except Exception: pass
    sew.Perform(); shp = sew.SewedShape()
    if shp.ShapeType() == TopAbs_SHELL: shp = TopoDS.Shell_s(shp) if hasattr(TopoDS, "Shell_s") else TopoDS.Shell(shp)
    exp = TopExp_Explorer(shp, TopAbs_SHELL)
    if exp.More():
        try: shp = BRepBuilderAPI_MakeSolid(TopoDS.Shell_s(exp.Current()) if hasattr(TopoDS, "Shell_s") else TopoDS.Shell(exp.Current())).Solid()
        except Exception as e: print("  (kept as shell:", e, ")")
    uni = ShapeUpgrade_UnifySameDomain(shp, True, True, True); uni.Build(); shp = uni.Shape()
    if not BRepCheck_Analyzer(shp).IsValid():
        fx = ShapeFix_Shape(shp); fx.Perform(); shp = fx.Shape(); print("  repaired:", BRepCheck_Analyzer(shp).IsValid())
    return shp


def tube_from_points(pts, r):
    P = (UP @ np.c_[pts, np.ones(len(pts))].T).T[:, :3]
    keep = [0]
    for i in range(1, len(P)):
        if np.linalg.norm(P[i] - P[keep[-1]]) > 4.0: keep.append(i)
    P = P[keep]
    arr = TColgp_HArray1OfPnt(1, len(P))
    for i, p in enumerate(P): arr.SetValue(i + 1, gp_Pnt(*map(float, p)))
    ip = GeomAPI_Interpolate(arr, False, 1e-3); ip.Perform(); curve = ip.Curve()
    spine = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(curve).Edge()).Wire()
    t = P[1] - P[0]; t = t / np.linalg.norm(t)
    prof = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(*map(float, P[0])), gp_Dir(*map(float, t))), r)).Edge()).Wire()
    return BRepOffsetAPI_MakePipe(spine, prof).Shape()


def rgb(h): h = h.lstrip("#"); return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def main():
    sys.path.insert(0, str(HERE))
    man = json.loads((STL / "components" / "manifest.json").read_text())
    items = [("casing_shell", STL / "field_node_shell.stl", "#eef2f9"), ("casing_base", STL / "field_node_base.stl", "#2563eb")]
    items += [(n, STL / "components" / f"{n}.stl", m["color"]) for n, m in man.items() if n not in ("esp_usb_cable", "cam_usb_cable")]
    app = XCAFApp_Application.GetApplication_s(); doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF")); app.NewDocument(TCollection_ExtendedString("MDTV-XCAF"), doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main()); ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    def add(name, shape, color):
        lab = st.AddShape(shape, False); TDataStd_Name.Set_s(lab, TCollection_ExtendedString(name)); r, g, b = rgb(color)
        ct.SetColor(lab, Quantity_Color(r, g, b, Quantity_TOC_sRGB), XCAFDoc_ColorGen); print("added", name, flush=True)
    for name, f, color in items: add(name, solid_from_mesh(trimesh.load(f)), color)
    cables = json.loads((STL / "components" / "cable_paths.json").read_text())
    for name, c in cables.items(): add(name, tube_from_points(np.array(c["points"]), c["radius"]), man[name]["color"])
    w = STEPCAFControl_Writer(); w.SetColorMode(True); w.SetNameMode(True); w.Transfer(doc, STEPControl_AsIs)
    out = STL / "field_node_full_assembly_colour.step"
    assert w.Write(str(out)) == IFSelect_RetDone; print("wrote", out, round(out.stat().st_size / 1e6, 1), "MB")


if __name__ == "__main__":
    main()
