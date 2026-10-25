# Which output goes into which figure or table

Run the scripts in this order from the `poacher-guard` folder. Every file is produced by a script, so nothing is typed by hand.
The yellow placeholders in `Chapter3_Research_Methodology.docx` mark every place that needs your real data.

| Step | Command | Output | Goes into |
|---|---|---|---|
| 0 | Print and sign `docs/consent_form_template.md` with every volunteer | signed forms | Section 3.13, ethics appendix |
| 1 | `python training/collect_frames.py --tag dusk --subject s01` (repeat per condition and volunteer) | `data/poacher_dataset/raw/*.jpg` | Figure 3.2 (sample frames per condition) |
| 2 | `python training/prelabel.py`, then correct every image in CVAT or labelImg (`docs/annotation_guide.md`) | label `.txt` files | Figures 3.3 and 3.4 (screenshots of the tool before and after), Table 3.4 |
| 3 | `python training/split_dataset.py` | `results/dataset_stats.png`, `.json` | Figure 3.5, Table 3.3 |
| 4 | `python training/train_poacher.py` | `runs/poacher/results.png`, `confusion_matrix.png`, `PR_curve.png`, `val_batch*_pred.jpg` | Figure 3.6; the other plots go to Chapter 4 |
| 5 | `python training/evaluate_vision.py --weights runs/poacher/weights/best.pt --baseline models/yolo11n.pt` | `results/vision_results.md/json`, `predictions_grid.jpg` | Chapter 4 tables and figure (fine-tuned vs pretrained, per condition, per volunteer) |
| 6 | Put gunshot and other WAV files in `data/gunshot_audio/{gunshot,other}`, then `python training/train_gunshot.py` | `results/gunshot_results.json`, `gunshot_roc.png`, `gunshot_confusion_*.png`, `gunshot_threshold.png` | Table 3.6 and Chapter 4 |
| 7 | BLE range and authorisation tests (Section 3.7) | your own tables | Chapter 4 |
| 8 | Staged scenarios of Table 3.7 | your own counts and delays | Chapter 4 |
| 9 | Run `python run.py`, then `node tools/capture_screenshots.js` | `results/screens/*.png` | Figure 3.8 |

Rebuild the chapter after editing the text: `python docs/build_chapter3.py` (also prints a CUT style check).
CUT places results in Chapter 4. Do not copy a number from the scripts into the text until the run uses your real dataset.
