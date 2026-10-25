"""Gunshot detector experiment (Sections 3.4.2, 3.6.2, 3.8.2): zero-shot YAMNet against YAMNet scores + logistic regression.

Data: Gunshot Audio Dataset clips (AK-12, AK-47, IMI Desert Eagle) as positives; ESC-50 clips as negatives.
Split by whole clips: ESC-50 fold 5 = test, folds 1 to 4 = train; 20 per cent of the clips of each gun class = test.
The classifier is applied to every 0.975 s window (hop 0.5 s) as the prototype does, and a clip is flagged when its
highest window score reaches the threshold.
"""
import json
import pickle
from math import gcd
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf
from scipy.signal import resample_poly
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold

import sys
sys.path.insert(0, "/home/user/poacher-guard")
from app.audio import SR, WIN, YamNet  # noqa: E402
from common import DATA, OUT, SEED  # noqa: E402
from evalkit import wilson  # noqa: E402

GUN = Path("/home/user/harihara-valliappan/gun-classification-using-gunshot/Datas")
ESC = DATA / "esc50"
HOP = 8000  # 0.5 s
yam = YamNet("/home/user/poacher-guard/models/yamnet.tflite")
GUN_IDX = [i for i, l in enumerate(yam.labels) if l in ("Gunshot, gunfire", "Machine gun", "Fusillade", "Artillery fire", "Cap gun")]
assert len(GUN_IDX) == 5, GUN_IDX


