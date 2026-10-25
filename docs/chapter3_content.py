# Chapter 3 content. Item types: h1, h2, p, table, fig (real image), slot (figure still to be produced).
FIG = "chapter3/figures/"

C = []
def h1(t): C.append(("h1", t))
def h2(t): C.append(("h2", t))
def p(t): C.append(("p", t))
def table(cap, head, rows, widths=None): C.append(("table", cap, head, rows, widths))
def fig(cap, path): C.append(("fig", cap, path))
def slot(cap, how): C.append(("slot", cap, how))

h1("Chapter 3: Research methodology")

h2("3.0 Introduction")
p("This chapter describes how the real-time anti-poaching detection and ranger alert system was designed, trained and tested. The system combines a poacher detection model that reads webcam images, a gunshot detection model that reads laptop microphone audio, a Bluetooth Low Energy (BLE) ranger tag check, an ESP32 flame sensing node and a web dashboard hosted on the base station laptop. The chapter presents the research philosophy, approach and design, the hardware and software used, the collection and annotation of the image data, the training of both models, the evaluation procedures and the ethical safeguards applied to the volunteers who were photographed.")
p("The measurements produced by these procedures are reported in Chapter 4. Every figure in this chapter that shows a tool or a training output was captured from the working system. The source code, the training scripts and the evaluation scripts are stored in the poacher-guard folder of the project repository (awesomeddiey/Hazvinei-deploy) and are listed in [SUPERVISOR CONFIRMATION REQUIRED: appendix number].")

h2("3.1 Research philosophy")
p("A pragmatist philosophy was adopted because the study required a working artefact that detects intruders and measurable evidence that the artefact performs acceptably in the field. Detection accuracy, alert delay and false alarm rates were treated as objective quantities that could be measured on held-out data. Choices about alert rules, dashboard content and the use of ranger tags were guided by what rangers need to act on an alert quickly [CITATION REQUIRED].")

h2("3.2 Research approach")
p("A quantitative approach was followed. Both detection models were evaluated with numerical metrics (precision, recall, F1 score and mean average precision) calculated on recordings and images that were never used for training. The integrated system was evaluated with counted outcomes, such as the number of correct alerts out of the number of staged intrusions and with measured delays in seconds.")

h2("3.3 Research design")
p("An experimental design within a design and development approach was adopted because the study produced a prototype and then tested it under controlled conditions [CITATION REQUIRED]. Four stages were followed. Requirements were derived from the problem statement in Chapter 1 and the prototype was built from the components described in Section 3.4. Each model was then trained and evaluated separately on held-out data. The complete system was finally tested with staged scenarios at [DETAIL REQUIRED: test site], and a stage was repeated when a test showed that a component needed revision.")

h2("3.4 System architecture")
h2("3.4.1 Hardware")
p("The base station was a laptop that ran both detection models, the BLE scanner, the alert engine and the dashboard server. The laptop used its built-in microphone for audio and a USB webcam configured at a resolution of 640 by 480 pixels for video. Two ESP32 development boards were used as field devices. One board carried a flame sensor module and sent readings to the base station over Wi-Fi. The other board was programmed as a ranger tag that advertises a fixed BLE name. Table 3.1 lists the components.")
table("Table 3.1: Hardware components", ["Component", "Specification", "Function"], [
    ["Laptop (base station)", "[DETAIL REQUIRED: make, processor, memory, operating system]", "Runs models, BLE scanner, alert engine and dashboard"],
    ["Webcam", "[DETAIL REQUIRED: model]; 640 x 480 pixels", "Video input for the poacher detection model"],
    ["Microphone", "Laptop built-in; sampled at 16 kHz, mono", "Audio input for the gunshot detection model"],
    ["ESP32 flame node", "ESP32 board with flame sensor module (analogue pin GPIO34, digital pin GPIO27)", "Fire detection and heartbeat over Wi-Fi"],
    ["ESP32 ranger tag", "ESP32 board advertising the name RANGER-R001", "Identifies an authorised ranger by BLE"],
    ["Wi-Fi router", "[DETAIL REQUIRED: model]", "Network link between the flame node and the base station"],
], [1.6, 2.8, 2.1])

