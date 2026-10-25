"""Select Open Images photographs for the African test set and the control set (Section 3.4.1).

Step 1 (this script): filter person boxes, find candidate photographs whose Flickr title names a sub-Saharan
African country, people or place, keep those with person boxes that are not group boxes or depictions, draw a
random sample of 640 (seed 42) and download them from the Open Images S3 bucket.
Step 2 (finalize_openimages.py): after the visual review, write YOLO labels for the kept images and draw the
control set of the same size.
"""
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen

import pandas as pd

from common import DATA, OUT, PERSON_MID, SEED

OI = DATA / "oi"
SPLITS = {"train": ("train-images-boxable-with-rotation.csv", "oidv6-train-annotations-bbox.csv"),
          "validation": ("validation-images-with-rotation.csv", "validation-annotations-bbox.csv"),
          "test": ("test-images-with-rotation.csv", "test-annotations-bbox.csv")}
PLACES = ("zimbabw|kenya|tanzania|uganda|rwanda|burundi|malawi|zambia|mozambi|botswana|namibia|lesotho|swazi|eswatini|"
          "south africa|ghana|nigeria|senegal|mali\\b|burkina|cameroon|ethiopia|congo|masai|maasai|serengeti|ngorongoro|"
          "sierra leone|liberia|gambia|togo\\b|benin\\b|angola|madagascar|sudan|somali|eritrea|gabon|chad\\b|niger\\b|"
          "ivory coast|cote d|harare|bulawayo|nairobi|kampala|lagos|accra|dakar|bamako|kigali|zanzibar|kilimanjaro|"
          "okavango|kalahari|soweto|johannesburg|cape town|durban|himba|zulu|xhosa|samburu|sub-saharan|africa|swahili|"
          "malealea|mombasa|arusha|lusaka|lilongwe|maputo|windhoek|gaborone|maseru|addis|abuja|kinshasa|freetown|"
          "monrovia|ouagadougou|niamey|conakry|kikuyu|hausa|yoruba|ashanti|fulani|tuareg|bushmen|ugandan|kenyan|"
          "tanzanian|zambian|malawian|rwandan|ghanaian|nigerian|ethiopian|senegalese|malian|cameroonian|liberian")
NORTH = "north africa|morocco|egypt|tunisia|algeria|libya|marrakech|cairo|sahara|moroccan|egyptian|african american|african-american"


def person_boxes(split):
    f = OI / f"person_{split}.csv"
    if not f.exists():
        parts = [c[c.LabelName == PERSON_MID] for c in pd.read_csv(OI / SPLITS[split][1], chunksize=2_000_000)]
        pd.concat(parts).to_csv(f, index=False)
    return pd.read_csv(f)


def main():
    imgs, boxes = [], []
    for s, (icsv, _) in SPLITS.items():
        im = pd.read_csv(OI / icsv, usecols=["ImageID", "Subset", "License", "Author", "Title", "OriginalLandingURL"])
        imgs.append(im); boxes.append(person_boxes(s))
    im, bx = pd.concat(imgs), pd.concat(boxes)
    agg = bx.groupby("ImageID").agg(n=("XMin", "size"), grp=("IsGroupOf", "max"), dep=("IsDepiction", "max"))
    ok = agg[(agg.grp == 0) & (agg.dep == 0)]
    t = im.Title.fillna("").str.lower()
    afr = t.str.contains(PLACES, regex=True) & ~t.str.contains(NORTH, regex=True)
    cand = im[afr].merge(ok, left_on="ImageID", right_index=True)
    pool = im[~afr].merge(ok, left_on="ImageID", right_index=True)
    print("African-titled candidates:", len(cand), "| control pool:", len(pool))
    cand = cand.sample(n=min(640, len(cand)), random_state=SEED)
    cand.to_csv(OI / "african_candidates.csv", index=False); pool.to_csv(OI / "control_pool.csv", index=False)
    (OI / "images").mkdir(exist_ok=True)

    def dl(row):
        f = OI / "images" / f"{row.ImageID}.jpg"
        if not f.exists():
            try: f.write_bytes(urlopen(f"https://open-images-dataset.s3.amazonaws.com/{row.Subset}/{row.ImageID}.jpg", timeout=30).read())
            except Exception as e: print("fail", row.ImageID, e)
    with ThreadPoolExecutor(16) as ex: list(ex.map(dl, cand.itertuples()))
    print("downloaded", len(list((OI / "images").glob("*.jpg"))))


if __name__ == "__main__":
    main()
