// Poacher Guard - sensor node SIM8008 (ESP32 DevKit, 38-pin): flame sensor + GSM text alerts.
//
// What it does
//   1. FIRE: reads the flame sensor on D18. On flame it texts the phone at once (works even if the laptop or Wi-Fi
//      is down) and shows the fire on the laptop dashboard over Wi-Fi.
//   2. POACHER / GUNSHOT: every 2 s it asks the laptop (PC running our models) for new alerts and texts them.
//   Every text says the threat and the node:  THREAT: <what> | NODE: SIM8008 | ...
//
// Wiring (ESP32 38-pin DevKit)
//   Flame sensor module (LM393)          GSM module (SIM800L, or SIM7600 / A7670 4G)
//     VCC -> 3V3                           TXD -> GPIO16 (RX2)
//     GND -> GND                           RXD -> GPIO17 (TX2)
//     DO  -> D18 (GPIO18)                  GND -> ESP32 GND (shared ground is required)
//     (AO not used: GPIO18 is digital)     VCC -> its OWN supply. SIM800L: 3.7-4.2 V able to give 2 A peaks
//                                                 (18650 cell or buck converter set to 4.0 V) + 1000 uF capacitor.
//                                                 Never from the ESP32 3V3/5V pin: it resets when it transmits.
//   SIM card: airtime/SMS bundle, PIN lock off. SIM800L needs 2G coverage on the network.
//   Set the flame module's sensitivity with its blue potentiometer: its DO LED should light only for a flame.
//
// Arduino IDE: board "ESP32 Dev Module", Serial Monitor 115200. The laptop must run Poacher Guard on the same Wi-Fi.
#include <WiFi.h>
#include <HTTPClient.h>

// ------------------------------------------------------------------ settings
const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASS = "YOUR_PASSWORD";
const char* SERVER    = "http://10.225.4.245:8000";   // laptop running Poacher Guard (its IP + :8000)
const char* NODE_ID   = "SIM8008";                     // node name in texts and on the dashboard (config.yaml flame.nodes)

const char* PHONES[] = {"+263772109787"};               // 0772109787 in international format
const int   N_PHONES = sizeof(PHONES) / sizeof(PHONES[0]);
const char* SMS_TYPES = "poacher,gunshot";              // laptop alerts that are texted
const unsigned long SMS_GAP_MS = 120000;                // at most one text per threat type every 2 minutes
const bool  TEXT_ON_BOOT = true;                        // "node online" text at start, proves the GSM works

const int  PIN_FLAME = 18;              // D18
const bool FLAME_ACTIVE_LOW = true;     // most LM393 flame modules pull DO LOW on flame; set false if yours goes HIGH
const int  CONFIRM_READS = 3;           // consecutive flame reads (250 ms apart) before it counts as fire

const int  GSM_RX = 16, GSM_TX = 17;
const long GSM_BAUD = 9600;             // SIM800L default; many 4G boards use 115200
// ---------------------------------------------------------------------------

HardwareSerial gsm(2);
bool lastFire = false, gsmReady = false;
int hot = 0;
long lastAlertId = -1;                  // newest laptop alert already handled (-1 = not asked yet)
unsigned long lastFlamePost = 0, lastPoll = 0, lastGsmCheck = 0;
unsigned long lastSms[3] = {0, 0, 0};   // fire, poacher, gunshot
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
  at("ATE0");                                   // no echo
  if (at("AT+CPIN?").indexOf("READY") < 0) { Serial.println("[GSM] SIM not ready (inserted? PIN lock off?)"); return false; }
  at("AT+CMGF=1");                              // text mode
  at("AT+CSCS=\"GSM\"");
  String reg = at("AT+CREG?");
  bool onNet = reg.indexOf(",1") >= 0 || reg.indexOf(",5") >= 0;   // home or roaming
  at("AT+CSQ");                                 // signal 0-31 (below 10 is weak, 99 = none)
  if (!onNet) Serial.println("[GSM] not on the network yet (antenna? 2G coverage? power supply?)");
  return onNet;
}

