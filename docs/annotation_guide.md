# Annotation guide (poacher detection model)

Use CVAT, labelImg or Roboflow. Export in **YOLO format**. Keep one `.txt` per image beside the `.jpg`
in `data/poacher_dataset/raw/`.

## Classes
| id | name | draw a box around |
|---|---|---|
| 0 | person | every visible human, head to feet (or to the visible edge when cropped or hidden) |
| 1 | weapon | a rifle, shotgun, axe or machete held or carried. Use **props or replicas only** (see ethics) |

The model labels what is visible. It never labels "poacher" or "ranger". That decision is made by the
alert engine from the BLE ranger tag. Never label, group or filter people by race, skin tone or identity.

## Rules
1. Box every person who is at least 30 % visible, including people far away, in shade, in tall grass or partly behind trees.
2. Boxes are tight: the edge touches the body or clothing, with no large gaps.
3. Do not box reflections, posters, statues or shadows.
4. When two people overlap, draw two overlapping boxes.
5. Blurry or night-IR frames are kept. Delete a frame only if no human can be recognised by an annotator.
6. Weapons: box the whole weapon, including the part held by the person.

## Workflow
1. `python training/prelabel.py` drafts the person boxes. Pre-labels are drafts only.
2. An annotator reviews EVERY image and corrects boxes, adds weapons and deletes wrong boxes.
3. Count: images reviewed, boxes accepted unchanged, boxes moved or resized, boxes deleted, boxes added (report the correction rate).
4. Quality check: a second annotator independently re-labels a random 10 % of images. Report the mean IoU of matched boxes and the number of disagreements.
5. Take the **annotation screenshots** while working: (a) the tool with the pre-labels loaded, (b) the same image after correction, (c) the class list, (d) an image with a weapon box.
6. `python training/split_dataset.py` then splits by volunteer.
