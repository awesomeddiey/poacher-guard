"use strict";
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* ---------- icons ---------- */
const P = {
  shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
  camera: '<path d="M3 8a2 2 0 0 1 2-2h2l1.5-2h7L17 6h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><circle cx="12" cy="12.5" r="3.5"/>',
  mic: '<rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
  ble: '<path d="M7 7l10 10-5 4V3l5 4L7 17"/>',
  flame: '<path d="M12 3c1 4 5 5.5 5 10a5 5 0 0 1-10 0c0-2 1-3 2-4 .3 1.5 1 2 2 2-1-3-.5-5 1-8z"/>',
  map: '<path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/>',
  pulse: '<path d="M3 12h4l2-6 4 12 2-6h6"/>',
  bell: '<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z"/><path d="M10 21h4"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2 20c0-3.5 3-5.5 7-5.5s7 2 7 5.5"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7M18 15c2.5.6 4 2.3 4 5"/>',
  expand: '<path d="M14 4h6v6M10 20H4v-6M20 4l-7 7M4 20l7-7"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  sound: '<path d="M4 9v6h4l5 4V5L8 9z"/><path d="M16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11"/>',
  mute: '<path d="M4 9v6h4l5 4V5L8 9z"/><path d="M17 9l5 6M22 9l-5 6"/>',
  boom: '<path d="M12 2l2 6 6-2-4 5 5 3-6 1 1 6-4-4-4 4 1-6-6-1 5-3-4-5 6 2z"/>',
  node: '<rect x="4" y="4" width="16" height="16" rx="4"/><circle cx="12" cy="12" r="3"/>',
  alert: '<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18v.5"/>',
  battery: '<rect x="2" y="8" width="17" height="9" rx="2"/><path d="M22 11v3"/>',
};
const icon = (n) => `<svg class="i" viewBox="0 0 24 24">${P[n] || ""}</svg>`;
const applyIcons = (root = document) => root.querySelectorAll("[data-i]").forEach((e) => { e.innerHTML = icon(e.dataset.i); });
const EV_ICON = { poacher: "alert", gunshot: "boom", fire: "flame", ranger: "shield" };
const KIND_ICON = { camera: "camera", flame: "flame" };

/* ---------- format ---------- */
const fmt = (ts) => new Date(ts * 1000).toLocaleString([], { dateStyle: "medium", timeStyle: "medium" });
const ago = (s) => (s == null ? "never" : s < 60 ? `${Math.round(s)}s ago` : s < 3600 ? `${Math.round(s / 60)}m ago` : `${Math.round(s / 3600)}h ago`);
const dur = (s) => { const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60); return h ? `${h}h ${m}m` : `${m}m ${s % 60}s`; };
const bat = (v) => `<span class="bar ${v < 25 ? "low" : ""}" style="display:block"><i style="width:${Math.max(3, Math.min(100, v))}%"></i></span>`;

/* ---------- state ---------- */
let status = null, events = [], unacked = new Map(), soundOn = false, audioCtx = null, openView = null;

