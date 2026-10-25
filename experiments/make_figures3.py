"""Figures 3.3 and 3.5 to 3.13 for Chapter 3, drawn from the experiment outputs."""
import html
import json
import pickle
import sys
from pathlib import Path

import cv2
import librosa
import librosa.display
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from common import DATA, FIG, OUT  # noqa: E402
from evalkit import iou  # noqa: E402

plt.rcParams.update({"font.family": "DejaVu Serif", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
BLUE, RED, GREY, LBLUE = "#1d4ed8", "#dc2626", "#64748b", "#93c5fd"
afr = pd.read_csv(OUT / "african_test_set.csv").set_index("ImageID")


def draw(im, boxes, color, dashed=False, scores=None):
    out = im.copy()
    for k, b in enumerate(boxes):
        p1, p2 = (int(b[0]), int(b[1])), (int(b[2]), int(b[3]))
        if dashed:
            for x in range(p1[0], p2[0], 14):
                cv2.line(out, (x, p1[1]), (min(x + 7, p2[0]), p1[1]), color, 3); cv2.line(out, (x, p2[1]), (min(x + 7, p2[0]), p2[1]), color, 3)
            for y in range(p1[1], p2[1], 14):
                cv2.line(out, (p1[0], y), (p1[0], min(y + 7, p2[1])), color, 3); cv2.line(out, (p2[0], y), (p2[0], min(y + 7, p2[1])), color, 3)
        else:
            cv2.rectangle(out, p1, p2, color, 3)
            if scores is not None: cv2.putText(out, f"{scores[k]:.2f}", (p1[0] + 3, max(p1[1] - 6, 18)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    return out


def credit(iid):
    r = afr.loc[iid]; return f"{r.Author}. {html.unescape(str(r.Title))}. Open Images {iid}. CC BY 2.0. {r.OriginalLandingURL}"


def fig_labels(ids):
    """Figure 3.3: images with boxes drawn back from their YOLO label files, with the file contents beneath."""
    fig, axs = plt.subplots(2, len(ids), figsize=(4.6 * len(ids), 6.2), gridspec_kw={"height_ratios": [3, 1.3]})
    for k, iid in enumerate(ids):
        im = cv2.cvtColor(cv2.imread(str(DATA / "oi_african" / "images" / f"{iid}.jpg")), cv2.COLOR_BGR2RGB); H, W = im.shape[:2]
        lines = [l.split() for l in (DATA / "oi_african" / "labels" / f"{iid}.txt").read_text().splitlines() if l.strip()]
        bx = [[(float(x) - float(w) / 2) * W, (float(y) - float(h) / 2) * H, (float(x) + float(w) / 2) * W, (float(y) + float(h) / 2) * H] for _, x, y, w, h in lines]
        axs[0, k].imshow(draw(im, bx, (220, 38, 38))); axs[0, k].axis("off")
        axs[1, k].axis("off"); axs[1, k].text(0, 1, "\n".join(" ".join(l[:1] + [f"{float(v):.4f}" for v in l[1:]]) for l in lines[:7]) + ("\n..." if len(lines) > 7 else ""), va="top", family="monospace", fontsize=8)
    fig.tight_layout(); fig.savefig(FIG / "fig3_3_labels.png", dpi=200); plt.close(fig)


def fig_curves():
    """Figure 3.6: training curves."""
    df = pd.read_csv(DATA / "runs" / "person_ft" / "results.csv"); df.columns = [c.strip() for c in df.columns]
    fig, ax = plt.subplots(1, 3, figsize=(11, 3.3)); e = df["epoch"]
    for c, col in (("train/box_loss", BLUE), ("train/cls_loss", RED), ("train/dfl_loss", GREY)): ax[0].plot(e, df[c], marker="o", ms=3, color=col, label=c.split("/")[1])
    ax[0].set_title("Training losses"); ax[0].set_xlabel("Epoch"); ax[0].legend()
    for c, col in (("val/box_loss", BLUE), ("val/cls_loss", RED), ("val/dfl_loss", GREY)): ax[1].plot(e, df[c], marker="o", ms=3, color=col, label=c.split("/")[1])
    ax[1].set_title("Validation losses"); ax[1].set_xlabel("Epoch"); ax[1].legend()
    for c, col, lab in (("metrics/precision(B)", GREY, "precision"), ("metrics/recall(B)", RED, "recall"), ("metrics/mAP50(B)", BLUE, "mAP@0.5"), ("metrics/mAP50-95(B)", LBLUE, "mAP@0.5:0.95")): ax[2].plot(e, df[c], marker="o", ms=3, color=col, label=lab)
    ax[2].set_title("Validation metrics"); ax[2].set_xlabel("Epoch"); ax[2].legend()
    fig.tight_layout(); fig.savefig(FIG / "fig3_6_training.png", dpi=200); plt.close(fig)


def fig_pr_f1(ev):
    pre, ft = ev["pretrained/voc_test"]["curves"], ev["finetuned/voc_test"]["curves"]
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.6))
    ax[0].plot(pre["pr_rec"], pre["pr_prec"], color=BLUE, label=f"Pretrained (AP {ev['pretrained/voc_test']['mAP50']:.3f})"); ax[0].plot(ft["pr_rec"], ft["pr_prec"], color=RED, label=f"Fine-tuned (AP {ev['finetuned/voc_test']['mAP50']:.3f})")
    ax[0].set_xlabel("Recall"); ax[0].set_ylabel("Precision"); ax[0].set_xlim(0, 1); ax[0].set_ylim(0, 1.02); ax[0].legend(loc="lower left"); ax[0].set_title("Precision-recall (IoU 0.5)")
    ax[1].plot(pre["conf"], pre["f1"], color=BLUE, label="Pretrained"); ax[1].plot(ft["conf"], ft["f1"], color=RED, label="Fine-tuned")
    ax[1].axvline(0.45, color=GREY, ls=":", label="Prototype threshold (0.45)"); ax[1].set_xlabel("Confidence threshold"); ax[1].set_ylabel("F1-score"); ax[1].legend(); ax[1].set_title("F1-score against confidence")
    fig.tight_layout(); fig.savefig(FIG / "fig3_7_pr_f1.png", dpi=200); plt.close(fig)


def fig_confusion_img(ev):
    fig, ax = plt.subplots(1, 2, figsize=(7, 3.2))
    for a, (k, t) in zip(ax, (("pretrained", "Pretrained YOLO11n"), ("finetuned", "Fine-tuned YOLO11n"))):
        e = ev[f"{k}/voc_test"]; m = np.array([[e["img_without"] - e["img_flagged"], e["img_flagged"]], [e["img_missed"], e["img_with"] - e["img_missed"]]])
        a.imshow(m, cmap="Blues"); a.set_xticks([0, 1], ["no person", "person"]); a.set_yticks([0, 1], ["no person", "person"]); a.set_xlabel("Predicted"); a.set_ylabel("Actual"); a.set_title(t)
        for i in range(2):
            for j in range(2): a.text(j, i, int(m[i, j]), ha="center", va="center", color="white" if m[i, j] > m.max() / 2 else "black", fontsize=12)
        a.spines[:].set_visible(False)
    fig.tight_layout(); fig.savefig(FIG / "fig3_8_confusion_images.png", dpi=200); plt.close(fig)


def fig_size(ev):
    fig, ax = plt.subplots(figsize=(6, 3.5)); bins = list(ev["pretrained/african"]["recall_by_size"].keys()); x = np.arange(len(bins)); w = 0.38
    for off, key, col, lab in ((-w / 2, "pretrained/african", BLUE, "African set"), (w / 2, "pretrained/control", LBLUE, "Control set")):
        d = ev[key]["recall_by_size"]; r = np.array([d[b]["hit"] / max(d[b]["n"], 1) * 100 for b in bins]); lo = np.array([d[b]["ci"][0] * 100 for b in bins]); hi = np.array([d[b]["ci"][1] * 100 for b in bins])
        ax.bar(x + off, r, w, color=col, label=f"{lab}", yerr=[r - lo, hi - r], capsize=3, ecolor=GREY)
        for xi, b in zip(x + off, bins): ax.text(xi, 2, f"n={d[b]['n']}", ha="center", fontsize=7, color="white" if col == BLUE else "black", rotation=90, va="bottom")
    ax.set_xticks(x, [f"{b} of image" for b in bins]); ax.set_ylabel("Recall at confidence 0.5 (%)"); ax.set_ylim(0, 105); ax.legend(); ax.set_xlabel("Person area as a share of the image")
    fig.tight_layout(); fig.savefig(FIG / "fig3_9_recall_by_size.png", dpi=200); plt.close(fig)


def pick_examples(n=4):
    from evalkit import match_all  # noqa
    P = pickle.loads((DATA / "pred_cache" / "pretrained_african_640.pkl").read_bytes()); F = pickle.loads((DATA / "pred_cache" / "finetuned_african_640.pkl").read_bytes())
    rows = []
    for p, f in zip(P, F):
        def tp(r):
            k = r["scores"] >= 0.5; b = r["boxes"][k]; m = iou(b, r["gt"]); used = set(); c = 0
            for i in np.argsort(-r["scores"][k]):
                j = [q for q in np.argsort(-m[i]) if q not in used and m[i, q] >= 0.5] if m.shape[1] else []
                if j: used.add(j[0]); c += 1
            return c
        rows.append((p["id"], len(p["gt"]), tp(p), tp(f)))
    return rows, P, F


def fig_examples(ids, P, F):
    fig, axs = plt.subplots(len(ids), 2, figsize=(9.2, 3.3 * len(ids)))
    for r, iid in enumerate(ids):
        p = next(x for x in P if x["id"] == iid); f = next(x for x in F if x["id"] == iid)
        im = cv2.cvtColor(cv2.imread(str(DATA / "oi_african" / "images" / f"{iid}.jpg")), cv2.COLOR_BGR2RGB)
        for c, (rec, t) in enumerate(((p, "Pretrained"), (f, "Fine-tuned"))):
            k = rec["scores"] >= 0.5; v = draw(im, rec["gt"], (34, 160, 34), dashed=True); v = draw(v, rec["boxes"][k], (220, 38, 38), scores=rec["scores"][k])
            axs[r, c].imshow(v); axs[r, c].axis("off"); axs[r, c].set_title(f"{t}: {int(k.sum())} detections, {len(rec['gt'])} annotated", fontsize=8)
    fig.tight_layout(); fig.savefig(FIG / "fig3_10_examples.png", dpi=200); plt.close(fig)


def fig_audio_examples(gun_path, other_path, other_label, thunder_path):
    import soundfile as sf
    fig, axs = plt.subplots(2, 3, figsize=(10, 4.4))
    for c, (p, t) in enumerate(((gun_path, "Gunshot (AK-47)"), (other_path, other_label), (thunder_path, "Thunderstorm"))):
        y, sr = librosa.load(p, sr=16000, mono=True); y = y[:int(16000 * 4)]
        axs[0, c].plot(np.arange(len(y)) / sr, y, color=BLUE, lw=0.5); axs[0, c].set_title(t); axs[0, c].set_xlabel("Time (s)"); axs[0, c].set_ylim(-1, 1)
        S = librosa.power_to_db(librosa.feature.melspectrogram(y=y, sr=sr, n_mels=64, fmax=8000), ref=np.max)
        librosa.display.specshow(S, sr=sr, x_axis="time", y_axis="mel", fmax=8000, ax=axs[1, c], cmap="magma"); axs[1, c].set_xlabel("Time (s)")
    axs[0, 0].set_ylabel("Amplitude"); fig.tight_layout(); fig.savefig(FIG / "fig3_5_audio_examples.png", dpi=200); plt.close(fig)


def fig_gunshot():
    from sklearn.metrics import precision_recall_curve, roc_curve
    d = np.load(OUT / "gunshot_scores.npz", allow_pickle=True); r = json.loads((OUT / "gunshot_results.json").read_text()); y = d["y"]
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.6))
    for s, lab, col in ((d["zero"], "YAMNet zero-shot", BLUE), (d["clf"], "YAMNet scores + logistic regression", RED)):
        p, rc, _ = precision_recall_curve(y, s); ax[0].plot(rc, p, color=col, label=lab); f, t, _ = roc_curve(y, s); ax[1].plot(f, t, color=col, label=lab)
    ax[0].set_xlabel("Recall"); ax[0].set_ylabel("Precision"); ax[0].set_title("Precision-recall"); ax[0].legend(loc="lower left", fontsize=7); ax[0].set_ylim(0, 1.02)
    ax[1].plot([0, 1], [0, 1], ls=":", color=GREY); ax[1].set_xlabel("False positive rate"); ax[1].set_ylabel("True positive rate"); ax[1].set_title("ROC")
    fig.tight_layout(); fig.savefig(FIG / "fig3_11_gunshot_curves.png", dpi=200); plt.close(fig)
    fig, ax = plt.subplots(1, 4, figsize=(13, 3.2))
    for a, (k, t) in zip(ax, (("zero_035", "Zero-shot, 0.35"), ("zero_train_thr", f"Zero-shot, {r['threshold_from_train']:.2f}"), ("clf_050", "Logistic regression, 0.50"), ("clf_cv_thr", f"Logistic regression, {r['threshold_clf_from_cv']:.2f}"))):
        e = r[k]; m = np.array([[e["tn"], e["fp"]], [e["fn"], e["tp"]]]); a.imshow(m, cmap="Blues"); a.set_xticks([0, 1], ["not gunshot", "gunshot"]); a.set_yticks([0, 1], ["not gunshot", "gunshot"]); a.set_title(t); a.set_xlabel("Predicted"); a.set_ylabel("Actual")
        for i in range(2):
            for j in range(2): a.text(j, i, int(m[i, j]), ha="center", va="center", color="white" if m[i, j] > m.max() / 2 else "black", fontsize=12)
        a.spines[:].set_visible(False)
    fig.tight_layout(); fig.savefig(FIG / "fig3_12_gunshot_confusion.png", dpi=200); plt.close(fig)
    fig, ax = plt.subplots(figsize=(5.4, 3.4)); snr = sorted(int(k) for k in r["noise"]); 
    ax.plot(snr, [r["noise"][str(s)]["zero"] * 100 for s in snr], marker="o", color=BLUE, label="Zero-shot (0.35)"); ax.plot(snr, [r["noise"][str(s)]["clf"] * 100 for s in snr], marker="s", color=RED, label="Logistic regression (0.50)"); ax.plot(snr, [r["noise"][str(s)]["clf_cv"] * 100 for s in snr], marker="^", color=GREY, label=f"Logistic regression ({r['threshold_clf_from_cv']:.2f})")
    ax.set_xlabel("Signal-to-noise ratio (dB)"); ax.set_ylabel("Gunshot recall (%)"); ax.set_ylim(0, 105); ax.legend(); fig.tight_layout(); fig.savefig(FIG / "fig3_13_noise.png", dpi=200); plt.close(fig)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    ev = json.loads((OUT / "person_eval.json").read_text()) if (OUT / "person_eval.json").exists() else None
    if what in ("curves", "all"): fig_curves()
    if what in ("eval", "all") and ev: fig_pr_f1(ev); fig_confusion_img(ev); fig_size(ev)
    if what in ("gun", "all"): fig_gunshot()
    if what in ("examples", "all"):
        _, P, F = pick_examples(); fig_examples(sys.argv[2].split(","), P, F)