h2("3.4.2 Software environment")
p("The base station software was written in Python. The poacher detection model used the Ultralytics YOLO11n implementation [CITATION REQUIRED] with OpenCV for video capture. The gunshot detection model used the YAMNet audio classifier [CITATION REQUIRED] executed through the TensorFlow Lite runtime, with scikit-learn for the classifier. BLE advertisements were read with the Bleak library. The dashboard server used FastAPI with a WebSocket channel, alerts were stored in a SQLite database and the map used the Leaflet library. The ESP32 firmware was written in the Arduino framework. Table 3.2 gives the versions used.")
table("Table 3.2: Software used", ["Software", "Version", "Purpose"], [
    ["Python", "[DETAIL REQUIRED: run python --version]", "Base station programs"],
    ["Ultralytics (YOLO11n)", "[DETAIL REQUIRED: pip show ultralytics]", "Person and weapon detection"],
    ["OpenCV", "[DETAIL REQUIRED]", "Camera capture and image handling"],
    ["YAMNet (TFLite) with ai-edge-litert", "[DETAIL REQUIRED]", "Audio class scores"],
    ["scikit-learn", "[DETAIL REQUIRED]", "Gunshot classifier and metrics"],
    ["Bleak", "[DETAIL REQUIRED]", "BLE scanning"],
    ["FastAPI and Uvicorn", "[DETAIL REQUIRED]", "Dashboard server and WebSocket"],
    ["Arduino core for ESP32", "[DETAIL REQUIRED]", "Flame node and ranger tag firmware"],
], [2.2, 2.4, 1.9])

h2("3.4.3 Data flow")
p("Figure 3.1 shows how data moved through the system. Webcam frames passed to the poacher detection model, microphone audio passed to the gunshot detection model and BLE advertisements passed to the ranger tag registry. The flame node posted its readings to the base station over Wi-Fi. The alert engine combined these inputs, applied the rules described in Section 3.9 and sent each alert to the SQLite log, to the web dashboard and, where configured, to a Telegram group used by the rangers.")
fig("Figure 3.1: System architecture of the anti-poaching detection system", FIG + "fig3_1_architecture.png")

h2("3.5 Poacher detection model")
h2("3.5.1 Study population and image data")
p("The model was required to detect human presence in camera images of the protected areas where the system is intended to operate in Zimbabwe. General-purpose detectors are trained on public image collections whose composition may not match the people found in and around these areas [CITATION REQUIRED]. Detection performance on local people therefore could not be assumed and was measured. The study population was adult volunteers recruited from [POPULATION REQUIRED: for example students and staff of Chinhoyi University of Technology and serving rangers]. The volunteers were Black adults from [DETAIL REQUIRED: community or country], which matches the people expected at the intended sites [DETAIL REQUIRED: number of volunteers, age range and gender balance].")
p("The detection classes described what is visible in the image and nothing else. The class person was applied to every human and the class weapon was applied to rifles, axes and machetes. No class was based on skin tone, ethnicity or identity. The model did not decide whether a person was a poacher. That decision was made by the alert engine from the ranger tag evidence, as described in Section 3.9.")

h2("3.5.2 Sampling procedure and sample size")
p("Volunteers were selected by purposive sampling because the images had to cover the conditions under which the camera would operate. Each volunteer was photographed under the conditions listed in Table 3.3, which were chosen to include the situations in which a person is most likely to be missed: dusk and night, tall grass, partial hiding behind trees, long distance and different clothing. The final dataset contained [SAMPLE SIZE REQUIRED: total images] images of [SAMPLE SIZE REQUIRED: number of volunteers] volunteers.")
table("Table 3.3: Composition of the image dataset by capture condition and split", ["Condition", "Train", "Validation", "Test", "Total"], [
    ["day-open", "[DATA REQUIRED]", "[DATA REQUIRED]", "[DATA REQUIRED]", "[DATA REQUIRED]"],
    ["dusk", "[DATA REQUIRED]", "[DATA REQUIRED]", "[DATA REQUIRED]", "[DATA REQUIRED]"],
    ["night-ir", "[DATA REQUIRED]", "[DATA REQUIRED]", "[DATA REQUIRED]", "[DATA REQUIRED]"],
    ["bush (tall grass and trees)", "[DATA REQUIRED]", "[DATA REQUIRED]", "[DATA REQUIRED]", "[DATA REQUIRED]"],
    ["occluded", "[DATA REQUIRED]", "[DATA REQUIRED]", "[DATA REQUIRED]", "[DATA REQUIRED]"],
    ["Total images", "[DATA REQUIRED]", "[DATA REQUIRED]", "[DATA REQUIRED]", "[DATA REQUIRED]"],
], [2.2, 1.0, 1.1, 1.0, 1.0])