/* ---------- map ---------- */
function makeMap(el, interactive = true) {
  const m = L.map(el, { zoomControl: interactive, attributionControl: true }).setView([0, 0], 14);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
    { maxZoom: 19, subdomains: "abcd", attribution: "© OpenStreetMap · © CARTO" }).addTo(m);
  return m;
}
function nodeIcon(n, me) {
  const cls = me ? "me" : n.fire ? "bad" : n.online ? "" : "off";
  const label = me ? "THIS NODE" : n.label.split(" - ")[0];
  return L.divIcon({ className: "", iconSize: me ? [46, 46] : [38, 38], iconAnchor: me ? [23, 23] : [19, 19],
    html: `<div class="mk ${cls}">${icon(me ? "shield" : KIND_ICON[n.kind] || "node")}<span class="mkl">${esc(label)}</span></div>` });
}
function eventIcon(e) {
  return L.divIcon({ className: "", iconSize: [30, 30], iconAnchor: [15, 15], html: `<div class="ev">${icon(EV_ICON[e.type] || "alert")}</div>` });
}
function allPoints() {
  const pts = [[status.site.lat, status.site.lon]];
  status.nodes.forEach((n) => n.lat != null && pts.push([n.lat, n.lon]));
  return pts;
}
function fillMap(map, layer, onNode) {
  layer.clearLayers();
  const s = status.site;
  L.marker([s.lat, s.lon], { icon: nodeIcon({ label: "This node" }, true), zIndexOffset: 1000 })
    .on("click", () => onNode("self")).addTo(layer);
  status.nodes.forEach((n) => n.lat != null && L.marker([n.lat, n.lon], { icon: nodeIcon(n, false) })
    .on("click", () => onNode(n.id)).addTo(layer));
  events.filter((e) => e.type !== "ranger" && e.lat != null && !e.acknowledged).slice(0, 25).forEach((e) =>
    L.marker([e.lat, e.lon], { icon: eventIcon(e), zIndexOffset: 500 }).on("click", () => dlgEvent(e.id)).addTo(layer));
}
const mainMap = makeMap("map");
const mainLayer = L.layerGroup().addTo(mainMap);
let mapSig = "", fitted = false;
function fit(map) { const pts = allPoints(); if (pts.length > 1) map.fitBounds(pts, { padding: [50, 50], maxZoom: 16 }); else map.setView(pts[0], 15); }
function renderMap() {
  const sig = JSON.stringify([status.nodes.map((n) => [n.id, n.online, n.fire, n.lat, n.lon]), status.site, events.filter((e) => !e.acknowledged).map((e) => e.id)]);
  if (sig !== mapSig) { mapSig = sig; fillMap(mainMap, mainLayer, openNode); }
  if (!fitted) { fitted = true; fit(mainMap); }
}
$("recenter").onclick = () => fit(mainMap);

/* ---------- derived ---------- */
function sensors() {
  const s = status, out = [];
  out.push({ key: "camera", ic: "camera", name: "Webcam", on: s.vision.running, bad: false,
    sub: s.vision.running ? `${s.vision.fps} fps · ${s.vision.people} person(s) in view` : s.vision.error || "off" });
  out.push({ key: "mic", ic: "mic", name: "Microphone · gunshot AI", on: s.audio.running, bad: (s.audio.score || 0) >= 0.35,
    sub: s.audio.running ? `${esc((s.audio.device || "mic").slice(0, 28))} · score ${(s.audio.score || 0).toFixed(2)}` : s.audio.error || "off" });
  out.push({ key: "ble", ic: "ble", name: "BLE ranger-tag scanner", on: s.ble.running, bad: false,
    sub: s.ble.running ? `${s.rangers.filter((r) => r.present).length} of ${s.rangers.length} tags in range` : s.ble.error || "off" });
  s.nodes.forEach((n) => out.push({ key: "node:" + n.id, ic: KIND_ICON[n.kind] || "node", name: n.label, on: n.online, bad: n.fire,
    sub: n.fire ? "FIRE DETECTED" : n.online ? (n.kind === "flame" ? `flame raw ${n.raw ?? "-"}` : "reporting") : `offline · ${ago(n.age_s)}` }));
  return out;
}
const seeingTags = () => {
  const v = status.vision, tags = [];
  if (!v.running) return tags;
  const c = {};
  v.detections.forEach((d) => (c[d.label] = (c[d.label] || 0) + 1));
  Object.entries(c).forEach(([k, n]) => tags.push(`<span class="tag ${/weapon|rifle|gun|snare|axe|machete/.test(k) ? "bad" : "blue"}">${esc(k)}${n > 1 ? " ×" + n : ""}</span>`));
  if (!tags.length) tags.push('<span class="tag">Clear · no humans</span>');
  return tags;
};

