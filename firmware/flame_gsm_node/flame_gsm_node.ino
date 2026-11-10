// Poacher Guard - sensor node SIM8008 (ESP32 DevKit, 38-pin): STAND-ALONE flame sensor + GSM texts, Bluetooth link to the PC.
//
// FIRE      The flame sensor on D18 trips -> the node texts the phone(s) at once. Needs no PC, no Wi-Fi, no cable.
// POACHER   The PC (camera + microphone models) sees a poacher or hears a gunshot -> sends the text over Bluetooth ->
//           the node sends it by GSM.
// BLUETOOTH Low Energy, no pairing. The node advertises its name (NODE_ID); Poacher Guard on the PC finds it, connects by
//           itself and reconnects after a drop. The node shows on the dashboard as online with its flame state.
//
// Wiring
//   Flame sensor module:  VCC->3V3   GND->GND   DO->D18 (GPIO18)        (AO not used)
//   GSM module (SIM800L, or SIM7600 / A7670 4G):
//       TXD->GPIO16 (RX2)   RXD->GPIO17 (TX2)   GND->ESP32 GND
//       VCC -> its OWN supply: SIM800L needs 3.7-4.2 V that can give 2 A peaks (18650 cell, or a buck converter set to
//       4.0 V) + a 1000 uF capacitor. Never from the ESP32 3V3/5V pin: it resets whenever the GSM module transmits.
//   SIM card: airtime/SMS bundle, PIN lock off. SIM800L needs 2G coverage on the network.
//
// Arduino IDE: board "ESP32 Dev Module", Tools -> Partition Scheme -> "Huge APP (3MB No OTA)" if it says the sketch is
// too big. Serial Monitor 115200. UPLOAD-ESP32-NODE.bat does all of this and fills in the phone numbers for you.
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

// ------------------------------------------------------------------ settings
const char* NODE_ID   = "SIM8008";                      // Bluetooth name, node name in texts and on the dashboard
const char* PHONES[] = {"+2637XXXXXXXX"};               // ranger phone(s), international format (+263 7...)
const int   N_PHONES = sizeof(PHONES) / sizeof(PHONES[0]);
const unsigned long SMS_GAP_MS = 120000;                // at most one text per threat type every 2 minutes
const bool  TEXT_ON_BOOT = true;                        // "node online" text at start, proves the GSM works

const int  PIN_FLAME = 18;              // D18
const bool FLAME_ACTIVE_LOW = true;     // most LM393 flame modules pull DO LOW on flame; set false if yours goes HIGH
const int  CONFIRM_READS = 3;           // flame reads in a row (250 ms apart) before it counts as fire

const int  GSM_RX = 16, GSM_TX = 17;
const long GSM_BAUD = 9600;             // SIM800L default; many 4G boards use 115200
// ---------------------------------------------------------------------------

#define NUS_SERVICE "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"   // Nordic UART: a text pipe over Bluetooth LE
#define NUS_RX      "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"   // PC -> node
#define NUS_TX      "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"   // node -> PC

HardwareSerial gsm(2);
BLECharacteristic* txChar = nullptr;
volatile bool bleConnected = false, sendHello = false;
String rxBuf;
String inbox[4];                         // text commands from the PC, handled in loop() (sending a text takes seconds)
volatile int inboxN = 0;

bool lastFire = false, gsmReady = false;
int hot = 0;
unsigned long lastBeat = 0, lastHello = 0, lastGsmCheck = 0, lastPrint = 0;
unsigned long lastSms[3] = {0, 0, 0};    // fire, poacher, gunshot
bool smsSent[3] = {false, false, false};

// ---------- GSM ----------
String at(const String& cmd, unsigned long waitMs = 1000, const char* until = "OK") {
  while (gsm.available()) gsm.read();
  gsm.println(cmd);
  String r; unsigned long t0 = millis();
  while (millis() - t0 < waitMs) {
    while (gsm.available()) r += (char)gsm.read();
    if (r.indexOf(until) >= 0 || r.indexOf("ERROR") >= 0) break;
    delay(5);
  }
  r.trim();
  Serial.printf("[GSM] %s -> %s\n", cmd.c_str(), r.c_str());
  return r;
}