def load(p):
    x, sr = sf.read(p, dtype="float32", always_2d=True); x = x.mean(1)
    if sr != SR: g = gcd(sr, SR); x = resample_poly(x, SR // g, sr // g).astype(np.float32)
    return x


def windows_scores(x):
    if len(x) < WIN: x = np.pad(x, (0, WIN - len(x)))
    return np.stack([yam.run(x[i:i + WIN])[0] for i in range(0, len(x) - WIN + 1, HOP)])


def build_index():
    rng = np.random.RandomState(SEED); rows = []
    for cls_dir in sorted(GUN.iterdir()):
        files = sorted(cls_dir.glob("*.wav")); idx = rng.permutation(len(files)); n_test = int(round(0.2 * len(files)))
        for k, i in enumerate(idx):
            rows.append(dict(path=str(files[i]), label=1, source=cls_dir.name, category=cls_dir.name, split="test" if k < n_test else "train"))
    esc = pd.read_csv(ESC / "esc50.csv")
    for r in esc.itertuples():
        rows.append(dict(path=str(ESC / "audio" / r.filename), label=0, source="ESC-50", category=r.category, split="test" if r.fold == 5 else "train"))
    return pd.DataFrame(rows)


def main():
    idx = build_index(); cache = DATA / "gun_feats.pkl"
    if cache.exists(): feats = pickle.loads(cache.read_bytes())
    else:
        feats = {}
        for n, r in enumerate(idx.itertuples()):
            feats[r.path] = windows_scores(load(r.path))
            if n % 300 == 0: print("features", n, "/", len(idx), flush=True)
        cache.write_bytes(pickle.dumps(feats))
    idx["n_windows"] = [len(feats[p]) for p in idx.path]
    idx.to_csv(OUT / "gunshot_index.csv", index=False)
    tr, te = idx[idx.split == "train"].reset_index(drop=True), idx[idx.split == "test"].reset_index(drop=True)

    def win_xy(df):
        X = np.concatenate([feats[p] for p in df.path]); y = np.concatenate([[l] * len(feats[p]) for p, l in zip(df.path, df.label)])
        return X, y
    def clip_scores_zero(df): return np.array([feats[p][:, GUN_IDX].max() for p in df.path])
    def clip_scores_clf(df, clf): return np.array([clf.predict_proba(feats[p])[:, 1].max() for p in df.path])

    # ---- model selection on the training split only ----
    best = None; skf = StratifiedKFold(5, shuffle=True, random_state=SEED); cv = {}
    for C in (0.01, 0.1, 1, 10, 100):
        aps = []
        for a, b in skf.split(tr.path, tr.label):
            clf = LogisticRegression(C=C, class_weight="balanced", max_iter=3000).fit(*win_xy(tr.iloc[a]))
            aps.append(average_precision_score(tr.label.iloc[b], clip_scores_clf(tr.iloc[b], clf)))
        cv[C] = float(np.mean(aps))
        if best is None or cv[C] > best[1]: best = (C, cv[C])
    print("CV", cv, "best", best, flush=True)
    clf = LogisticRegression(C=best[0], class_weight="balanced", max_iter=3000).fit(*win_xy(tr))
    # threshold for the classifier chosen on out-of-fold training scores only (maximum F1)
    oof = np.zeros(len(tr))
    for a, b in skf.split(tr.path, tr.label):
        c_ = LogisticRegression(C=best[0], class_weight="balanced", max_iter=3000).fit(*win_xy(tr.iloc[a])); oof[b] = clip_scores_clf(tr.iloc[b], c_)
    f1c = []
    for t in np.linspace(0.01, 0.99, 99):
        p_ = oof >= t; tp_ = (p_ & (tr.label == 1)).sum(); fp_ = (p_ & (tr.label == 0)).sum(); fn_ = ((~p_) & (tr.label == 1)).sum(); f1c.append(2 * tp_ / max(2 * tp_ + fp_ + fn_, 1))
    t_clf = float(np.linspace(0.01, 0.99, 99)[int(np.argmax(f1c))])
    s_tr0 = clip_scores_zero(tr)
    ths = np.linspace(0.01, 0.99, 99); f1s = []
    for t in ths:
        p = s_tr0 >= t; tp = (p & (tr.label == 1)).sum(); fp = (p & (tr.label == 0)).sum(); fn = ((~p) & (tr.label == 1)).sum()
        f1s.append(2 * tp / max(2 * tp + fp + fn, 1))
    t_train = float(ths[int(np.argmax(f1s))])

    def metrics(y, s, t):
        p = s >= t; tp = int((p & (y == 1)).sum()); fp = int((p & (y == 0)).sum()); fn = int(((~p) & (y == 1)).sum()); tn = int(((~p) & (y == 0)).sum())
        pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
        return dict(threshold=float(t), tp=tp, fp=fp, fn=fn, tn=tn, precision=pr, recall=rc, f1=2 * pr * rc / max(pr + rc, 1e-9), fpr=fp / max(fp + tn, 1),
                    recall_ci=wilson(tp, tp + fn), fpr_ci=wilson(fp, fp + tn), ap=float(average_precision_score(y, s)), auc=float(roc_auc_score(y, s)))
    y_te = te.label.values
    s_zero, s_clf = clip_scores_zero(te), clip_scores_clf(te, clf)
    res = {"cv_ap_by_C": cv, "chosen_C": best[0], "threshold_from_train": t_train,
           "counts": {"train_gun": int((tr.label == 1).sum()), "train_other": int((tr.label == 0).sum()), "test_gun": int((te.label == 1).sum()), "test_other": int((te.label == 0).sum()),
                      "per_gun_class_train": tr[tr.label == 1].source.value_counts().to_dict(), "per_gun_class_test": te[te.label == 1].source.value_counts().to_dict()},
           "zero_035": metrics(y_te, s_zero, 0.35), "zero_train_thr": metrics(y_te, s_zero, t_train), "clf_050": metrics(y_te, s_clf, 0.5), "clf_cv_thr": metrics(y_te, s_clf, t_clf), "threshold_clf_from_cv": t_clf,
           "train_clf_errors": int(((clip_scores_clf(tr, clf) >= 0.5) != (tr.label == 1)).sum())}
    # false alarms by category
    te["zero"], te["clf"], te["clfcv"] = s_zero >= 0.35, s_clf >= 0.5, s_clf >= t_clf
    neg = te[te.label == 0].groupby("category").agg(clips=("path", "size"), zero=("zero", "sum"), clf=("clf", "sum"), clfcv=("clfcv", "sum")).sort_values(["zero", "clf"], ascending=False)
    res["false_alarms_by_category"] = neg.reset_index().to_dict("records")
    miss = te[(te.label == 1) & (~te.clf)]; res["clf_missed_gun_clips"] = miss.source.tolist()
    np.savez(OUT / "gunshot_scores.npz", y=y_te, zero=s_zero, clf=s_clf, cats=te.category.values, paths=te.path.values)

    # ---- noise-mixing test ----
    rng = np.random.RandomState(SEED)
    bush = ["rain", "wind", "crickets", "insects", "chirping_birds", "frog", "crackling_fire", "sheep", "cow", "rooster", "sea_waves", "water_drops", "thunderstorm"][:10]
    bush = ["rain", "wind", "crickets", "insects", "chirping_birds", "frog", "crackling_fire", "sheep", "cow", "rooster"]
    bg_pool = te[(te.label == 0) & (te.category.isin(bush))].path.tolist()
    guns = te[te.label == 1].path.tolist(); noise_res = {}
    bgs = {g: load(bg_pool[rng.randint(len(bg_pool))]) for g in guns}
    offs = {g: rng.randint(0, 20000) for g in guns}
    for snr in (20, 10, 0, -10):
        hit_z = hit_c = hit_cv = 0
        for g in guns:
            x = load(g); b = bgs[g]; L = max(len(b), len(x) + offs[g] + 1000); bb = np.zeros(L, np.float32); bb[:len(b)] = np.tile(b, int(np.ceil(L / len(b))))[:L]
            px, pb = np.mean(x ** 2), np.mean(b ** 2); gain = np.sqrt(px / (pb * 10 ** (snr / 10) + 1e-12))
            mix = bb * gain; o = offs[g]; mix[o:o + len(x)] += x
            w = windows_scores(mix.astype(np.float32))
            hit_z += w[:, GUN_IDX].max() >= 0.35; pc = clf.predict_proba(w)[:, 1].max(); hit_c += pc >= 0.5; hit_cv += pc >= t_clf
        noise_res[snr] = dict(zero=hit_z / len(guns), clf=hit_c / len(guns), clf_cv=hit_cv / len(guns), n=len(guns))
    res["noise"] = noise_res
    (OUT / "gunshot_results.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({k: res[k] for k in ("chosen_C", "threshold_from_train", "zero_035", "zero_train_thr", "clf_050", "clf_cv_thr", "threshold_clf_from_cv", "noise", "counts")}, indent=1, default=float))


if __name__ == "__main__":
    main()