/* ---------- render ---------- */
function renderAll() {
  const s = status, sn = sensors(), act = sn.filter((x) => x.on).length;
  $("site").textContent = `${s.site.name} · ${s.site.lat.toFixed(4)}, ${s.site.lon.toFixed(4)}`;
  $("chip-ws").className = "chip"; $("chip-ws").textContent = "Live";

  const open = [...unacked.values()], last = open[open.length - 1];
  const hero = $("hero"), vd = s.verdict || { state: "clear" };
  const more = open.length ? ` · ${open.length} unacknowledged alert${open.length > 1 ? "s" : ""}` : "";
  if (vd.state === "ranger" || vd.state === "checking") {
    // Live verdict for the person in view right now takes over the banner.
    const r = vd.state === "ranger";
    hero.className = r ? "ranger" : "checking";
    hero.innerHTML = `<div class="icon">${icon(r ? "shield" : "users")}</div><div class="txt"><div class="big">${r ? "RANGER ON CAMERA - " + esc(vd.ranger) : "Person in view - checking for a ranger tag..."}</div><div class="small">${r ? `Tag ${esc(vd.tag)} · ${vd.rssi} dBm · not an alarm` : "Deciding ranger or poacher"}${more}</div></div>${open.length ? '<button id="ackall">Acknowledge all</button>' : ""}`;
  } else {
  hero.className = open.length ? "alert" : "";
  hero.innerHTML = open.length
    ? `<div class="icon">${icon(EV_ICON[last.type] || "alert")}</div><div class="txt"><div class="big">${esc(last.title)}</div><div class="small">${fmt(last.ts)}${open.length > 1 ? ` · +${open.length - 1} more unacknowledged` : ""}</div></div><button id="ackall">Acknowledge all</button>`
    : `<div class="icon">${icon("shield")}</div><div class="txt"><div class="big">All clear</div><div class="small">${act} of ${sn.length} sensors active · no unacknowledged alerts</div></div>`;
  }
  if (open.length && $("ackall")) $("ackall").onclick = () => open.forEach((e) => ack(e.id));

  const c = s.counts_24h, total = (c.poacher || 0) + (c.gunshot || 0) + (c.fire || 0);
  const on = s.nodes.filter((n) => n.online).length;
  $("kpis").innerHTML = [
    ["sensors", "pulse", `${act}/${sn.length}`, "Active sensors", false],
    ["nodes", "node", `${on + 1}/${s.nodes.length + 1}`, "Nodes online", false],
    ["alerts", "alert", total, "Threat alerts · 24 h", total > 0 && open.length > 0],
    ["rangers", "users", s.rangers.filter((r) => r.present).length, "Rangers in range", false]].map(
    ([k, ic, v, l, bad]) => `<div class="kpi ${bad ? "bad" : ""}" data-k="${k}"><div class="ic">${icon(ic)}</div><div><div class="v">${v}</div><div class="l">${l}</div></div></div>`).join("");

  const v = s.vision;
  $("novideo").style.display = v.running ? "none" : "grid";
  $("vpill").style.display = v.running ? "" : "none";
  $("live-sub").textContent = v.running ? `This node · ${v.fps} fps` : "";
  $("seeing").innerHTML = seeingTags().join("");
  const ranger = s.rangers.find((r) => r.present);
  $("vstats").innerHTML = `
    <div class="stat ${v.people ? "bad" : ""}"><div class="l">People in view</div><div class="v">${v.people || 0}</div></div>
    <div class="stat ${v.weapon ? "bad" : ""}"><div class="l">Weapon</div><div class="v">${v.weapon ? "Detected" : "None"}</div></div>
    <div class="stat ${(s.audio.score || 0) >= 0.35 ? "bad" : ""}"><div class="l">Gunshot score</div><div class="v">${(s.audio.score || 0).toFixed(2)}</div></div>
    <div class="stat ${vd.state === "poacher" || vd.state === "armed" ? "bad" : ""}"><div class="l">Verdict now</div><div class="v">${{ clear: "Clear", checking: "Checking...", ranger: "Ranger", poacher: "Poacher", armed: "Armed" }[vd.state] || "-"}</div></div>
    <div class="stat"><div class="l">Ranger tag</div><div class="v">${ranger ? esc(ranger.ranger.split(" ").pop()) : "None"}</div></div>`;

  $("sensors-sub").textContent = `${act} / ${sn.length} online`;
  $("sensor-list").innerHTML = sn.map((x) => `<li data-s="${esc(x.key)}"><div class="sic ${x.bad ? "bad" : x.on ? "" : "off"}">${icon(x.ic)}</div>
    <div class="n"><b>${esc(x.name)}</b><span>${esc(x.sub)}</span></div><span class="badge ${x.bad ? "bad" : x.on ? "" : "off"}">${x.bad ? "ALERT" : x.on ? "Active" : "Offline"}</span></li>`).join("");

  const sy = s.system, cam = s.nodes.filter((n) => n.kind === "camera");
  $("telemetry").innerHTML = `<div class="h3">Base station</div>
    <div class="row"><span>Uptime</span><b>${dur(sy.uptime_s)}</b></div>
    <div class="row"><span>CPU load (1 min)</span><b>${sy.load1 ?? "n/a"}${sy.load1 != null ? ` / ${sy.cpus} cores` : ""}</b></div>
    <div class="row"><span>Disk free</span><b>${sy.disk_free_gb} GB</b></div>
    <div class="row"><span>Microphone</span><b>${esc(s.audio.device || (s.audio.running ? "default" : "off"))}</b></div>
    <div class="row"><span>Mic level</span><b>${Math.round(Math.min(1, (s.audio.level || 0) * 4) * 100)}%</b></div>
    <div class="row"><span>Gunshot score (recent peak)</span><b>${(s.audio.peak || 0).toFixed(2)}</b></div>
    <div class="h3">Field nodes</div>` + (cam.map((n) => { const t = n.telemetry || {};
      return `<div class="nt" data-n="${esc(n.id)}"><span>${esc(n.label.split(" - ")[0])}</span>${n.online && t.battery != null ? bat(t.battery) : '<span class="badge off">offline</span>'}<b>${n.online && t.battery != null ? Math.round(t.battery) + "%" : ""}</b></div>`; }).join("") || '<div class="empty">No field nodes configured</div>');

  const a = s.activity_24h, mx = Math.max(1, ...a);
  $("activity").innerHTML = `<svg class="chart" viewBox="0 0 240 90" preserveAspectRatio="none">${a.map((n, i) =>
    `<rect class="${n ? (n >= 3 ? "hot" : "has") : ""}" x="${i * 10 + 1}" y="${86 - (n ? 8 + 74 * n / mx : 4)}" width="8" height="${n ? 8 + 74 * n / mx : 4}" rx="3"/>`).join("")}</svg>
    <div class="ax"><span>24 h ago</span><span>${a.reduce((x, y) => x + y, 0)} threat alerts</span><span>now</span></div>`;
  $("rangers").innerHTML = `<div class="h3">Rangers</div>` + (s.rangers.map((r) => `<div class="rg ${r.present ? "on" : ""}"><span class="dot"></span><span>${esc(r.ranger)}</span><span>${r.present ? r.rssi + " dBm" : r.age_s != null ? ago(r.age_s) : "not seen"}</span></div>`).join("") || '<div class="empty">No tags</div>');

  $("sim").hidden = !s.simulation;
  const sb = $("sound"); sb.dataset.i = soundOn ? "sound" : "mute"; sb.classList.toggle("live", soundOn); sb.innerHTML = icon(sb.dataset.i);
  renderMap();
  if (openView && openView.update) openView.update();
}