h2("3.5.3 Image collection")
p("Frames were captured with the same webcam, resolution and mounting height as in deployment so that the training images matched the images seen in operation. A capture script saved one frame every second while a volunteer walked, stood, crouched and carried props in front of the camera. File names recorded the condition and an anonymous volunteer code in the form condition_subject_index, for example dusk_s04_0012.jpg. Weapon images were taken with props or replicas only. Collection took place at [DETAIL REQUIRED: locations and dates].")
slot("Figure 3.2: Sample frames from each capture condition", "Make a 2 by 3 montage of one consented frame per condition (day-open, dusk, night-ir, bush, occluded). Use only volunteers who ticked the face-in-dissertation box on the consent form, otherwise blur the faces.")

h2("3.5.4 Annotation")
p("Annotation was done in [METHOD REQUIRED: CVAT, labelImg or Roboflow] and exported in YOLO format, which stores one text file per image with the class and the normalised box centre, width and height of every object. Two classes were used (person and weapon) and the rules for drawing boxes were written in an annotation guide before labelling began. A box was drawn around every person who was at least 30 percent visible, edges were drawn tight to the body or clothing, and overlapping people received overlapping boxes.")
p("To reduce labelling time the pretrained model drafted the person boxes first. Every image was then reviewed by an annotator who corrected the boxes, deleted wrong ones and added the weapon class by hand. Draft boxes were never accepted without review. Table 3.4 reports how many draft boxes needed correction, which indicates how well the pretrained model already detected local people before any training. Figures 3.3 and 3.4 show the same image before and after correction.")
table("Table 3.4: Annotation effort and corrections", ["Measure", "Value"], [
    ["Images annotated", "[DATA REQUIRED]"],
    ["Draft person boxes produced by the pretrained model", "[DATA REQUIRED]"],
    ["Draft boxes accepted unchanged", "[DATA REQUIRED]"],
    ["Draft boxes moved or resized", "[DATA REQUIRED]"],
    ["Draft boxes deleted", "[DATA REQUIRED]"],
    ["Boxes added by hand (missed people and weapons)", "[DATA REQUIRED]"],
    ["Mean IoU between two annotators on a 10 percent sample", "[RESULT REQUIRED]"],
], [4.4, 2.1])
slot("Figure 3.3: Annotation tool with draft person boxes from the pretrained model", "Screenshot of the annotation tool showing a frame with the grey draft boxes and the class list (person, weapon) visible.")
slot("Figure 3.4: The same image after manual correction, including a weapon box", "Screenshot of the same frame after correction, with the missed person added and a weapon prop boxed.")

h2("3.5.5 Dataset partitioning")
p("The images were divided into training, validation and test sets in the proportions 70, 20 and 10 percent. The division was made by volunteer and not by image, so that every frame of one volunteer fell in a single set. Consecutive frames of the same person are almost identical. A division by image would have placed near-copies in both the training and the test sets and inflated the test result. A fixed random seed of 0 was used so that the same division could be reproduced. Figure 3.5 shows the resulting composition.")
slot("Figure 3.5: Dataset composition by condition and split", "Run training/split_dataset.py and insert results/dataset_stats.png.")

