// Browser versions of the two Poacher Guard detectors. Same models as the Python prototype:
//   person: YOLO11n (ONNX, onnxruntime-web, WebAssembly)      gunshot: YAMNet (TFLite, LiteRT.js, WebAssembly)
import * as ort from "/vendor/ort/ort.wasm.min.mjs";
import { loadLiteRt, loadAndCompile, Tensor } from "/vendor/litert/litert.js";

ort.env.wasm.wasmPaths = "/vendor/ort/";
ort.env.wasm.numThreads = 1;            // single thread: works without cross-origin isolation headers

export class PersonDetector {
  constructor(size = 640) { this.size = size; this.cv = new OffscreenCanvas(size, size); this.ctx = this.cv.getContext("2d", { willReadFrequently: true }); }
  async load(url = "/models/yolo11n.onnx") { this.session = await ort.InferenceSession.create(url, { executionProviders: ["wasm"], graphOptimizationLevel: "all" }); this.input = this.session.inputNames[0]; return this; }
  /** source: HTMLVideoElement | HTMLImageElement | canvas. Returns [{x1,y1,x2,y2,conf}] in source pixel coordinates. */
  async detect(source, conf = 0.45, nmsIou = 0.7) {
    const S = this.size, w = source.videoWidth || source.naturalWidth || source.width, h = source.videoHeight || source.naturalHeight || source.height;
    const r = Math.min(S / w, S / h), nw = Math.round(w * r), nh = Math.round(h * r), dx = (S - nw) >> 1, dy = (S - nh) >> 1;
    this.ctx.fillStyle = "rgb(114,114,114)"; this.ctx.fillRect(0, 0, S, S); this.ctx.drawImage(source, dx, dy, nw, nh);
    const px = this.ctx.getImageData(0, 0, S, S).data, n = S * S, t = new Float32Array(3 * n);
    for (let i = 0; i < n; i++) { t[i] = px[4 * i] / 255; t[n + i] = px[4 * i + 1] / 255; t[2 * n + i] = px[4 * i + 2] / 255; }
    const out = (await this.session.run({ [this.input]: new ort.Tensor("float32", t, [1, 3, S, S]) }))[this.session.outputNames[0]];
    const d = out.data, A = out.dims[2], cand = [];                    // output [1, 4 + 80, 8400]; class 0 = person
    for (let i = 0; i < A; i++) {
      const s = d[4 * A + i]; if (s < conf) continue;
      const cx = d[i], cy = d[A + i], bw = d[2 * A + i], bh = d[3 * A + i];
      cand.push({ x1: (cx - bw / 2 - dx) / r, y1: (cy - bh / 2 - dy) / r, x2: (cx + bw / 2 - dx) / r, y2: (cy + bh / 2 - dy) / r, conf: s });
    }
    cand.sort((a, b) => b.conf - a.conf); const keep = [];
    for (const c of cand) if (keep.every((k) => iou(k, c) < nmsIou)) keep.push(c);
    return keep.map((b) => ({ x1: Math.max(0, b.x1), y1: Math.max(0, b.y1), x2: Math.min(w, b.x2), y2: Math.min(h, b.y2), conf: b.conf }));
  }
}
function iou(a, b) {
  const x1 = Math.max(a.x1, b.x1), y1 = Math.max(a.y1, b.y1), x2 = Math.min(a.x2, b.x2), y2 = Math.min(a.y2, b.y2), i = Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
  return i / ((a.x2 - a.x1) * (a.y2 - a.y1) + (b.x2 - b.x1) * (b.y2 - b.y1) - i + 1e-9);
}

export const WIN = 15600, SR = 16000, GUN_IDX = [421, 422, 423, 424, 425];   // YAMNet: gunshot, machine gun, fusillade, artillery, cap gun
export class GunshotDetector {
  async load(model = "/models/yamnet.tflite", head = "/models/gunshot_head.json") {
    await loadLiteRt("/vendor/litert/"); this.model = await loadAndCompile(model, { accelerator: "wasm" });
    try { this.head = await (await fetch(head)).json(); } catch { this.head = null; }
    return this;
  }
  /** wav: Float32Array of 15600 samples at 16 kHz. Returns { zero: max gun-class score, head: logistic-regression probability or null, scores }. */
  async score(wav) {
    const t = new Tensor(wav, [WIN]); const res = await this.model.run(t); t.delete();
    let scores = null; for (const o of res) { const m = await o.moveTo("wasm"); const a = m.toTypedArray(); if (a.length === 521) scores = Float32Array.from(a); m.delete?.(); }
    try { res.delete?.(); } catch {}
    const zero = Math.max(...GUN_IDX.map((i) => scores[i]));
    let head = null; if (this.head) { let z = this.head.intercept; for (let i = 0; i < 521; i++) z += this.head.coef[i] * scores[i]; head = 1 / (1 + Math.exp(-z)); }
    return { zero, head, scores };
  }
}