function renderFeed() {
  const hide = $("hide-ranger").checked;
  const rows = events.filter((e) => !(hide && e.type === "ranger")).slice(0, 60);
  $("feed").innerHTML = rows.map((e) => `<li class="${e.severity} ${e.acknowledged ? "ack" : ""}" data-e="${e.id}">
    ${e.snapshot ? `<img class="thumb" src="/snapshots/${esc(e.snapshot)}" alt="">` : `<div class="thumb">${icon(EV_ICON[e.type] || "alert")}</div>`}
    <div style="flex:1;min-width:0"><div class="t">${esc(e.title)}</div><div class="m">${fmt(e.ts)}${e.lat != null ? ` · ${e.lat.toFixed(4)}, ${e.lon.toFixed(4)}` : ""}</div></div>
    ${e.severity === "critical" && !e.acknowledged ? `<button class="btn red" data-ack="${e.id}">Acknowledge</button>` : `<span class="badge ${e.severity === "critical" ? "off" : ""}">${e.type}</span>`}</li>`).join("") || '<li class="empty">No events yet</li>';
}

/* ---------- modal ---------- */
let modalMap = null;
function openModal(title, html, update, from) {
  closeModal(true);
  $("m-title").textContent = title; $("m-body").innerHTML = html; applyIcons($("m-body"));
  const sheet = document.querySelector(".sheet");
  if (from) { const r = from.getBoundingClientRect(); sheet.style.setProperty("--ox", r.left + r.width / 2 + "px"); sheet.style.setProperty("--oy", r.top + r.height / 2 + "px"); }
  else { sheet.style.setProperty("--ox", "50%"); sheet.style.setProperty("--oy", "50%"); }
  $("modal").hidden = false; document.body.style.overflow = "hidden";
  openView = { update };
  if (update) update();
}
function closeModal(quiet) {
  if (modalMap) { modalMap.remove(); modalMap = null; }
  const v = $("m-vid"); if (v) v.removeAttribute("src");
  $("modal").hidden = true; document.body.style.overflow = ""; openView = null;
  if (!quiet) $("m-body").innerHTML = "";
}
$("m-close").onclick = () => closeModal();
$("modal").onclick = (e) => { if (e.target === $("modal")) closeModal(); };
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });
let lastClick = null; document.addEventListener("click", (e) => { lastClick = e.target.closest(".card,.kpi,li,.mk,.ev") || e.target; }, true);

