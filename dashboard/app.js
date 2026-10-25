"use strict";
const $ = (id) => document.getElementById(id);
const ICON = { poacher: "🚨", gunshot: "💥", fire: "🔥", ranger: "🧑‍✈️" };
let events = [], status = null, soundOn = false, audioCtx = null, unacked = new Map();
const pins = new Map();

// ---- map -------------------------------------------------------------
const map = L.map("map").setView([0, 0], 15);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(map);
const siteLayer = L.layerGroup().addTo(map), nodeLayer = L.layerGroup().addTo(map), eventLayer = L.layerGroup().addTo(map);
let centred = false;

function drawStatic() {
  const s = status.site;
  if (!centred) { map.setView([s.lat, s.lon], 15); centred = true; }
  siteLayer.clearLayers();
  L.circleMarker([s.lat, s.lon], { radius: 9, color: "#4aa8ff", fillOpacity: .6 }).bindTooltip("Base station / camera").addTo(siteLayer);
  nodeLayer.clearLayers();
  status.nodes.forEach((n) => n.lat != null && L.circleMarker([n.lat, n.lon], {
    radius: 8, color: n.fire ? "#ff4d4f" : n.online ? "#3fb950" : "#777", fillOpacity: .7 }).bindTooltip(n.label).addTo(nodeLayer));
}
function pin(ev) {
  if (ev.lat == null || ev.type === "ranger" || pins.has(ev.id)) return;
  const m = L.marker([ev.lat, ev.lon], { icon: L.divIcon({ className: "", html: `<div style="font-size:24px">${ICON[ev.type] || "⚠️"}</div>`, iconSize: [28, 28] }) })
    .bindPopup(`<b>${esc(ev.title)}</b><br>${fmt(ev.ts)}`).addTo(eventLayer);
  pins.set(ev.id, m);
}

