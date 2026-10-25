import * as THREE from "three";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

const PARTS = window.__PARTS, REC = new URLSearchParams(location.search).has("rec");
const clamp = (x, a, b) => Math.min(b, Math.max(a, x)), lerp = (a, b, t) => a + (b - a) * t;
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2), easeOut = (t) => 1 - Math.pow(1 - t, 3);
const DUR = 30.0;

// ---------------------------------------------------------------- timeline
const GROUPS = [
  { match: (n) => n === "base", t0: 0.0, t1: 1.3, from: [0, 0, -50], fade: true },
  { match: (n) => n.startsWith("esp32_"), t0: 1.8, t1: 3.8, from: [0, 0, 150] },
  { match: (n) => n.startsWith("flame_"), t0: 4.2, t1: 6.0, from: [0, 0, 80] },
  { match: (n) => n.startsWith("esp_usb"), t0: 6.5, t1: 8.1, from: [-110, 0, 0] },
  { match: (n) => n === "shell", t0: 8.8, t1: 11.2, from: [0, 0, 150] },
  { match: (n) => n.startsWith("screw_"), t0: 14.2, t1: 15.6, from: [0, 0, -70], stagger: 0.25 },
  { match: (n) => n.startsWith("foot_"), t0: 16.2, t1: 17.0, from: [0, 0, -18], stagger: 0.14 },
  { match: (n) => n.startsWith("webcam_"), t0: 17.8, t1: 19.8, from: [110, 0, 0] },
  { match: (n) => n === "zip_ties", t0: 20.1, t1: 20.9, from: [12, 0, 0], fade: true },
  { match: (n) => n === "cam_usb_cable", t0: 21.2, t1: 22.2, from: [-14, 0, 0], fade: true },
  { match: (n) => n === "stand", t0: 23.0, t1: 24.6, from: [-70, 0, 0] },
];
const STEPS = [
  [0.0, "Base plate", "Blue back plate (this side goes on the tree): four strap lugs with 30 x 5 mm windows, hidden M3 holes, board blocks, a tall post for the flame module and four rubber-foot pockets."],
  [1.8, "ESP32 DevKit V1", "Rests on the four guide blocks with its USB end towards the right side wall."],
  [4.2, "Flame sensor module", "Hangs on its tall post. The IR sensor head stands up towards the round hole in the front face and pokes out of it."],
  [6.5, "USB lead for the ESP32", "The board lies with its USB end at the right side wall. The micro-USB plug goes through the side port, lined up with the socket."],
  [8.8, "Shell", "The white shell (body 150 x 100 x 45 mm) lowers over the back plate and locates on the inner lip. The IR sensor sticks out of the front face."],
  [11.4, "Inside view", "Boards, sensor and cables clear every wall (fit check: 0 mm³ overlap)."],
  [14.2, "Screws and feet", "Four M3 x 16 screws from the tree side, then four rubber feet. The strap lugs sit left and right."],
  [17.8, "USB webcam on the deck", "The clip base sits in the 50 x 26 mm recess on the top end wall. The lens faces away from the tree, like the IR sensor."],
  [20.1, "Zip ties and webcam cable", "Ties go through the four deck slots. The webcam lead needs no hole: it runs down the outside of the casing straight to the PC."],
  [23.0, "Stand foot", "Optional foot: the bottom end drops into its pocket so the node stands upright on a table or the ground, 150 mm tall. Leave it off when strapping to a tree."],
  [25.4, "Done", "Stand it up, or strap it to a trunk through the four lugs (camera end up), plug both USB leads into the PC and run run-poacher-guard.bat."],
];
const CAM = [ // time, azimuth deg, elevation deg, distance, target
  [0, 40, 30, 328, [82, 55, 0]], [2.5, 28, 40, 296, [82, 55, 8]], [5, 62, 42, 281, [90, 60, 12]], [7.2, 165, 22, 335, [30, 30, 14]],
  [9.8, 215, 24, 406, [82, 55, 22]], [12.5, 250, 16, 367, [82, 55, 16]], [15.0, 305, -34, 335, [82, 55, -2]], [17.2, 335, 22, 367, [82, 55, 12]],
  [19.4, 215, 26, 437, [82, 55, 34]], [22.4, 200, 22, 468, [82, 55, 26]], [30, 560, 20, 421, [82, 55, 24]],
];
const XRAY = [[0, 1], [11.4, 1], [12.1, 0.18], [13.8, 0.18], [14.1, 1], [30, 1]]; // shell opacity

// ---------------------------------------------------------------- scene
const canvas = document.getElementById("c"), renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(REC ? 1 : Math.min(devicePixelRatio, 2)); renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap; renderer.setClearColor(0xf4f7fc);
const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(30, 16 / 9, 5, 5000); camera.up.set(0, 0, 1);
scene.add(new THREE.HemisphereLight(0xffffff, 0x9fb3d6, 0.95));
const sun = new THREE.DirectionalLight(0xffffff, 2.1); sun.position.set(190, -260, 420); sun.target.position.set(82, 55, 0); sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048); Object.assign(sun.shadow.camera, { left: -260, right: 260, top: 260, bottom: -260, near: 10, far: 1200 }); sun.shadow.bias = -0.0004; scene.add(sun, sun.target);
const fill = new THREE.DirectionalLight(0xbcd2ff, 0.7); fill.position.set(-300, 200, 120); scene.add(fill);
const floor = new THREE.Mesh(new THREE.CircleGeometry(900, 64), new THREE.ShadowMaterial({ opacity: 0.2 })); floor.position.set(82, 55, -6.05); floor.receiveShadow = true; scene.add(floor);
const controls = new OrbitControls(camera, canvas); controls.enableDamping = true; controls.dampingFactor = 0.08;
let auto = true; controls.addEventListener("start", () => { if (!REC) { auto = false; document.getElementById("auto").classList.remove("on"); } });