bool gsmInit() {
  for (int i = 0; i < 10 && at("AT").indexOf("OK") < 0; i++) delay(500);
  at("ATE0");
  if (at("AT+CPIN?").indexOf("READY") < 0) { Serial.println("[GSM] SIM not ready (inserted? PIN lock off?)"); return false; }
  at("AT+CMGF=1");
  at("AT+CSCS=\"GSM\"");
  String reg = at("AT+CREG?");
  bool onNet = reg.indexOf(",1") >= 0 || reg.indexOf(",5") >= 0;
  at("AT+CSQ");                                 // signal 0-31 (below 10 weak, 99 none)
  if (!onNet) Serial.println("[GSM] not on the network yet (antenna? coverage? power supply?)");
  return onNet;
}

bool sendSms(const char* number, const String& text) {
  String r = at(String("AT+CMGS=\"") + number + "\"", 5000, ">");
  if (r.indexOf(">") < 0) return false;
  gsm.print(text.substring(0, 160));
  gsm.write(26);                                // Ctrl+Z sends
  String done; unsigned long t0 = millis();
  while (millis() - t0 < 20000) {
    while (gsm.available()) done += (char)gsm.read();
    if (done.indexOf("+CMGS") >= 0 || done.indexOf("ERROR") >= 0) break;
    delay(20);
  }
  bool ok = done.indexOf("+CMGS") >= 0;
  Serial.printf("[SMS] %s %s: %s\n", ok ? "sent to" : "FAILED to", number, text.c_str());
  return ok;
}

// kind: 0 fire, 1 poacher, 2 gunshot. Returns 1 sent, 0 failed, -1 skipped (same threat texted recently).
int textAll(int kind, const String& text) {
  if (smsSent[kind] && millis() - lastSms[kind] < SMS_GAP_MS) { Serial.println("[SMS] skipped (same threat texted recently)"); return -1; }
  if (!gsmReady) gsmReady = gsmInit();
  bool any = false;
  for (int i = 0; i < N_PHONES; i++) any |= sendSms(PHONES[i], text);
  if (any) { lastSms[kind] = millis(); smsSent[kind] = true; }
  return any ? 1 : 0;
}

// ---------- Bluetooth ----------
// Send a line to the PC in 20-byte pieces (the smallest Bluetooth packet); the PC joins them at the newline.
void bleSend(const String& line) {
  if (!bleConnected || !txChar) return;
  for (int i = 0; i < (int)line.length(); i += 20) {
    String piece = line.substring(i, i + 20);
    txChar->setValue((uint8_t*)piece.c_str(), piece.length());
    txChar->notify();
    delay(10);
  }
}

class LinkCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer*) { bleConnected = true; sendHello = true; Serial.println("[BT] PC connected"); }
  void onDisconnect(BLEServer*) {
    bleConnected = false;
    Serial.println("[BT] PC disconnected - advertising again");
    BLEDevice::startAdvertising();
  }
};

class RxCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* c) {
    auto v = c->getValue();                                   // std::string or String, depending on the ESP32 core version
    for (size_t i = 0; i < v.length(); i++) rxBuf += (char)v[i];
    int nl;
    while ((nl = rxBuf.indexOf('\n')) >= 0) {
      String line = rxBuf.substring(0, nl); rxBuf = rxBuf.substring(nl + 1);
      line.trim();
      if (line.startsWith("@SMS,") && inboxN < 4) inbox[inboxN++] = line;
    }
    if (rxBuf.length() > 400) rxBuf = "";                     // garbage: start over
  }
};