function dlgVideo() {
  openModal("Live camera · this node", `<div class="split"><div><div class="video" style="aspect-ratio:4/3"><img id="m-vid" src="/video?${Date.now()}" alt="Live"><div class="pill live">LIVE</div><div id="m-seeing"></div></div></div>
    <div><div class="h3">What it is seeing</div><div class="chipset" id="m-tags"></div><div id="m-kv"></div></div></div>`, () => {
    const v = status.vision, a = status.audio; if (!$("m-kv")) return;
    $("m-tags").innerHTML = seeingTags().join("") || '<span class="badge off">camera offline</span>';
    $("m-kv").innerHTML = [["Model", v.model.split(/[\\/]/).pop()], ["Frame rate", v.fps + " fps"], ["People in view", v.people], ["Weapon", v.weapon ? "Detected" : "None"],
      ["Confidence", v.detections.length ? Math.round(Math.max(...v.detections.map((d) => d.conf)) * 100) + "%" : "-"],
      ["Gunshot score", (a.score || 0).toFixed(2)], ["Mic level", Math.round(Math.min(1, (a.level || 0) * 4) * 100) + "%"]]
      .map(([k, x]) => `<div class="row"><span>${k}</span><b>${esc(x)}</b></div>`).join("");
  }, lastClick);
}

function dlgMap(focusId) {
  openModal("Node map", `<div id="m-map"></div><div class="legend" style="margin-top:14px"><span><b class="k me"></b>This node</span><span><b class="k on"></b>Online</span><span><b class="k off"></b>Offline</span><span><b class="k bad"></b>Alert</span></div>`, null, lastClick);
  modalMap = makeMap("m-map"); const layer = L.layerGroup().addTo(modalMap);
  fillMap(modalMap, layer, (id) => { closeModal(); openNode(id); });
  setTimeout(() => { modalMap.invalidateSize(); fit(modalMap); }, 60);
}
$("map-ex").onclick = () => dlgMap();

function openNode(id) {
  if (id === "self") return dlgSelf();
  const n = status.nodes.find((x) => x.id === id); if (!n) return;
  const render = () => {
    const cur = status.nodes.find((x) => x.id === id) || n, t = cur.telemetry || {};
    $("m-body").innerHTML = `<div class="chipset"><span class="badge ${cur.fire ? "bad" : cur.online ? "" : "off"}">${cur.fire ? "FIRE" : cur.online ? "Online" : "Offline"}</span><span class="badge off">${cur.kind === "flame" ? "Flame sensor" : "Camera node"}</span></div>
      <div class="kv" style="${Object.keys(t).length ? "" : "grid-template-columns:1fr"}"><div><div class="row"><span>ID</span><b>${esc(cur.id)}</b></div><div class="row"><span>Position</span><b>${cur.lat?.toFixed(5)}, ${cur.lon?.toFixed(5)}</b></div><div class="row"><span>Last heard</span><b>${ago(cur.age_s)}</b></div>
      ${cur.kind === "flame" ? `<div class="row"><span>Flame reading (raw)</span><b>${cur.raw ?? "-"}</b></div>` : ""}</div>
      ${Object.keys(t).length ? "<div>" : "<div hidden>"}${t.battery != null ? `<div class="row"><span>Battery</span><b>${Math.round(t.battery)}%</b></div>` : ""}${t.rssi != null ? `<div class="row"><span>Signal</span><b>${t.rssi} dBm</b></div>` : ""}${t.temp != null ? `<div class="row"><span>Temperature</span><b>${t.temp} °C</b></div>` : ""}${t.humidity != null ? `<div class="row"><span>Humidity</span><b>${t.humidity}%</b></div>` : ""}${t.people != null ? `<div class="row"><span>People seen</span><b>${t.people}</b></div>` : ""}</div></div>
      ${t.seeing ? `<div class="h3">Currently seeing</div><div class="chipset">${t.seeing.map((x) => `<span class="tag blue">${esc(x)}</span>`).join("")}</div>` : ""}
      ${cur.online ? "" : '<p class="empty">This node has not reported recently. Check power and Wi-Fi/LoRa link.</p>'}
      <button class="btn light" id="show-on-map">Show on map</button>`;
    $("show-on-map").onclick = () => { closeModal(); document.getElementById("mapcard").scrollIntoView({ behavior: "smooth", block: "center" }); mainMap.flyTo([cur.lat, cur.lon], 17); };
  };
  openModal(n.label, "", render, lastClick);
}
function dlgSelf() {
  openModal("This node · base station", "", () => {
    const s = status, sy = s.system;
    $("m-body").innerHTML = `<div class="chipset"><span class="badge">Base</span></div><div class="kv"><div>
      <div class="row"><span>Site</span><b>${esc(s.site.name)}</b></div><div class="row"><span>Position</span><b>${s.site.lat}, ${s.site.lon}</b></div><div class="row"><span>Uptime</span><b>${dur(sy.uptime_s)}</b></div></div>
      <div><div class="row"><span>Camera</span><b>${s.vision.running ? s.vision.fps + " fps" : "off"}</b></div><div class="row"><span>Microphone</span><b>${s.audio.running ? "listening" : "off"}</b></div><div class="row"><span>BLE scanner</span><b>${s.ble.running ? "scanning" : "off"}</b></div></div></div>
      <button class="btn" id="open-cam">Open live camera</button>`;
    $("open-cam").onclick = dlgVideo;
  }, lastClick);
}

