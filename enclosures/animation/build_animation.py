"""Builds assembly.html (one self-contained file: models, viewer, controls). python build_animation.py"""
import base64, json, subprocess
from pathlib import Path

HERE = Path(__file__).parent; STL = HERE.parent / "stl"
parts = {"base": dict(file=STL / "field_node_base.stl", color="#2563eb"), "shell": dict(file=STL / "field_node_shell.stl", color="#eef2f9"), "stand": dict(file=STL / "field_node_stand.stl", color="#93c5fd")}
man = json.loads((STL / "components" / "manifest.json").read_text())
for n, m in man.items(): parts[n] = dict(file=STL / "components" / f"{n}.stl", color=m["color"])
data = {n: dict(color=p["color"], b64=base64.b64encode(p["file"].read_bytes()).decode()) for n, p in parts.items()}
subprocess.run(["/tmp/claude-0/lit2/node_modules/.bin/esbuild", str(HERE / "anim.js"), "--bundle", "--minify", "--format=iife", f"--outfile={HERE / 'anim.bundle.js'}"], check=True, env={"NODE_PATH": "/tmp/claude-0/lit2/node_modules", "PATH": "/usr/bin:/bin:/opt/node22/bin"})
html = (HERE / "template.html").read_text().replace("/*PARTS*/null", json.dumps(data)).replace("/*BUNDLE*/", (HERE / "anim.bundle.js").read_text().replace("</script", "<\\/script"))
(HERE.parent / "assembly.html").write_text(html); print("assembly.html", round(len(html) / 1e6, 2), "MB,", len(data), "parts")