h2("3.5.6 Model training")
p("Training started from YOLO11n weights pretrained on the COCO dataset [CITATION REQUIRED], which is a transfer learning approach that needs far fewer images than training from random weights. The model was trained for up to 80 epochs at an image size of 640 pixels with a batch size of 16. Training stopped early if the validation metric did not improve for 20 epochs. The default augmentations of the Ultralytics library were applied, which include colour jitter, random scaling, translation, mosaic composition and horizontal flipping. The training hardware was [DETAIL REQUIRED: processor or graphics card and training time]. Table 3.5 lists the settings and Figure 3.6 shows the training curves.")
table("Table 3.5: Poacher detection model training settings", ["Setting", "Value"], [
    ["Starting weights", "YOLO11n pretrained on COCO"],
    ["Classes", "person, weapon"],
    ["Maximum epochs", "80"],
    ["Early stopping patience", "20 epochs"],
    ["Image size", "640 pixels"],
    ["Batch size", "16"],
    ["Random seed", "0"],
    ["Confidence threshold in deployment", "0.45"],
    ["Confirmation rule in deployment", "person present in at least 3 of the last 6 processed frames"],
    ["Frames processed in deployment", "every second frame"],
], [3.2, 3.3])
slot("Figure 3.6: Training and validation curves of the poacher detection model", "After running training/train_poacher.py insert runs/poacher/results.png.")

h2("3.5.7 Evaluation procedure")
p("The trained model was evaluated once on the test set, which had not been used for training or for selecting settings. Precision, recall, mean average precision at an intersection over union (IoU) of 0.5 (mAP@0.5) and mean average precision averaged over IoU from 0.5 to 0.95 (mAP@0.5:0.95) were obtained from the Ultralytics validation routine. A second evaluation used the deployment confidence of 0.45 and counted a detection as correct when its IoU with an annotated person was at least 0.5. Precision was calculated as true positives divided by the sum of true and false positives and recall as true positives divided by the sum of true positives and false negatives.")
p("The pretrained model was run on the same test images as a baseline, so that the gain from training on local data could be reported. Recall was also calculated separately for each capture condition and for each volunteer. The per-volunteer calculation was used to check that no individual was missed more often than the others, without grouping volunteers by any personal characteristic. The scripts that produced these results are evaluate_vision.py and train_poacher.py. The results are presented in Chapter 4.")

h2("3.6 Gunshot detection model")
h2("3.6.1 Audio data")
p("Two classes of audio recordings were collected, gunshot and other. The gunshot class contained recordings of rifle and shotgun fire taken at different distances and in different terrain [DETAIL REQUIRED: source of recordings, number, and the permission obtained for live firing or the public source used]. The other class contained sounds that occur in a conservancy and that could be mistaken for a gunshot, namely wind, birdsong, vehicles, speech, thunder, branches snapping, fireworks and silence. All recordings were converted to mono at 16 kHz in WAV format. Table 3.6 shows the dataset composition.")
table("Table 3.6: Composition of the audio dataset", ["Class", "Recordings", "Total duration (s)", "Windows (0.975 s)"], [
    ["gunshot", "[DATA REQUIRED]", "[DATA REQUIRED]", "[DATA REQUIRED]"],
    ["other", "[DATA REQUIRED]", "[DATA REQUIRED]", "[DATA REQUIRED]"],
], [1.6, 1.6, 1.8, 1.7])

h2("3.6.2 Feature extraction and classifier")
p("Audio was cut into windows of 15 600 samples, which is 0.975 seconds at 16 kHz and is the input length of YAMNet. Each window was passed through YAMNet, which returned a score for each of the 521 AudioSet sound classes [CITATION REQUIRED]. During training the windows overlapped by half, with a hop of 7 800 samples. A logistic regression classifier with balanced class weights and a regularisation constant of 2.0 was then trained on the 521 scores of each window to separate gunshot from other.")
p("A baseline that needed no training was also defined. It took the highest score among the five YAMNet classes for gunshot and gunfire, machine gun, fusillade, artillery fire and cap gun and raised an alert when that score reached 0.35. In deployment the microphone stream was kept in a two-second buffer and the latest window was scored every 0.5 seconds, so a gunshot could be detected within about one second of occurring.")

h2("3.6.3 Training and threshold selection")
p("Recordings, and not windows, were divided between training and test sets in the proportions 75 and 25 percent with a fixed seed of 0. Windows cut from one recording therefore never appeared on both sides of the division. The alert threshold of the classifier was examined between 0.05 and 0.95 in steps of 0.05. The chosen value was the one that gave [RESULT REQUIRED: target recall] recall with the fewest false alarms on the test recordings. The initial values were 0.6 for the classifier and 0.35 for the baseline.")