function dlgSensor(key) {
  if (key === "camera") return dlgVideo();
  if (key.startsWith("node:")) return openNode(key.slice(5));
  const x = sensors().find((s) => s.key === key);
  openModal(x.name, "", () => {
    const s = status, a = s.audio;
    $("m-body").innerHTML = key === "mic"
      ? `<div class="chipset"><span class="badge ${a.running ? "" : "off"}">${a.running ? "Listening" : "Off"}</span></div>
         <div class="h3">Gunshot probability</div><div class="bar" style="height:16px"><i style="width:${Math.round((a.score || 0) * 100)}%;${(a.score || 0) >= 0.35 ? "background:var(--red)" : ""}"></i></div>
         <div class="ax"><span>0</span><span>alert at 0.35</span><span>1</span></div>
         <div class="h3">Input level</div><div class="bar" style="height:16px"><i style="width:${Math.round(Math.min(1, (a.level || 0) * 4) * 100)}%"></i></div>${a.error ? `<p class="empty">${esc(a.error)}</p>` : ""}`
      : `<div class="chipset"><span class="badge ${s.ble.running ? "" : "off"}">${s.ble.running ? "Scanning" : "Off"}</span></div>
         ${s.rangers.map((r) => `<div class="row"><span>${esc(r.ranger)} (${esc(r.id)})</span><b>${r.present ? "In range · " + r.rssi + " dBm" + (r.interval_s ? " · heard every " + r.interval_s + " s" : "") : r.age_s != null ? "last seen " + ago(r.age_s) : "never seen"}</b></div>`).join("")}${s.ble.error ? `<p class="empty">${esc(s.ble.error)}</p>` : ""}`;
  }, lastClick);
}

