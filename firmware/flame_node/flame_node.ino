// Poacher Guard - ESP32 flame/fire node.
// Reads a 4-pin flame sensor module and tells the laptop over Wi-Fi.
//
// Wiring (typical YG1006 / "flame sensor module" with LM393):
//   VCC -> 3V3   GND -> GND   AO -> GPIO34 (analog)   DO -> GPIO27 (digital)
// Most modules read LOW on the analog pin when flame is strong, so a LOW raw
// value = fire. Adjust FIRE_BELOW after watching the Serial Monitor.
#include <WiFi.h>
#include <HTTPClient.h>

const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASS = "YOUR_PASSWORD";
// Laptop IP on the same network + dashboard port (see config.yaml server.port).
const char* SERVER_URL = "http://192.168.1.50:8000/api/sensors/flame";
const char* NODE_ID    = "FLAME-01";   // must match flame.nodes[].id in config.yaml

const int PIN_ANALOG  = 34;
const int PIN_DIGITAL = 27;
const int FIRE_BELOW  = 1500;          // 0-4095; lower = more infrared flame light
const int CONFIRM_READS = 3;           // consecutive hot reads before reporting fire
const unsigned long HEARTBEAT_MS = 10000;

bool lastFire = false;
int hot = 0;
unsigned long lastSend = 0;

void connectWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) delay(250);
}

bool post(bool fire, int raw) {
  connectWifi();
  if (WiFi.status() != WL_CONNECTED) return false;
  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");
  String body = String("{\"node\":\"") + NODE_ID + "\",\"fire\":" + (fire ? "true" : "false") +
                ",\"raw\":" + raw + "}";
  int code = http.POST(body);
  http.end();
  return code == 200;
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_DIGITAL, INPUT);
  analogReadResolution(12);
  connectWifi();
}

void loop() {
  int raw = analogRead(PIN_ANALOG);
  bool dig = digitalRead(PIN_DIGITAL) == LOW;       // module's own threshold
  hot = (raw < FIRE_BELOW || dig) ? hot + 1 : 0;
  bool fire = hot >= CONFIRM_READS;
  Serial.printf("raw=%d dig=%d fire=%d\n", raw, dig, fire);

  unsigned long now = millis();
  // Send immediately on a state change, otherwise as a periodic heartbeat
  // (the dashboard shows the node offline if heartbeats stop).
  if (fire != lastFire || now - lastSend >= (fire ? 3000UL : HEARTBEAT_MS)) {
    if (post(fire, raw)) lastSend = now;
    lastFire = fire;
  }
  delay(250);
}
