"""After the visual review: write the African test set (kept indices) and draw the control set.

African set = reviewed candidates listed in keep_*.txt (indices into african_candidates.csv).
Rural/bush subset = indices in rural.txt. Control = random photographs with no African place in the title, same filters,
same split balance as the African set (seed 42). Labels are all person boxes (none are group boxes or depictions).
"""
import html
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen

import pandas as pd

from common import DATA, OUT, PERSON_MID, SEED

oi = DATA / "oi"
keep = sorted({int(x) for f in oi.glob("keep_*.txt") for x in f.read_text().split()})
rural = {int(x) for x in (oi / "rural.txt").read_text().split()}
cand = pd.read_csv(oi / "african_candidates.csv").reset_index(drop=True)
afr = cand.iloc[keep].copy(); afr["rural"] = [i in rural for i in keep]
# Strict rule: the title must name a specific African country, city, region or people. A title that only says
# "Africa" or "African" can describe an event on another continent, so those images are dropped.
SPECIFIC = re.compile(r"zimbabw|kenya|tanzania|uganda|rwanda|burundi|malawi|zambia|mozambi|botswana|namibia|lesotho|swazi|eswatini|south africa|ghana|nigeria|senegal|mali\b|burkina|cameroon|ethiopia|congo|masai|maasai|serengeti|ngorongoro|sierra leone|liberia|gambia|togo\b|benin\b|angola|madagascar|sudan|somali|eritrea|gabon|chad\b|niger\b|ivory coast|cote d|harare|bulawayo|nairobi|kampala|lagos|accra|dakar|bamako|kigali|zanzibar|kilimanjaro|okavango|kalahari|soweto|johannesburg|cape town|durban|himba|zulu|xhosa|samburu|swahili|malealea|mombasa|arusha|lusaka|lilongwe|maputo|windhoek|gaborone|maseru|addis|abuja|kinshasa|freetown|monrovia|ouagadougou|niamey|conakry|kikuyu|hausa|yoruba|ashanti|fulani|tuareg|ugandan|kenyan|tanzanian|zambian|malawian|rwandan|ghanaian|nigerian|ethiopian|senegalese|malian|cameroonian|liberian", re.I)
n_before = len(afr); afr = afr[afr.Title.fillna("").map(html.unescape).map(lambda t: bool(SPECIFIC.search(t)))]; print("reviewed", n_before, "-> after strict title rule", len(afr))
pool = pd.read_csv(oi / "control_pool.csv")
n = len(afr)
split_counts = afr.Subset.value_counts()
ctrl = pd.concat([pool[pool.Subset == s].sample(n=int(c), random_state=SEED) for s, c in split_counts.items()])
boxes = pd.concat([pd.read_csv(oi / f"person_{s}.csv") for s in ("train", "validation", "test")])


def download(row):
    f = oi / "images" / f"{row.ImageID}.jpg"
    if not f.exists():
        f.write_bytes(urlopen(f"https://open-images-dataset.s3.amazonaws.com/{row.Subset}/{row.ImageID}.jpg", timeout=60).read())


def build(df, name):
    d = DATA / name; (d / "images").mkdir(parents=True, exist_ok=True); (d / "labels").mkdir(exist_ok=True)
    with ThreadPoolExecutor(16) as ex: list(ex.map(download, df.itertuples()))
    b = boxes[boxes.ImageID.isin(set(df.ImageID))]
    nb = 0
    for r in df.itertuples():
        link = d / "images" / f"{r.ImageID}.jpg"
        if not link.exists(): link.symlink_to(oi / "images" / f"{r.ImageID}.jpg")
        rows = b[b.ImageID == r.ImageID]
        lines = [f"0 {(x0 + x1) / 2:.6f} {(y0 + y1) / 2:.6f} {x1 - x0:.6f} {y1 - y0:.6f}\n" for x0, x1, y0, y1 in zip(rows.XMin, rows.XMax, rows.YMin, rows.YMax)]
        (d / "labels" / f"{r.ImageID}.txt").write_text("".join(lines)); nb += len(lines)
    return nb


s = {"african": {"images": len(afr), "boxes": build(afr, "oi_african")}}
rur = afr[afr.rural]; s["african_rural"] = {"images": len(rur), "boxes": int(boxes[boxes.ImageID.isin(set(rur.ImageID))].shape[0])}
(DATA / "oi_african_rural").mkdir(exist_ok=True)
for sub in ("images", "labels"):
    (DATA / "oi_african_rural" / sub).mkdir(exist_ok=True)
    for r in rur.itertuples():
        src = DATA / "oi_african" / sub / f"{r.ImageID}.{'jpg' if sub == 'images' else 'txt'}"
        dst = DATA / "oi_african_rural" / sub / src.name
        if not dst.exists(): dst.symlink_to(src)
s["control"] = {"images": len(ctrl), "boxes": build(ctrl, "oi_control")}
s["source_splits_african"] = {k: int(v) for k, v in split_counts.items()}
afr.to_csv(OUT / "african_test_set.csv", index=False); ctrl.to_csv(OUT / "control_test_set.csv", index=False)
import json; (OUT / "openimages_summary.json").write_text(json.dumps(s, indent=2)); print(json.dumps(s, indent=1))
