// AquaSense ESP32 node: capacitive soil probe + DHT22 + optional irrigation valve relay.
// Libraries: WiFi, HTTPClient, ArduinoJson (v6), "DHT sensor library" (Adafruit)
//
// Safety design (valve):
//  * the relay is switched OFF first thing on every boot and held OFF during deep sleep
//  * every run has a local timer, so the valve closes even if WiFi or the server disappears
//  * runs are capped by MAX_VALVE_MIN regardless of what the server asks
//  * readings are buffered in RTC memory while offline and uploaded in one batch later
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include "driver/gpio.h"

// ---- configure these ----
const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASS = "YOUR_PASSWORD";
const char* BASE_URL  = "http://YOUR_SERVER_IP:5001";
const char* API_KEY   = "DEVICE_KEY_FROM_FIELD_PAGE";   // per-device key shown on the field page
const char* DEVICE    = "SM-NT-001";

#define HAS_VALVE 1
const int  RELAY_PIN = 26;
const bool RELAY_ACTIVE_LOW = true;
const int  SOIL_PIN = 34, DHT_PIN = 4;
const int  AIR_DRY = 3200, AIR_WET = 1400;               // calibrate: probe in air / in water
const uint32_t SLEEP_MIN = 15;
const uint32_t MAX_VALVE_MIN = 240;
// -------------------------

DHT dht(DHT_PIN, DHT22);
struct Sample { float moisture, airT, hum; uint32_t boot; };
RTC_DATA_ATTR Sample buf[24];
RTC_DATA_ATTR uint8_t nBuf = 0;
RTC_DATA_ATTR uint32_t bootNo = 0;

void relay(bool on) { digitalWrite(RELAY_PIN, (on ^ RELAY_ACTIVE_LOW) ? HIGH : LOW); }

bool wifiUp(uint32_t timeoutMs = 15000) {
  if (WiFi.status() == WL_CONNECTED) return true;
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < timeoutMs) delay(250);
  return WiFi.status() == WL_CONNECTED;
}

int httpCall(const String& path, const char* method, const String& body, String& out) {
  HTTPClient http;
  http.begin(String(BASE_URL) + path);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", API_KEY);
  http.setTimeout(8000);
  int code = (String(method) == "GET") ? http.GET() : http.POST(body);
  out = (code > 0) ? http.getString() : "";
  http.end();
  return code;
}

void addSample(const Sample& s) {
  if (nBuf == 24) { memmove(&buf[0], &buf[1], sizeof(Sample) * 23); nBuf = 23; }   // drop oldest
  buf[nBuf++] = s;
}

bool flushBuffer() {
  if (nBuf == 0) return true;
  DynamicJsonDocument doc(6144);
  doc["device_code"] = DEVICE;
  JsonArray arr = doc.createNestedArray("readings");
  for (uint8_t i = 0; i < nBuf; i++) {
    JsonObject o = arr.createNestedObject();
    o["soil_moisture"] = buf[i].moisture; o["air_temp"] = buf[i].airT; o["humidity"] = buf[i].hum;
    o["age_s"] = (bootNo - buf[i].boot) * SLEEP_MIN * 60;
  }
  String body, out; serializeJson(doc, body);
  int code = httpCall("/api/readings/batch", "POST", body, out);
  if (code == 201) { nBuf = 0; return true; }
  return false;
}

void ack(const String& ref, bool ok) {
  String out, body = String("{\"ref\":\"") + ref + "\",\"status\":\"" + (ok ? "done" : "failed") + "\"}";
  httpCall(String("/api/devices/") + DEVICE + "/ack", "POST", body, out);
}

#if HAS_VALVE
void runValve(uint32_t minutes, const String& ref) {
  if (minutes > MAX_VALVE_MIN) minutes = MAX_VALVE_MIN;
  relay(true);
  uint32_t t0 = millis(), lastPoll = millis();
  while (millis() - t0 < minutes * 60000UL) {
    delay(1000);
    if (millis() - lastPoll > 30000UL) {              // let the server stop us early
      lastPoll = millis();
      if (WiFi.status() == WL_CONNECTED) {
        String out;
        if (httpCall(String("/api/devices/") + DEVICE + "/command", "GET", "", out) == 200) {
          StaticJsonDocument<192> d;
          if (!deserializeJson(d, out) && String((const char*)d["action"]) == "close") break;
        }
      }
    }
  }
  relay(false);                                       // always closes, even offline
  if (wifiUp(8000)) ack(ref, true);
}

void checkValve() {
  String out;
  if (httpCall(String("/api/devices/") + DEVICE + "/command", "GET", "", out) != 200) return;
  StaticJsonDocument<192> d;
  if (deserializeJson(d, out)) return;
  String action = d["action"] | "idle";
  if (action == "open") runValve(d["minutes"] | 0, String((const char*)(d["ref"] | "")));
}
#endif

void setup() {
  pinMode(RELAY_PIN, OUTPUT);
  gpio_hold_dis((gpio_num_t)RELAY_PIN);
  relay(false);                                       // fail-safe: valve closed on every boot
  Serial.begin(115200);
  dht.begin();
  bootNo++;

  int raw = analogRead(SOIL_PIN);
  Sample s = { (float)constrain(map(raw, AIR_DRY, AIR_WET, 0, 100), 0, 100), dht.readTemperature(), dht.readHumidity(), bootNo };

  if (wifiUp()) {
    bool ok = flushBuffer();
    String out;
    DynamicJsonDocument doc(256);
    doc["device_code"] = DEVICE; doc["soil_moisture"] = s.moisture;
    if (!isnan(s.airT)) doc["air_temp"] = s.airT;
    if (!isnan(s.hum)) doc["humidity"] = s.hum;
    String body; serializeJson(doc, body);
    int code = httpCall("/api/readings", "POST", body, out);
    if (code != 201) addSample(s);
    Serial.printf("POST %d moisture=%.1f buffered=%d flushed=%d\n", code, s.moisture, nBuf, ok);
#if HAS_VALVE
    checkValve();
#endif
  } else {
    addSample(s);
    Serial.printf("offline, buffered %d\n", nBuf);
  }

  relay(false);
  gpio_hold_en((gpio_num_t)RELAY_PIN);                // keep relay off through deep sleep
  gpio_deep_sleep_hold_en();
  esp_sleep_enable_timer_wakeup((uint64_t)SLEEP_MIN * 60ULL * 1000000ULL);
  esp_deep_sleep_start();
}

void loop() {}