function dlgEvent(id) {
  const e = events.find((x) => x.id === id); if (!e) return;
  const d = e.detail || {};
  const info = Object.entries(d).filter(([k]) => k !== "boxes").map(([k, v]) => `<div class="row"><span>${esc(k.replace(/_/g, " "))}</span><b>${esc(typeof v === "number" ? Math.round(v * 1000) / 1000 : typeof v === "object" ? JSON.stringify(v) : v)}</b></div>`).join("");
  openModal(e.severity === "critical" ? "Alert" : "Ranger sighting", `
    <div class="split"><div>${e.snapshot ? `<img class="bigimg" src="/snapshots/${esc(e.snapshot)}" alt="">` : `<div class="empty">No snapshot for this event</div>`}</div>
    <div><h3 style="margin:0 0 6px;font-size:20px;color:${e.severity === "critical" ? "var(--red)" : "var(--ink)"}">${esc(e.title)}</h3>
      <div class="row"><span>Time</span><b>${fmt(e.ts)}</b></div>
      ${e.lat != null ? `<div class="row"><span>Location</span><b><a href="https://maps.google.com/?q=${e.lat},${e.lon}" target="_blank" rel="noopener" style="color:var(--blue)">${e.lat.toFixed(5)}, ${e.lon.toFixed(5)}</a></b></div>` : ""}${info}
      <div style="margin-top:16px;display:flex;gap:10px">${e.severity === "critical" && !e.acknowledged ? `<button class="btn red" id="m-ack">Acknowledge</button>` : ""}${e.lat != null ? `<button class="btn light" id="m-loc">Show on map</button>` : ""}</div></div></div>`, null, lastClick);
  if ($("m-ack")) $("m-ack").onclick = () => { ack(id); closeModal(); };
  if ($("m-loc")) $("m-loc").onclick = () => { closeModal(); document.getElementById("mapcard").scrollIntoView({ behavior: "smooth", block: "center" }); mainMap.flyTo([e.lat, e.lon], 17); };
}

function dlgActivity() {
  openModal("Alerts · last 24 hours", "", () => {
    const a = status.activity_24h, mx = Math.max(1, ...a), c = status.counts_24h, now = new Date();
    $("m-body").innerHTML = `<div class="kv" style="grid-template-columns:repeat(4,1fr);margin-bottom:18px">${["poacher", "gunshot", "fire", "ranger"].map((k) => `<div class="stat"><div class="l">${k}</div><div class="v">${c[k] || 0}</div></div>`).join("")}</div>
      <svg class="chart" viewBox="0 0 480 170" preserveAspectRatio="none">${a.map((n, i) => `<rect class="${n ? (n >= 3 ? "hot" : "has") : ""}" x="${i * 20 + 2}" y="${160 - (n ? 12 + 140 * n / mx : 5)}" width="16" height="${n ? 12 + 140 * n / mx : 5}" rx="5"><title>${n} alerts</title></rect>`).join("")}</svg>
      <div class="ax"><span>${new Date(now - 864e5).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span><span>Threat alerts per hour</span><span>now</span></div>`;
  }, lastClick);
}

function dlgKpi(k) {
  if (k === "sensors") return openModal("Active sensors", "", () => { $("m-body").innerHTML = '<ul id="sl"></ul>'; $("sl").innerHTML = $("sensor-list").innerHTML; $("sl").onclick = sensorClick; }, lastClick);
  if (k === "nodes") return dlgMap();
  if (k === "alerts") return dlgActivity();
  openModal("Rangers in range", "", () => {
    $("m-body").innerHTML = status.rangers.map((r) => `<div class="rg ${r.present ? "on" : ""}" style="padding:10px 0;border-bottom:1px solid var(--line)"><span class="dot"></span><span><b>${esc(r.ranger)}</b> · ${esc(r.id)}</span><span>${r.present ? "In range · " + r.rssi + " dBm" : r.age_s != null ? "last seen " + ago(r.age_s) : "never seen"}</span></div>`).join("");
  }, lastClick);
}

/* ---------- interactions ---------- */
const sensorClick = (e) => { const li = e.target.closest("[data-s]"); if (li) dlgSensor(li.dataset.s); };
$("sensor-list").onclick = sensorClick;
$("kpis").onclick = (e) => { const k = e.target.closest("[data-k]"); if (k) dlgKpi(k.dataset.k); };
$("live").onclick = dlgVideo;
$("activity-card").onclick = dlgActivity;
$("telemetry").onclick = (e) => { const n = e.target.closest("[data-n]"); if (n) openNode(n.dataset.n); };
$("feed").onclick = (e) => { const a = e.target.closest("[data-ack]"); if (a) return ack(+a.dataset.ack); const li = e.target.closest("[data-e]"); if (li) dlgEvent(+li.dataset.e); };
$("hide-ranger").onchange = renderFeed;
$("sim").onclick = (e) => { const b = e.target.closest("[data-sim]"); if (b) fetch(`/api/simulate/${b.dataset.sim}`, { method: "POST" }); };
document.querySelectorAll("#rail nav a").forEach((a) => a.addEventListener("click", () => { document.querySelectorAll("#rail nav a").forEach((x) => x.classList.toggle("on", x === a)); }));

