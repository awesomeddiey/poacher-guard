"""Detection metrics used in Section 3.7: AP (COCO-style, 101-point), precision, recall, F1, image-level
confusion matrix, recall by person size with Wilson intervals, and CPU inference time."""
import pickle
from math import sqrt
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

IOUS = np.arange(0.5, 0.96, 0.05)


def gt_boxes(lbl, W, H):
    out = []
    if lbl.exists():
        for line in lbl.read_text().split("\n"):
            if line.strip():
                _, x, y, w, h = map(float, line.split()[:5]); out.append([(x - w / 2) * W, (y - h / 2) * H, (x + w / 2) * W, (y + h / 2) * H])
    return np.array(out).reshape(-1, 4)


def iou(a, b):
    if len(a) == 0 or len(b) == 0: return np.zeros((len(a), len(b)))
    x1 = np.maximum(a[:, None, 0], b[None, :, 0]); y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 2], b[None, :, 2]); y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    aa = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1]); bb = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return inter / (aa[:, None] + bb[None, :] - inter + 1e-9)


def predict_set(weights, ds_dir, imgsz=640, cache=None):
    """Run the model on every image of a dataset directory (images/, labels/). Returns a list of per-image records."""
    cache = Path(cache) if cache else None
    if cache and cache.exists(): return pickle.loads(cache.read_bytes())
    model = YOLO(str(weights)); recs = []
    imgs = sorted((Path(ds_dir) / "images").glob("*.jpg"))
    for i, p in enumerate(imgs):
        im = cv2.imread(str(p)); H, W = im.shape[:2]
        r = model.predict(im, imgsz=imgsz, conf=0.001, iou=0.7, classes=[0], max_det=300, verbose=False, device="cpu")[0]
        b = r.boxes
        recs.append(dict(id=p.stem, W=W, H=H, gt=gt_boxes(Path(ds_dir) / "labels" / f"{p.stem}.txt", W, H),
                         boxes=b.xyxy.cpu().numpy(), scores=b.conf.cpu().numpy(), ms=sum(r.speed.values())))
    if cache: cache.parent.mkdir(parents=True, exist_ok=True); cache.write_bytes(pickle.dumps(recs))
    return recs


def match_all(recs, thr):
    """Greedy matching in descending score order. Returns (scores, is_tp) over all predictions."""
    S, T = [], []
    for r in recs:
        o = np.argsort(-r["scores"]); b, s = r["boxes"][o], r["scores"][o]
        m = iou(b, r["gt"]); used = set(); tp = np.zeros(len(b), bool)
        for i in range(len(b)):
            if m.shape[1]:
                j = [k for k in np.argsort(-m[i]) if k not in used and m[i, k] >= thr]
                if j: used.add(j[0]); tp[i] = True
        S.append(s); T.append(tp)
    return (np.concatenate(S) if S else np.zeros(0)), (np.concatenate(T) if T else np.zeros(0, bool))


def ap_from(scores, tp, n_gt):
    o = np.argsort(-scores); tpc = np.cumsum(tp[o]); fpc = np.cumsum(~tp[o])
    rec = tpc / max(n_gt, 1); prec = tpc / np.maximum(tpc + fpc, 1)
    mrec = np.concatenate([[0], rec, [1]]); mpre = np.concatenate([[1], prec, [0]])
    mpre = np.flip(np.maximum.accumulate(np.flip(mpre)))
    x = np.linspace(0, 1, 101)
    return float(np.mean(np.interp(x, mrec, mpre))), rec, prec


def wilson(k, n, z=1.96):
    if n == 0: return (float("nan"), float("nan"))
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); a = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - a) / d, (c + a) / d)


def summarise(recs, conf=0.5):
    n_gt = sum(len(r["gt"]) for r in recs)
    aps = [ap_from(*match_all(recs, t), n_gt)[0] for t in IOUS]
    s50, t50 = match_all(recs, 0.5)
    ap50, rec_c, prec_c = ap_from(s50, t50, n_gt)
    out = dict(n_images=len(recs), n_gt=n_gt, mAP50=ap50, mAP50_95=float(np.mean(aps)))
    k = s50 >= conf; tp = int(t50[k].sum()); fp = int(k.sum() - tp); fn = n_gt - tp
    out.update(tp=tp, fp=fp, fn=fn, precision=tp / max(tp + fp, 1), recall=tp / max(n_gt, 1))
    cs = np.arange(0.05, 0.96, 0.01); f1s, ps, rs = [], [], []
    for c in cs:
        kk = s50 >= c; t_ = int(t50[kk].sum()); f_ = int(kk.sum() - t_)
        p_, r_ = t_ / max(t_ + f_, 1), t_ / max(n_gt, 1); ps.append(p_); rs.append(r_); f1s.append(2 * p_ * r_ / max(p_ + r_, 1e-9))
    b = int(np.argmax(f1s)); out.update(best_f1=float(f1s[b]), best_f1_conf=float(cs[b]))
    # image level
    with_p = [r for r in recs if len(r["gt"])]; without = [r for r in recs if not len(r["gt"])]
    out.update(img_with=len(with_p), img_without=len(without),
               img_missed=sum(1 for r in with_p if not (r["scores"] >= conf).any()),
               img_flagged=sum(1 for r in without if (r["scores"] >= conf).any()))
    # recall by size
    sizes, hit = [], []
    for r in recs:
        if not len(r["gt"]): continue
        keep = r["scores"] >= conf; b_ = r["boxes"][keep]; sc = r["scores"][keep]
        o = np.argsort(-sc); b_ = b_[o]; m = iou(b_, r["gt"]); used = set(); matched = np.zeros(len(r["gt"]), bool)
        for i in range(len(b_)):
            j = [q for q in np.argsort(-m[i]) if q not in used and m[i, q] >= 0.5]
            if j: used.add(j[0]); matched[j[0]] = True
        g = r["gt"]; sizes += list(((g[:, 2] - g[:, 0]) * (g[:, 3] - g[:, 1])) / (r["W"] * r["H"])); hit += list(matched)
    sizes, hit = np.array(sizes), np.array(hit)
    bins = [(0, 0.01, "<1%"), (0.01, 0.05, "1-5%"), (0.05, 0.2, "5-20%"), (0.2, 1.01, ">20%")]
    out["recall_by_size"] = {lab: dict(n=int(((sizes >= lo) & (sizes < hi)).sum()), hit=int(hit[(sizes >= lo) & (sizes < hi)].sum()),
                                       ci=wilson(int(hit[(sizes >= lo) & (sizes < hi)].sum()), int(((sizes >= lo) & (sizes < hi)).sum())))
                             for lo, hi, lab in bins}
    ms = [r["ms"] for r in recs[5:]]; out["ms_mean"] = float(np.mean(ms))
    out["curves"] = dict(pr_rec=rec_c[::max(1, len(rec_c) // 400)].tolist(), pr_prec=prec_c[::max(1, len(rec_c) // 400)].tolist(),
                         conf=cs.tolist(), f1=f1s, prec=ps, rec=rs)
    return out
