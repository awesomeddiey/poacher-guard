# Chapter 3 experiments

Reproduces every number, table and figure of `docs/Chapter3_Research_Methodology_Full.docx`. Datasets are downloaded to `PG_DATA` (default `/tmp/claude-0/data`) and are not stored in this repository. Results go to `results/chapter3/`, figures to `docs/chapter3/figures/`.

| Step | Script | What it does |
|---|---|---|
| 1 | `prep_voc.py` | Builds the VOC 2007 person subsets (train 1,200 + 400 negatives, validation 300, test 1,000), seed 42 |
| 2 | `prep_openimages.py` | Finds African-titled Open Images photographs with person boxes and downloads a random 640 |
| 3 | `contact_sheets.py` | Numbered contact sheets used for the visual review |
| 4 | `finalize_openimages.py` | Applies the review (`keep_*.txt`), the strict title rule, and draws the control set |
| 5 | `train_person.py` | Fine-tunes YOLO11n (COCO head kept), 512 px, AdamW 0.001, seed 42, 48-minute CPU budget |
| 6 | `train_person_headreplace.py` | One-epoch run with a new single-class head (abandoned approach) |
| 7 | `run_eval_person.py --size512` | Evaluates pretrained and fine-tuned models on VOC test and the Open Images sets |
| 8 | `gunshot_experiment.py` | YAMNet zero-shot vs logistic regression; thresholds from training data; noise-mixing test |
| 9 | `prototype_tests.py 60` | Runs the real vision worker and alert engine on 3 s clips (software only) |
| 10 | `labelstudio_setup.py`, `shot_labelstudio.js` | Label Studio project and the annotation screenshot |
| 11 | `make_figures3.py all` and `docs/make_figures.py` | Figures |
| 12 | `docs/build_chapter3_full.py` | Builds the Word chapter (numbers are read from the JSON results) |

Metric code is in `evalkit.py` (checked against the Ultralytics validator: AP50 0.893 vs 0.895 on VOC test).
Needs: `pip install -r requirements.txt pandas librosa matplotlib python-docx`; Label Studio in a separate virtualenv.