void startBluetooth() {
  BLEDevice::init(NODE_ID);
  BLEDevice::setMTU(247);
  BLEServer* server = BLEDevice::createServer();
  server->setCallbacks(new LinkCallbacks());
  BLEService* svc = server->createService(NUS_SERVICE);
  txChar = svc->createCharacteristic(NUS_TX, BLECharacteristic::PROPERTY_NOTIFY);
  txChar->addDescriptor(new BLE2902());
  BLECharacteristic* rx = svc->createCharacteristic(NUS_RX, BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
  rx->setCallbacks(new RxCallbacks());
  svc->start();
  BLEAdvertising* adv = BLEDevice::getAdvertising();
  adv->addServiceUUID(NUS_SERVICE);
  adv->setScanResponse(true);
  BLEDevice::startAdvertising();
  Serial.printf("[BT] advertising as '%s'\n", NODE_ID);
}

// "@SMS,poacher,<text>" from the PC -> send the text by GSM, tell the PC how it went.
void handleCommand(const String& line) {
  int c1 = line.indexOf(',', 5);
  if (c1 < 0) return;
  String kind = line.substring(5, c1), text = line.substring(c1 + 1);
  Serial.printf("[PC] %s alert: %s\n", kind.c_str(), text.c_str());
  int r = textAll(kind == "gunshot" ? 2 : 1, text);
  bleSend(String("@SMS,") + (r > 0 ? "ok" : r < 0 ? "skipped" : "fail") + "," + kind + "\n");
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_FLAME, INPUT_PULLUP);             // pull-up: an unplugged wire reads "no flame"
  Serial.println("\n== POACHER GUARD sensor node ==");
  gsm.begin(GSM_BAUD, SERIAL_8N1, GSM_RX, GSM_TX);
  delay(3000);                                  // let the GSM module start
  gsmReady = gsmInit();
  startBluetooth();
  if (TEXT_ON_BOOT && gsmReady)
    for (int i = 0; i < N_PHONES; i++) sendSms(PHONES[i], String("POACHER GUARD | NODE: ") + NODE_ID + " online | text alerts active");
  Serial.println("[SYSTEM] ready");
}

void loop() {
  unsigned long now = millis();

  // flame sensor on D18
  int raw = digitalRead(PIN_FLAME);
  bool flame = (raw == LOW) == FLAME_ACTIVE_LOW;
  hot = flame ? hot + 1 : 0;
  bool fire = hot >= CONFIRM_READS;
  if (now - lastPrint >= 1000) {
    lastPrint = now;
    Serial.printf("[FLAME] GPIO18=%d %s | PC link %s | GSM %s\n", raw, flame ? "FLAME" : "clear",
                  bleConnected ? "connected" : "waiting", gsmReady ? "ready" : "NOT ready");
  }
  if (fire != lastFire) {
    lastFire = fire;
    Serial.printf("[FLAME] %s\n", fire ? "FIRE" : "clear");
    bleSend(String("@FLAME,") + (fire ? "1" : "0") + "\n");               // tell the PC first: the text below takes seconds
    if (fire) textAll(0, String("THREAT: FIRE - flame detected | NODE: ") + NODE_ID + " | check the area now");
    lastBeat = millis();
  }

  // tell the PC who we are and what we see: on connect, then as a heartbeat
  if (sendHello || now - lastHello >= 20000) {
    sendHello = false; lastHello = now;
    bleSend(String("@HELLO,") + NODE_ID + ",gsm=" + (gsmReady ? "1" : "0") + "\n");
    bleSend(String("@FLAME,") + (fire ? "1" : "0") + "\n");
    lastBeat = now;
  } else if (now - lastBeat >= (fire ? 3000UL : 5000UL)) {
    lastBeat = now;
    bleSend(String("@FLAME,") + (fire ? "1" : "0") + "\n");
  }

  // texts the PC asked for
  while (inboxN > 0) {
    String line = inbox[0];
    for (int i = 1; i < inboxN; i++) inbox[i - 1] = inbox[i];
    inboxN--;
    handleCommand(line);
  }

  // GSM not ready at start? try again every 30 s
  if (!gsmReady && now - lastGsmCheck >= 30000) { lastGsmCheck = now; gsmReady = gsmInit(); }

  delay(250);
}
