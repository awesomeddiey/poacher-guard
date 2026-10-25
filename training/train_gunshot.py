"""Train and evaluate the gunshot detection model from your own recordings.

Folder layout:
    data/gunshot_audio/gunshot/*.wav    real gunshots (rifle, shotgun, near and far)
    data/gunshot_audio/other/*.wav      wind, birds, vehicles, speech, thunder, branches, fireworks, silence

    python training/train_gunshot.py [folder]

Files (not windows) are split into train and test so the score reflects unseen recordings.
Writes models/gunshot_head.joblib and, in results/: gunshot_results.json, gunshot_confusion.png,
gunshot_roc.png and gunshot_threshold.png. The zero-shot YAMNet score (no training) is evaluated on
the same test files as the baseline.
"""
import json
import sys
from math import gcd
from pathlib import Path

import joblib
import matplotlib
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import ConfusionMatrixDisplay, auc, confusion_matrix, precision_recall_fscore_support, roc_curve
from sklearn.model_selection import train_test_split

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.audio import SR, WIN, YamNet  # noqa: E402

DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "gunshot_audio"
OUT = ROOT / "results"; OUT.mkdir(exist_ok=True)
GUN_IDX = [421, 422, 423, 424, 425]  # YAMNet classes: gunshot, machine gun, fusillade, artillery, cap gun


def load(path):
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    x = x.mean(1)
    if sr != SR:
        g = gcd(sr, SR)
        x = resample_poly(x, SR // g, sr // g).astype(np.float32)
    return x


def windows(x, hop=WIN // 2):
    if len(x) < WIN:
        yield np.pad(x, (0, WIN - len(x))); return
    for i in range(0, len(x) - WIN + 1, hop):
        yield x[i:i + WIN]


def feats(yam, files):
    X, y = [], []
    for f, cls in files:
        for w in windows(load(f)):
            X.append(yam.run(w)[0]); y.append(cls)
    return np.array(X), np.array(y)


def main():
    yam = YamNet(ROOT / "models" / "yamnet.tflite")
    files = []
    for label, cls in (("other", 0), ("gunshot", 1)):
        fs = sorted((DATA / label).glob("*.wav"))
        if len(fs) < 4:
            sys.exit(f"Need at least 4 .wav files in {DATA / label}")
        files += [(f, cls) for f in fs]
        print(f"{label}: {len(fs)} files")
    tr, te = train_test_split(files, test_size=0.25, stratify=[c for _, c in files], random_state=0)
    Xtr, ytr = feats(yam, tr); Xte, yte = feats(yam, te)
    clf = LogisticRegression(max_iter=2000, class_weight="balanced", C=2.0).fit(Xtr, ytr)
    p_custom = clf.predict_proba(Xte)[:, 1]
    p_zero = Xte[:, GUN_IDX].max(1)  # zero-shot baseline
    res = {"train_files": len(tr), "test_files": len(te), "train_windows": int(len(ytr)), "test_windows": int(len(yte)), "models": {}}
    fig, axr = plt.subplots(figsize=(4.6, 4))
    for name, p, thr in (("custom_head", p_custom, 0.6), ("zero_shot_yamnet", p_zero, 0.35)):
        pred = (p >= thr).astype(int)
        pr, rc, f1, _ = precision_recall_fscore_support(yte, pred, average="binary", zero_division=0)
        fpr, tpr, _ = roc_curve(yte, p)
        tn, fp, fn, tp = confusion_matrix(yte, pred, labels=[0, 1]).ravel()
        res["models"][name] = {"threshold": thr, "precision": round(pr, 4), "recall": round(rc, 4), "f1": round(f1, 4),
                               "auc": round(auc(fpr, tpr), 4), "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}
        axr.plot(fpr, tpr, label=f"{name} (AUC {auc(fpr, tpr):.2f})")
        ConfusionMatrixDisplay(confusion_matrix(yte, pred, labels=[0, 1]), display_labels=["other", "gunshot"]).plot(cmap="Blues", colorbar=False)
        plt.title(f"{name}, threshold {thr}"); plt.tight_layout(); plt.savefig(OUT / f"gunshot_confusion_{name}.png", dpi=200); plt.close()
    axr.plot([0, 1], [0, 1], "--", color="#94a3b8"); axr.set_xlabel("False positive rate"); axr.set_ylabel("True positive rate"); axr.legend(loc="lower right")
    fig.tight_layout(); fig.savefig(OUT / "gunshot_roc.png", dpi=200); plt.close(fig)
    ths = np.linspace(0.05, 0.95, 19); f, ax = plt.subplots(figsize=(5.4, 3.6))
    for lab, fn_ in (("precision", lambda pr_: precision_recall_fscore_support(yte, pr_, average="binary", zero_division=0)[0]),
                     ("recall", lambda pr_: precision_recall_fscore_support(yte, pr_, average="binary", zero_division=0)[1])):
        ax.plot(ths, [fn_((p_custom >= t).astype(int)) for t in ths], label=lab)
    ax.set_xlabel("Alert threshold (custom head)"); ax.legend(); f.tight_layout(); f.savefig(OUT / "gunshot_threshold.png", dpi=200); plt.close(f)
    (OUT / "gunshot_results.json").write_text(json.dumps(res, indent=2))
    joblib.dump(clf, ROOT / "models" / "gunshot_head.joblib")
    print(json.dumps(res, indent=1)); print("Saved models/gunshot_head.joblib and results/gunshot_*")


if __name__ == "__main__":
    main()