h2("3.6.4 Evaluation procedure")
p("The classifier and the baseline were evaluated on the same test recordings. Precision, recall, F1 score, the area under the receiver operating characteristic curve (AUC) and a confusion matrix were calculated for each. A field test was then conducted at [DETAIL REQUIRED: site] in which gunshots were recorded at [DETAIL REQUIRED: distances in metres] from the laptop microphone. The detection rate at each distance was counted. False alarms were counted over [DETAIL REQUIRED: hours] of continuous ambient recording with no gunshot present. The script train_gunshot.py performed the training and produced the evaluation figures.")

h2("3.7 Ranger authorisation by BLE tag")
p("Authorised rangers carried an ESP32 board that advertised the fixed name RANGER-R001 (RANGER-R002 for the second ranger) at an interval of 20 to 40 milliseconds. The laptop scanned passively for BLE advertisements and compared each advertised name or hardware address with the list of registered tags. A tag was accepted as present when it had been heard within the previous 15 seconds with a received signal strength indicator (RSSI) of at least -90 dBm. Weaker or older sightings were ignored.")
p("Two tests were designed for this component. In the range test the tag was placed at distances of [DETAIL REQUIRED: for example 1, 5, 10, 20 and 30 metres] in open ground and in dense bush. The proportion of 15-second windows in which the tag was detected was recorded together with the mean RSSI. In the authorisation test a volunteer walked past the camera with the tag and without it, and the system response was compared with the expected response, ranger sighting with the tag and poacher alert without it. The number of repetitions was [SAMPLE SIZE REQUIRED].")

h2("3.8 Flame sensing node")
p("The flame node read the analogue output of the flame sensor module with a 12-bit converter every 250 milliseconds. A reading below 1 500 on the scale 0 to 4 095 or an active digital output counted as a hot reading. A fire was declared after three consecutive hot readings. The node posted a JSON message containing its identifier, the fire state and the raw reading to the base station whenever the state changed and as a heartbeat every 10 seconds, or every 3 seconds while a fire was declared. The base station marked a node offline when no message had arrived for 30 seconds.")
p("The node was tested by exposing it to a lighter flame at distances of [DETAIL REQUIRED: distances in centimetres or metres] and in direct sunlight with no flame. The detection result and the delay between ignition and the dashboard alert were recorded for each trial, with [SAMPLE SIZE REQUIRED] trials per distance. The sunlight trials were included because infrared sunlight is a known cause of false fire readings in flame sensor modules [CITATION REQUIRED].")

h2("3.9 Alert fusion and web dashboard")
p("The alert engine decided what each detection meant. A person confirmed by the poacher detection model was treated as a ranger sighting if a registered tag was present and as a poacher alert if no tag was present. A visible weapon always produced an armed alert, because a tag cannot excuse a weapon. A gunshot within 120 seconds of a poacher alert, in either order, raised the alert to armed poacher. Cooldown periods of 30 seconds for poacher alerts, 120 seconds for ranger sightings, 10 seconds for gunshots and 60 seconds for fire prevented one event from generating many alerts. Figure 3.7 shows the decision logic.")
fig("Figure 3.7: Alert decision logic of the alert engine", FIG + "fig3_2_alert_logic.png")
p("Each alert was saved with its time, type, location and a snapshot of the camera frame. A laptop has no satellite positioning receiver, so each alert carried the fixed coordinates of the node that raised it, which were entered in the configuration file when the node was installed. The dashboard received alerts through a WebSocket connection. It showed the live camera view with the objects detected and the status of every sensor and node, together with a map of all nodes on which the base station was highlighted. Telemetry for the base station and the field nodes and the alert log were shown below the map. Selecting any element opened an enlarged dialog with more detail. Figure 3.8 shows the dashboard.")
slot("Figure 3.8: Web dashboard of the anti-poaching system during a test", "Run the system with your own test footage and execute: node tools/capture_screenshots.js http://localhost:8000. Insert results/screens/dashboard_overview.png and, if useful, camera_dialog.png.")

