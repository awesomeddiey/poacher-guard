// Renders STL files to PNG with three.js in headless Chromium.  node render_previews.js
const { chromium } = require("playwright"); const http = require("http"), fs = require("fs"), path = require("path");
const THREE = process.env.THREE_DIR || "/tmp/claude-0/three/package"; const ROOT = __dirname;
const srv = http.createServer((q, r) => { const u = decodeURIComponent(q.url.split("?")[0]); const f = u.startsWith("/three/") ? path.join(THREE, u.slice(7)) : path.join(ROOT, u);
  fs.readFile(f, (e, d) => { if (e) { r.writeHead(404); r.end(); } else { r.writeHead(200, { "Content-Type": f.endsWith(".js") ? "text/javascript" : f.endsWith(".stl") ? "application/octet-stream" : "text/html" }); r.end(d); } }); }).listen(8765);
const page = `<!doctype html><body style="margin:0;background:#fff"><canvas id=c width=1100 height=800></canvas>
<script type="importmap">{"imports":{"three":"/three/build/three.module.js","three/addons/":"/three/examples/jsm/"}}</script>
<script type="module">
import * as T from "three"; import { STLLoader } from "three/addons/loaders/STLLoader.js";
const r = new T.WebGLRenderer({ canvas: document.getElementById("c"), antialias: true, preserveDrawingBuffer: true }); r.setClearColor(0xffffff);
window.show = async (files, colors, az, el, explode) => {
  const s = new T.Scene(); const L = new STLLoader(); const g = new T.Group(); let k = 0;
  for (const [i, f] of files.entries()) { const geo = await L.loadAsync("/stl/" + f); geo.computeVertexNormals();
    const m = new T.Mesh(geo, new T.MeshStandardMaterial({ color: colors[i], roughness: .55, metalness: .05 })); m.position.z = i * explode; g.add(m); }
  s.add(g); const box = new T.Box3().setFromObject(g); const c = box.getCenter(new T.Vector3()); const sz = box.getSize(new T.Vector3()).length();
  s.add(new T.HemisphereLight(0xffffff, 0x8899bb, 1.1)); const d = new T.DirectionalLight(0xffffff, 2.2); d.position.set(60, -80, 120); s.add(d);
  const cam = new T.PerspectiveCamera(30, 1100 / 800, 1, 2000); const a = az * Math.PI / 180, e = el * Math.PI / 180;
  cam.up.set(0, 0, 1); cam.position.set(c.x + sz * 1.6 * Math.cos(e) * Math.sin(a), c.y - sz * 1.6 * Math.cos(e) * Math.cos(a), c.z + sz * 1.6 * Math.sin(e)); cam.lookAt(c);
  r.render(s, cam); return true; };
</script></body>`;
fs.writeFileSync(path.join(ROOT, "_view.html"), page);
(async () => {
  const b = await chromium.launch({ args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] }); const p = await b.newPage({ viewport: { width: 1100, height: 800 } });
  p.on("pageerror", e => console.log("pageerror", e.message)); await p.goto("http://localhost:8765/_view.html"); await p.waitForTimeout(800);
  const jobs = [];
  for (const n of ["flame_node", "ranger_tag"]) {
    jobs.push([`${n}_assembly`, [`${n}_base.stl`, `${n}_lid.stl`], ["#2563eb", "#93c5fd"], 35, 30, 22]);
    jobs.push([`${n}_base`, [`${n}_base.stl`], ["#2563eb"], 25, 48, 0]); jobs.push([`${n}_base_front`, [`${n}_base.stl`], ["#2563eb"], 160, 30, 0]);
    jobs.push([`${n}_lid`, [`${n}_lid.stl`], ["#93c5fd"], 25, -40, 0]);
  }
  for (const [name, files, colors, az, el, ex] of jobs) {
    await p.evaluate(async (a) => await window.show(...a), [files, colors, az, el, ex]); await p.locator("#c").screenshot({ path: path.join(ROOT, "previews", name + ".png") }); console.log("rendered", name);
  }
  await b.close(); srv.close();
})();
