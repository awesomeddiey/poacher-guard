// Poacher Guard - ranger BLE tag (second ESP32, sewn into the uniform/backpack).
// Advertises a fixed name; the laptop treats a person as an authorised ranger
// while it hears this name. Change TAG_NAME per ranger and mirror it in
// config.yaml -> ble.tags[].name
#include <BLEDevice.h>
#include <BLEAdvertising.h>

const char* TAG_NAME = "RANGER-R001";

void setup() {
  BLEDevice::init(TAG_NAME);
  BLEAdvertising* adv = BLEDevice::getAdvertising();
  adv->setScanResponse(true);
  adv->setMinInterval(0x20);   // ~20 ms: quick pickup; raise (0x640 = 1 s) to save battery
  adv->setMaxInterval(0x40);
  BLEDevice::startAdvertising();
}

void loop() { delay(1000); }