const MAT = (name, color) => {
  const metal = /module|shield|lens_ring|screw|pins|antenna/.test(name), cable = /cable|ties|plug/.test(name);
  return new THREE.MeshStandardMaterial({ color, metalness: metal ? 0.75 : 0.05, roughness: metal ? 0.3 : cable ? 0.75 : 0.55, transparent: true, opacity: 1 });
};
const objs = {}; const loader = new STLLoader();
for (const [name, p] of Object.entries(PARTS)) {
  const bin = Uint8Array.from(atob(p.b64), (c) => c.charCodeAt(0)).buffer, geo = loader.parse(bin); geo.computeVertexNormals();
  const m = new THREE.Mesh(geo, MAT(name, p.color)); m.castShadow = name !== "cam_usb_cable"; m.receiveShadow = true; m.visible = false; scene.add(m); objs[name] = m;
}
const groupOf = {}; for (const g of GROUPS) { let i = 0; for (const n of Object.keys(objs)) if (g.match(n)) { groupOf[n] = { g, i: i++ }; } }

// ---------------------------------------------------------------- time -> pose
let t = 0, playing = true, speed = 1, xrayOn = false;
const interp = (keys, tt) => { for (let i = 0; i < keys.length - 1; i++) if (tt <= keys[i + 1][0]) { const k = ease(clamp((tt - keys[i][0]) / (keys[i + 1][0] - keys[i][0]), 0, 1)); return [keys[i], keys[i + 1], k]; } return [keys.at(-1), keys.at(-1), 0]; };
function pose(tt) {
  for (const [name, o] of Object.entries(objs)) {
    const { g, i } = groupOf[name] || {}; if (!g) { o.visible = true; continue; }
    const a = g.t0 + i * (g.stagger || 0), b = g.t1 + i * (g.stagger || 0), k = clamp((tt - a) / (b - a), 0, 1), e = easeOut(k);
    o.visible = tt >= a; o.position.set(g.from[0] * (1 - e), g.from[1] * (1 - e), g.from[2] * (1 - e));
    const op = g.fade ? clamp(k * 1.6, 0, 1) : 1; o.material.opacity = op;
    if (name === "shell") { let x = 1; const [k0, k1, kk] = interp(XRAY, tt); x = lerp(k0[1], k1[1], kk); if (xrayOn) x = 0.18; o.material.opacity = x; o.material.depthWrite = x > 0.9; o.castShadow = x > 0.9; }
  }
  if (auto) { const [a, b, k] = interp(CAM, tt); const az = lerp(a[1], b[1], k) * Math.PI / 180, el = lerp(a[2], b[2], k) * Math.PI / 180, d = lerp(a[3], b[3], k), tg = a[4].map((v, j) => lerp(v, b[4][j], k));
    controls.target.set(...tg); camera.position.set(tg[0] + d * Math.cos(el) * Math.sin(az), tg[1] - d * Math.cos(el) * Math.cos(az), tg[2] + d * Math.sin(el)); }
  const s = STEPS.filter((x) => tt >= x[0]).at(-1) || STEPS[0], idx = STEPS.indexOf(s);
  document.getElementById("stepno").textContent = `Step ${idx + 1} of ${STEPS.length}`; document.getElementById("steptitle").textContent = s[1]; document.getElementById("steptext").textContent = s[2];
  document.querySelectorAll(".chip").forEach((c, j) => c.classList.toggle("on", j === idx)); document.getElementById("bar").style.width = `${(tt / DUR) * 100}%`; document.getElementById("seek").value = tt;
}
function resize() { const w = canvas.clientWidth, h = canvas.clientHeight; if (canvas.width !== Math.floor(w * renderer.getPixelRatio())) { renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); } }
function draw() { resize(); pose(t); controls.update(); renderer.render(scene, camera); }
window.renderAt = (tt) => { t = tt; draw(); return true; };

// ---------------------------------------------------------------- UI
document.getElementById("steps").innerHTML = STEPS.map((s, i) => `<button class="chip" data-t="${s[0]}"><b>${i + 1}</b>${s[1]}</button>`).join("");
document.querySelectorAll(".chip").forEach((c) => (c.onclick = () => { t = +c.dataset.t + 0.01; playing = false; auto = true; sync(); }));
const seek = document.getElementById("seek"); seek.max = DUR; seek.oninput = () => { t = +seek.value; playing = false; sync(); };
const sync = () => { document.getElementById("play").textContent = playing ? "Pause" : "Play"; document.getElementById("auto").classList.toggle("on", auto); document.getElementById("xray").classList.toggle("on", xrayOn); };
document.getElementById("play").onclick = () => { if (t >= DUR - 0.05) t = 0; playing = !playing; sync(); };
document.getElementById("restart").onclick = () => { t = 0; playing = true; auto = true; sync(); };
document.getElementById("auto").onclick = () => { auto = !auto; sync(); };
document.getElementById("xray").onclick = () => { xrayOn = !xrayOn; sync(); };
document.getElementById("speed").onchange = (e) => (speed = +e.target.value);
let last = performance.now();
(function loop(now) { if (playing && !REC) { t += ((now - last) / 1000) * speed; if (t >= DUR) { t = DUR; playing = false; sync(); } } last = now; draw(); requestAnimationFrame(loop); })(last);
if (REC) document.body.classList.add("rec");
sync(); window.__ready = true;