function beep() {
  if (!soundOn || !audioCtx) return;
  for (let i = 0; i < 4; i++) {
    const o = audioCtx.createOscillator(), g = audioCtx.createGain(), t = audioCtx.currentTime + i * 0.3;
    o.type = "square"; o.frequency.value = i % 2 ? 660 : 880; g.gain.value = 0.12;
    o.connect(g).connect(audioCtx.destination); o.start(t); o.stop(t + 0.25);
  }
}
$("sound").onclick = () => { audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)(); soundOn = !soundOn; if (soundOn) beep(); if (status) renderAll(); };

async function ack(id) {
  await fetch(`/api/events/${id}/ack`, { method: "POST" });
  const e = events.find((x) => x.id === id); if (e) e.acknowledged = true; unacked.delete(id);
  renderFeed(); if (status) renderAll();
}
function addEvent(e, live) {
  if (events.some((x) => x.id === e.id)) return;
  events.unshift(e);
  if (e.severity === "critical" && !e.acknowledged) unacked.set(e.id, e);
  if (live && e.severity === "critical") beep();
  if (live && e.type === "gunshot") gunPopup(e);
}

/* Gunshot toast: ONE card in the bottom-right corner. A new gunshot while it is showing updates the same card
   (latest details + "N gunshots") and restarts its 20 s timer, instead of stacking another card. */
let gunToast = null;
function gunPopup(e) {
  const d = e.detail || {};
  if (!gunToast) {
    const el = document.createElement("div"); el.className = "gp"; el.setAttribute("role", "alertdialog");
    gunToast = { el, n: 0, timer: null, id: null };
    const close = () => { if (!gunToast || gunToast.el !== el) return; clearTimeout(gunToast.timer); gunToast = null; el.classList.add("out"); setTimeout(() => el.remove(), 250); };
    gunToast.close = close;
    el.addEventListener("click", (ev) => {
      if (ev.target.closest(".gp-x")) return close();
      if (ev.target.closest(".gp-v")) { const id = gunToast && gunToast.id; close(); if (id != null) dlgEvent(id); }
    });
    $("popups").appendChild(el);
  }
  const t = gunToast; t.n += 1; t.id = e.id;
  t.el.classList.toggle("armed", !!d.with_poacher);
  t.el.innerHTML = `<div class="gp-ic">${icon("boom")}${t.n > 1 ? `<span class="gp-n">${t.n}</span>` : ""}</div>
    <div class="gp-tx"><div class="gp-t">${esc(e.title)}</div>
      <div class="gp-s">${t.n > 1 ? `${t.n} gunshots · latest ` : ""}${new Date(e.ts * 1000).toLocaleTimeString()}${d.label ? ` · ${esc(d.label)}` : ""}</div></div>
    <button class="gp-v">View</button><button class="gp-x" aria-label="Close">${icon("x")}</button>`;
  t.el.classList.remove("bump"); void t.el.offsetWidth; t.el.classList.add("bump");
  clearTimeout(t.timer); t.timer = setTimeout(t.close, 20000);
}

/* ---------- live link ---------- */
setInterval(() => { $("clock").textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }); }, 1000);
function connect() {
  const ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
  ws.onopen = () => { $("video").src = "/video?" + Date.now(); };
  ws.onclose = () => { const c = $("chip-ws"); c.className = "chip bad"; c.textContent = "Reconnecting…"; setTimeout(connect, 2000); };
  ws.onmessage = (m) => {
    const d = JSON.parse(m.data);
    if (d.kind === "hello") { status = d.status; events = []; unacked.clear(); d.events.slice().reverse().forEach((e) => addEvent(e, false)); renderAll(); renderFeed(); }
    else if (d.kind === "status") { status = d.status; renderAll(); }
    else if (d.kind === "nodes" && status) { status.nodes = d.nodes; renderAll(); }
    else if (d.kind === "rangers" && status) { status.rangers = d.rangers; renderAll(); }
    else if (d.kind === "verdict" && status) { status.verdict = d.verdict; renderAll(); }
    else if (d.kind === "event") { addEvent(d.event, true); renderFeed(); if (status) { status.counts_24h[d.event.type] = (status.counts_24h[d.event.type] || 0) + 1; renderAll(); } }
  };
}
applyIcons();
$("chip-ws").className = "chip bad"; $("chip-ws").textContent = "Connecting…";
connect();
