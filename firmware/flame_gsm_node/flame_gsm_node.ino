// Poacher Guard - field node for an ESP32 DevKit (38-pin): flame sensor + GSM text alerts.
//
// What it does
//   1. Reads the flame sensor. On fire it texts every phone number below at once (works even if the laptop or
//      Wi-Fi is down) and reports the fire to the laptop dashboard over Wi-Fi.
//   2. Every 2 s asks the laptop for new alerts (GET /api/sms). When the camera finds a POACHER, or the microphone a
//      GUNSHOT, the laptop answers with a ready-made text message and this node sends it by SMS.
//
// Wiring (ESP32 38-pin DevKit)
//   Flame sensor module (LM393, 3 or 4 pins)
//     VCC -> 3V3      GND -> GND
//     AO  -> GPIO34   (analog; leave unconnected on a 3-pin module and set USE_ANALOG = false)
//     DO  -> GPIO27   (digital; LOW = flame)
//     Do NOT use the pins marked D0, D1, D2, D3, CMD or CLK (GPIO 6-11): they belong to the flash chip and
//     using them crashes the board.
//   GSM module (SIM800L 2G, or SIM7600 / A7670 4G - same text-message commands)
//     TXD -> GPIO16 (RX2)     RXD -> GPIO17 (TX2)     GND -> ESP32 GND (common ground is required)
//     VCC -> its own supply: SIM800L needs 3.7-4.2 V that can give 2 A peaks (an 18650 cell, or a buck converter
//            set to 4.0 V) with a 1000 uF capacitor across VCC/GND. NEVER power it from the ESP32 3V3 or 5V pin:
//            it resets every time it tries to send. A 4G board with a 5 V input can use a 5 V 2 A supply.
//     Insert a SIM card with airtime/SMS bundle and the PIN lock turned off.
//
// Setup
//   Arduino IDE, board "ESP32 Dev Module". Edit the settings below, upload, open Serial Monitor at 115200.
//   The laptop must run Poacher Guard and be on the same Wi-Fi; SERVER is the laptop's IP (PowerShell:
//   (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias 'Wi-Fi').IPAddress ).
#include <WiFi.h>
#include <HTTPClient.h>

// ------------------------------------------------------------------ settings
const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASS = "YOUR_PASSWORD";
const char* SERVER    = "http://10.225.4.245:8000";   // laptop running Poacher Guard
const char* NODE_ID   = "FLAME-01";                    // must match flame.nodes[].id in config.yaml

const char* PHONES[] = {"+263770000000"};               // rangers to text, international format
const int   N_PHONES = sizeof(PHONES) / sizeof(PHONES[0]);
const char* SMS_TYPES = "poacher,gunshot";              // laptop alerts that are texted
const unsigned long SMS_GAP_MS = 120000;                // at most one text per alert type every 2 minutes
const bool  TEXT_ON_BOOT = true;                        // send "node online" once, to prove the GSM works

const int  PIN_FLAME_AO = 34;
const int  PIN_FLAME_DO = 27;
const bool USE_ANALOG   = true;
const int  FIRE_BELOW   = 1500;     // 0-4095: lower analog value = more flame light. Tune in Serial Monitor.
const int  CONFIRM_READS = 3;       // consecutive hot reads (250 ms apart) before it counts as fire

const int GSM_RX = 16, GSM_TX = 17;
const long GSM_BAUD = 9600;         // SIM800L default; many 4G boards use 115200
// ---------------------------------------------------------------------------

HardwareSerial gsm(2);
bool lastFire = false, gsmReady = false;
int hot = 0;
long lastAlertId = -1;              // newest laptop event already handled (-1 = not asked yet)
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
  if (!onNet) Serial.println("[GSM] not registered on the network yet (antenna? 2G coverage? power?)");
  return onNet;
}

bool sendSms(const char* number, const String& text) {
  String r = at(String("AT+CMGS=\"") + number + "\"", 5000, ">");
  if (r.indexOf(">") < 0) return false;
  gsm.print(text.substring(0, 160));
  gsm.write(26);                                // Ctrl+Z sends the message
  String done; unsigned long t0 = millis();
  while (millis() - t0 < 20000) {               // network can take several seconds
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
  if (smsSent[kind] && millis() - lastSms[kind] < SMS_GAP_MS) { Serial.println("[SMS] skipped (sent one recently)"); return; }
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
  if (started && millis() - lastTry < 15000) return;   // retry every 15 s, so the flame check keeps running
  lastTry = millis(); started = true;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  for (int i = 0; i < 20 && WiFi.status() != WL_CONNECTED; i++) delay(250);
  Serial.printf("[WiFi] %s %s\n", WiFi.status() == WL_CONNECTED ? "connected, IP" : "not connected",
                WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString().c_str() : "");
}

void postFlame(bool fire, int raw) {
  if (WiFi.status() != WL_CONNECTED) return;
  HTTPClient http;
  http.begin(String(SERVER) + "/api/sensors/flame");
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(String("{\"node\":\"") + NODE_ID + "\",\"fire\":" + (fire ? "true" : "false") + ",\"raw\":" + raw + "}");
  http.end();
  if (code == 200) lastFlamePost = millis();
}

// Ask the laptop for alerts newer than lastAlertId; text each poacher/gunshot alert.
void pollAlerts() {
  if (WiFi.status() != WL_CONNECTED) return;
  HTTPClient http;
  http.setConnectTimeout(2000);
  http.setTimeout(3000);
  http.begin(String(SERVER) + "/api/sms?after=" + lastAlertId + "&types=" + SMS_TYPES);
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
    textAll(type == "gunshot" ? 2 : 1, text);
  }
  lastAlertId = newest;
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_FLAME_DO, INPUT_PULLUP);           // pull-up: an unplugged DO wire reads "no flame", not random
  analogReadResolution(12);
  gsm.begin(GSM_BAUD, SERIAL_8N1, GSM_RX, GSM_TX);
  delay(3000);                                  // let the GSM module start
  gsmReady = gsmInit();
  connectWifi();
  if (TEXT_ON_BOOT && gsmReady)
    for (int i = 0; i < N_PHONES; i++) sendSms(PHONES[i], String("POACHER GUARD: node ") + NODE_ID + " online. Text alerts are active.");
}

void loop() {
  unsigned long now = millis();

  // flame sensor
  int raw = USE_ANALOG ? analogRead(PIN_FLAME_AO) : 4095;
  bool dig = digitalRead(PIN_FLAME_DO) == LOW;
  hot = ((USE_ANALOG && raw < FIRE_BELOW) || dig) ? hot + 1 : 0;
  bool fire = hot >= CONFIRM_READS;
  if (fire != lastFire) {
    Serial.printf("[FLAME] %s (raw=%d)\n", fire ? "FIRE" : "clear", raw);
    if (fire) textAll(0, String("POACHER GUARD FIRE at node ") + NODE_ID + ". Flame sensor triggered (reading " + raw + "). Check the area now.");
    connectWifi(); postFlame(fire, raw);
    lastFire = fire;
  } else if (now - lastFlamePost >= (fire ? 3000UL : 10000UL)) {
    connectWifi(); postFlame(fire, raw);        // heartbeat: dashboard shows the node online
  }

  // laptop alerts -> SMS
  if (now - lastPoll >= 2000) { lastPoll = now; connectWifi(); pollAlerts(); }

  // re-check the GSM network now and then if it was not ready
  if (!gsmReady && now - lastGsmCheck >= 30000) { lastGsmCheck = now; gsmReady = gsmInit(); }

  delay(250);
}