h2("3.10 System testing procedure")
p("Software testing began with 15 automated unit and interface tests that checked the alert rules, the cooldown periods, the expiry of ranger tags, the fire alert and the dashboard interface. These tests were repeated after every change to the code. Integrated testing followed with the staged scenarios in Table 3.7, each repeated [SAMPLE SIZE REQUIRED] times. A scenario was scored as correct when the alert type shown on the dashboard matched the expected type.")
table("Table 3.7: Integrated test scenarios", ["No.", "Scenario", "Expected response"], [
    ["1", "Volunteer without a tag enters the camera view", "Poacher alert with snapshot"],
    ["2", "Volunteer carrying a tag enters the camera view", "Ranger sighting and no alarm"],
    ["3", "Volunteer with a tag, tag removed for more than 15 seconds", "Poacher alert after the tag expires"],
    ["4", "Gunshot sound only", "Gunshot alert"],
    ["5", "Gunshot, then a volunteer without a tag within 120 seconds", "Armed poacher alert"],
    ["6", "Weapon prop carried by a volunteer with a tag", "Armed alert"],
    ["7", "Lighter flame placed in front of the flame node", "Fire alert at the node location"],
    ["8", "Power removed from the flame node", "Node shown offline after 30 seconds"],
], [0.5, 3.6, 2.4])
p("The alert delay was measured as the time between the staged event and the appearance of the alert on the dashboard, using a stopwatch recording and the timestamps stored in the database [METHOD REQUIRED: confirm timing method]. Delays are reported as medians with the range. Each trial was repeated [SAMPLE SIZE REQUIRED] times so that the spread of the delay could be reported as well as its typical value.")

h2("3.11 Data analysis procedure")
p("Results were analysed descriptively. Confusion matrices, precision, recall, F1 score, mAP and AUC were calculated with the Ultralytics and scikit-learn libraries, while the fine-tuned model was compared with the pretrained baseline on identical test data. Alert delays were summarised with the median and the range. No inferential test was applied unless the supervisor required one [SUPERVISOR CONFIRMATION REQUIRED]. All tables and figures in Chapter 4 were generated by scripts so that the reported numbers could be traced to a file.")

h2("3.12 Reliability and validity")
p("Reliability was supported by fixed random seeds, by reusing the same division of the data for every comparison and by repeating each field scenario [SAMPLE SIZE REQUIRED] times. Internal validity was protected by keeping the test data completely separate from training and by dividing the data by volunteer and by recording. The same camera, resolution and mounting height were used for training images and for the field tests, which supports external validity for the site tested.")
p("The results cannot be generalised beyond the volunteers, the locations and the sounds that were sampled. A ranger tag identifies an object and not a person, so a stolen or copied tag would be accepted as a ranger. This limitation of the authorisation method is reported with the results and is considered again in Chapter 5.")

h2("3.13 Ethical considerations")
p("Every volunteer received an information sheet and signed a consent form before being photographed. Participation was voluntary, volunteers could withdraw and request deletion of their images until [DATE REQUIRED]. Volunteers were identified only by an anonymous code. Images were stored on a password-protected laptop, used only for this research and deleted on [DATE REQUIRED]. Faces appeared in the dissertation only for volunteers who gave separate written permission. Ethics clearance was obtained from [SUPERVISOR CONFIRMATION REQUIRED: committee and reference number], and the handling of personal data followed the Cyber and Data Protection Act of Zimbabwe [CITATION REQUIRED].")
p("Several safeguards addressed the risks specific to this study. Only props and replicas were used for weapon images. No live firearm was handled during image collection. The classes of the model described objects and not people, and the model was never trained or evaluated to distinguish people by race, so the decision to raise an alarm depended on the absence of a ranger tag. Volunteers were recruited to represent the people found at the intended sites, and the per-volunteer evaluation was included to detect unequal performance. Field tests inside a protected area were carried out only with written permission from [DETAIL REQUIRED: park authority or landowner], and recordings of gunfire were made only at [DETAIL REQUIRED: licensed range or approved site].")

h2("3.14 Chapter summary")
p("This chapter described a quantitative, experimental and design-based study of an anti-poaching system built from a poacher detection model, a gunshot detection model, a BLE ranger tag check, a flame sensing node and a web dashboard. Image data of local volunteers were collected, annotated with a reviewed pre-labelling process, divided by volunteer and used to fine-tune a YOLO11n model. Audio recordings were converted to YAMNet class scores and used to train a classifier that was compared with an untrained baseline. Each component and the integrated system were tested with defined procedures. The ethical safeguards for the volunteers were also stated. The next chapter presents the results of these procedures.")