bool sendSms(const char* number, const String& text) {
  String r = at(String("AT+CMGS=\"") + number + "\"", 5000, ">");
  if (r.indexOf(">") < 0) return false;
  gsm.print(text.substring(0, 160));
  gsm.write(26);                                // Ctrl+Z sends the message
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

// kind: 0 fire, 1 poacher, 2 gunshot. Repeats of the same kind are held back for SMS_GAP_MS.
void textAll(int kind, const String& text) {
  if (smsSent[kind] && millis() - lastSms[kind] < SMS_GAP_MS) { Serial.println("[SMS] skipped (same threat texted recently)"); return; }
  if (!gsmReady) gsmReady = gsmInit();
  bool any = false;
  for (int i = 0; i < N_PHONES; i++) any |= sendSms(PHONES[i], text);
  if (any) { lastSms[kind] = millis(); smsSent[kind] = true; }
}

// ---------- Wi-Fi / laptop ----------
void connectWifi() {
  static unsigned long lastTry = 0;
  static bool started = false;
  if (WiFi.status() == WL_CONNECTED) return;
  if (started && millis() - lastTry < 15000) return;   // retry every 15 s so the flame check keeps running
  lastTry = millis(); started = true;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  for (int i = 0; i < 20 && WiFi.status() != WL_CONNECTED; i++) delay(250);
  if (WiFi.status() == WL_CONNECTED) Serial.printf("[WiFi] connected, IP %s\n", WiFi.localIP().toString().c_str());
  else Serial.println("[WiFi] not connected (fire texts still work)");
}

void postFlame(bool fire) {
  if (WiFi.status() != WL_CONNECTED) return;
  HTTPClient http;
  http.setConnectTimeout(2000);
  http.begin(String(SERVER) + "/api/sensors/flame");
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(String("{\"node\":\"") + NODE_ID + "\",\"fire\":" + (fire ? "true" : "false") + ",\"raw\":" + (fire ? 0 : 4095) + "}");
  http.end();
  if (code == 200) lastFlamePost = millis();
}

// Ask the laptop for alerts newer than lastAlertId and text each one.
void pollAlerts() {
  if (WiFi.status() != WL_CONNECTED) return;
  HTTPClient http;
  http.setConnectTimeout(2000);
  http.setTimeout(3000);
  http.begin(String(SERVER) + "/api/sms?after=" + lastAlertId + "&types=" + SMS_TYPES + "&node=" + NODE_ID);
  int code = http.GET();
  if (code != 200) { http.end(); Serial.printf("[laptop] no answer (%d) - is Poacher Guard running at %s ?\n", code, SERVER); return; }
  String body = http.getString();
  http.end();
  int nl = body.indexOf('\n');
  if (nl < 0) return;
  long newest = body.substring(0, nl).toInt();
  int pos = nl + 1;
  while (pos < (int)body.length()) {            // lines: id \t type \t text
    int end = body.indexOf('\n', pos); if (end < 0) end = body.length();
    String line = body.substring(pos, end); pos = end + 1;
    int t1 = line.indexOf('\t'), t2 = line.indexOf('\t', t1 + 1);
    if (t1 < 0 || t2 < 0) continue;
    String type = line.substring(t1 + 1, t2), text = line.substring(t2 + 1);
    textAll(type == "gunshot" ? 2 : 1, text);   // text = "THREAT: POACHER ALERT ... | NODE: SIM8008 | 01:08 | maps..."
  }
  lastAlertId = newest;
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_FLAME, INPUT_PULLUP);             // pull-up: an unplugged wire reads "no flame"
  gsm.begin(GSM_BAUD, SERIAL_8N1, GSM_RX, GSM_TX);
  delay(3000);                                  // let the GSM module start
  gsmReady = gsmInit();
  connectWifi();
  if (TEXT_ON_BOOT && gsmReady)
    for (int i = 0; i < N_PHONES; i++) sendSms(PHONES[i], String("POACHER GUARD | NODE: ") + NODE_ID + " online | text alerts active");
}

void loop() {
  unsigned long now = millis();

  // flame sensor on D18
  bool flame = (digitalRead(PIN_FLAME) == LOW) == FLAME_ACTIVE_LOW;
  hot = flame ? hot + 1 : 0;
  bool fire = hot >= CONFIRM_READS;
  if (fire != lastFire) {
    Serial.printf("[FLAME] %s\n", fire ? "FIRE" : "clear");
    if (fire) textAll(0, String("THREAT: FIRE - flame detected | NODE: ") + NODE_ID + " | check the area now");
    connectWifi(); postFlame(fire);
    lastFire = fire;
  } else if (now - lastFlamePost >= (fire ? 3000UL : 10000UL)) {
    connectWifi(); postFlame(fire);             // heartbeat: dashboard shows the node online
  }

  // laptop alerts (poacher, gunshot) -> SMS
  if (now - lastPoll >= 2000) { lastPoll = now; connectWifi(); pollAlerts(); }

  // GSM not ready at start? try again every 30 s
  if (!gsmReady && now - lastGsmCheck >= 30000) { lastGsmCheck = now; gsmReady = gsmInit(); }

  delay(250);
}
