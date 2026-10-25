import pandas as pd
from PIL import Image, ImageDraw
from common import DATA
oi = DATA / "oi"; c = pd.read_csv(oi / "african_candidates.csv").reset_index(drop=True)
out = DATA / "oi" / "sheets"; out.mkdir(exist_ok=True)
W, H, COLS, ROWS = 280, 210, 6, 4
for s in range(0, len(c), COLS * ROWS):
    sheet = Image.new("RGB", (W * COLS, H * ROWS), "white")
    for k, r in enumerate(c.iloc[s:s + COLS * ROWS].itertuples()):
        im = Image.open(oi / "images" / f"{r.ImageID}.jpg").convert("RGB"); im.thumbnail((W - 4, H - 4))
        x, y = (k % COLS) * W, (k // COLS) * H; sheet.paste(im, (x + 2, y + 2))
        d = ImageDraw.Draw(sheet); d.rectangle([x + 2, y + 2, x + 40, y + 18], fill="black"); d.text((x + 5, y + 4), str(s + k), fill="yellow")
    sheet.save(out / f"sheet_{s // (COLS * ROWS):02d}.jpg", quality=80)
print(len(c), "images,", (len(c) + 23) // 24, "sheets")
