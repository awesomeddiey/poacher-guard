"""Train the custom gunshot classifier from your own recordings.

Folder layout:
    data/gunshot_audio/gunshot/*.wav    real gunshots (rifle, shotgun, from distance...)
    data/gunshot_audio/other/*.wav      everything else: wind, birds, vehicles, speech,
                                        thunder, branches snapping, fireworks, silence

Run:  python training/train_gunshot.py [folder]
Writes models/gunshot_head.joblib; the app uses it automatically on next start.
More and more varied 'other' clips = fewer false alarms.
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.audio import SR, WIN, YamNet  # noqa: E402

DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "gunshot_audio"


def load(path):
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    x = x.mean(1)
    if sr != SR:
        from math import gcd
        g = gcd(sr, SR)
        x = resample_poly(x, SR // g, sr // g).astype(np.float32)
    return x


def windows(x, hop=WIN // 2):
    if len(x) < WIN:
        yield np.pad(x, (0, WIN - len(x)))
        return
    for i in range(0, len(x) - WIN + 1, hop):
        yield x[i:i + WIN]


def main():
    yam = YamNet(ROOT / "models" / "yamnet.tflite")
    X, y = [], []
    for label, cls in (("other", 0), ("gunshot", 1)):
        files = sorted((DATA / label).glob("*.wav"))
        if not files:
            sys.exit(f"No .wav files in {DATA / label}")
        for f in files:
            for w in windows(load(f)):
                X.append(yam.run(w)[0]); y.append(cls)
        print(f"{label}: {len(files)} files")
    X, y = np.array(X), np.array(y)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, stratify=y, random_state=0)
    clf = LogisticRegression(max_iter=2000, class_weight="balanced", C=2.0).fit(Xtr, ytr)
    print(classification_report(yte, clf.predict(Xte), target_names=["other", "gunshot"]))
    joblib.dump(clf, ROOT / "models" / "gunshot_head.joblib")
    print("saved models/gunshot_head.joblib - set audio.threshold ~0.6 for the custom head")


if __name__ == "__main__":
    main()