// ---- helpers ---------------------------------------------------------
function esc(s) { return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function fmt(ts) { return new Date(ts * 1000).toLocaleString(); }
function chip(id, ok, text) { const e = $(id); e.className = "chip " + (ok ? "ok" : "bad"); e.textContent = text; }

function beep() {
  if (!soundOn || !audioCtx) return;
  for (let i = 0; i < 4; i++) {
    const o = audioCtx.createOscillator(), g = audioCtx.createGain(), t = audioCtx.currentTime + i * 0.3;
    o.type = "square"; o.frequency.value = i % 2 ? 660 : 880; g.gain.value = 0.15;
    o.connect(g).connect(audioCtx.destination); o.start(t); o.stop(t + 0.25);
  }
}
$("sound").onclick = () => {
  audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
  soundOn = !soundOn; $("sound").textContent = soundOn ? "🔊 Alarm sound on" : "🔇 Enable alarm sound"; if (soundOn) beep();
};

// ---- render ----------------------------------------------------------
function renderStatus() {
  const s = status;
  $("site").textContent = s.site.name;
  chip("chip-cam", s.vision.running, s.vision.running ? `Camera ${s.vision.fps} fps` : "Camera: " + (s.vision.error || "off"));
  chip("chip-mic", s.audio.running, s.audio.running ? "Mic listening" : "Mic: " + (s.audio.error || "off"));
  chip("chip-ble", s.ble.running, s.ble.running ? "BLE scanning" : "BLE: " + (s.ble.error || "off"));
  $("lvl").value = Math.min(1, (s.audio.level || 0) * 4); $("gs").value = s.audio.score || 0; $("gs-v").textContent = (s.audio.score || 0).toFixed(2);
  $("cam-meta").textContent = s.vision.running ? `${s.vision.people} person(s) in view` : "";
  $("novideo").style.display = s.vision.running ? "none" : "grid";
  $("rangers").innerHTML = s.rangers.map((r) =>
    `<li><span><span class="dot ${r.present ? "on" : "off"}"></span>${esc(r.ranger)}</span><span class="meta">${r.present ? `in range · ${r.rssi} dBm` : r.age_s != null ? `last seen ${Math.round(r.age_s)}s ago` : "never seen"}</span></li>`).join("") || "<li class='meta'>No tags configured</li>";
  $("nodes").innerHTML = s.nodes.map((n) =>
    `<li><span><span class="dot ${n.fire ? "fire" : n.online ? "on" : "off"}"></span>${esc(n.label)}</span><span class="meta">${n.fire ? "FIRE" : n.online ? "online" : "offline"}</span></li>`).join("") || "<li class='meta'>No nodes</li>";
  const c = s.counts_24h;
  $("counts").innerHTML = ["poacher", "gunshot", "fire", "ranger"].map((k) => `<span>${ICON[k]} <b>${c[k] || 0}</b> <span class="meta">${k}</span></span>`).join("");
  $("sim").hidden = !s.simulation;
  drawStatic();
}

function renderFeed() {
  const hide = $("hide-ranger").checked;
  $("feed").innerHTML = events.filter((e) => !(hide && e.type === "ranger")).slice(0, 100).map((e) => `
    <li class="${e.severity} ${e.acknowledged ? "ack" : ""}" data-id="${e.id}">
      ${e.snapshot ? `<img src="/snapshots/${esc(e.snapshot)}" data-full="/snapshots/${esc(e.snapshot)}" alt="">` : `<div class="ph">${ICON[e.type] || "⚠️"}</div>`}
      <div><div class="t">${ICON[e.type] || ""} ${esc(e.title)}</div>
        <div class="meta">${fmt(e.ts)} · ${e.lat != null ? `<a href="https://maps.google.com/?q=${e.lat},${e.lon}" target="_blank" rel="noopener">${e.lat.toFixed(5)}, ${e.lon.toFixed(5)}</a>` : ""}</div></div>
      ${e.severity === "critical" && !e.acknowledged ? `<button data-ack="${e.id}">Ack</button>` : ""}
    </li>`).join("") || "<li class='meta'>No events yet</li>";
}

function renderBanner() {
  const open = [...unacked.values()];
  $("banner").hidden = !open.length;
  if (open.length) { const e = open[open.length - 1]; $("banner-title").textContent = `${ICON[e.type] || "⚠️"} ${e.title}` + (open.length > 1 ? `  (+${open.length - 1} more)` : ""); $("banner-time").textContent = fmt(e.ts); }
}

function addEvent(e, live) {
  if (events.some((x) => x.id === e.id)) return;
  events.unshift(e); pin(e);
  if (e.severity === "critical" && !e.acknowledged) unacked.set(e.id, e);
  if (live && e.severity === "critical") beep();
}
async function ack(id) { await fetch(`/api/events/${id}/ack`, { method: "POST" }); const e = events.find((x) => x.id === id); if (e) e.acknowledged = true; unacked.delete(id); renderFeed(); renderBanner(); }

$("banner-ack").onclick = () => [...unacked.keys()].forEach(ack);
$("feed").onclick = (ev) => {
  const a = ev.target.closest("[data-ack]"); if (a) return ack(+a.dataset.ack);
  const im = ev.target.closest("img[data-full]"); if (im) { $("lightbox").querySelector("img").src = im.dataset.full; $("lightbox").hidden = false; }
};
$("lightbox").onclick = () => ($("lightbox").hidden = true);
$("hide-ranger").onchange = renderFeed;
$("sim").onclick = (ev) => { const b = ev.target.closest("[data-sim]"); if (b) fetch(`/api/simulate/${b.dataset.sim}`, { method: "POST" }); };

// ---- live link -------------------------------------------------------
function connect() {
  const ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
  ws.onopen = () => { chip("chip-ws", true, "Live"); $("video").src = "/video?" + Date.now(); };
  ws.onclose = () => { chip("chip-ws", false, "Reconnecting…"); setTimeout(connect, 2000); };
  ws.onmessage = (m) => {
    const d = JSON.parse(m.data);
    if (d.kind === "hello") { status = d.status; events = []; unacked.clear(); d.events.slice().reverse().forEach((e) => addEvent(e, false)); renderStatus(); renderFeed(); renderBanner(); }
    else if (d.kind === "status") { status = d.status; renderStatus(); }
    else if (d.kind === "nodes") { if (status) { status.nodes = d.nodes; renderStatus(); } }
    else if (d.kind === "event") { addEvent(d.event, true); renderFeed(); renderBanner(); }
  };
}
chip("chip-ws", false, "Connecting…");
connect();
