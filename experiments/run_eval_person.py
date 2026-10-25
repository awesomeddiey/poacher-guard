"""Evaluate pretrained and fine-tuned YOLO11n on VOC test and the three Open Images sets (Tables 3.5 and 3.6)."""
import json
import sys

from common import DATA, OUT
from evalkit import predict_set, summarise

PRE = "/home/user/poacher-guard/models/yolo11n.pt"
FT = str(DATA / "runs" / "person_ft" / "weights" / "best.pt")
SETS = {"voc_test": DATA / "voc_yolo" / "test", "african": DATA / "oi_african", "african_rural": DATA / "oi_african_rural", "control": DATA / "oi_control"}
cache = DATA / "pred_cache"; cache.mkdir(exist_ok=True)
res = {}
for mname, w in (("pretrained", PRE), ("finetuned", FT)):
    for dname, d in SETS.items():
        recs = predict_set(w, d, 640, cache / f"{mname}_{dname}_640.pkl")
        res[f"{mname}/{dname}"] = summarise(recs); print(mname, dname, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in res[f"{mname}/{dname}"].items() if k in ("n_images", "n_gt", "mAP50", "mAP50_95", "precision", "recall")}, flush=True)
if "--size512" in sys.argv:
    for mname, w in (("pretrained", PRE), ("finetuned", FT)):
        recs = predict_set(w, SETS["voc_test"], 512, cache / f"{mname}_voc_test_512.pkl"); res[f"{mname}/voc_test_512"] = summarise(recs)
(OUT / "person_eval.json").write_text(json.dumps(res, indent=1)); print("saved")
