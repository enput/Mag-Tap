# Kommandoer til at sende MQTT data (Windows CMD)

**Forudsætning:** Mosquitto CLI er installeret (mosquitto_pub).

## 1) Telemetri (QoS 1)

mosquitto_pub -h 127.0.0.1 -p 1883 -t v1/telemetry/esp-01/temp -q 1 -m "esp-01|temp|23.7"

mosquitto_pub -h 127.0.0.1 -p 1883 -t v1/telemetry/esp-01/humidity -q 1 -m "esp-01|humidity|45.2"

## 2) Status (retained)

mosquitto_pub -h 127.0.0.1 -p 1883 -t v1/status/esp-01 -q 1 -r -m "online"

mosquitto_pub -h 127.0.0.1 -p 1883 -t v1/status/esp-01 -q 1 -r -m "offline"

## 3) Time request

mosquitto_pub -h 127.0.0.1 -p 1883 -t v1/time/request/esp-01 -q 1 -m "1739078400000"

## 4) Med brugernavn/password

mosquitto_pub -h 127.0.0.1 -p 1883 -u edge -P changeme -t v1/telemetry/esp-01/temp -q 1 -m "esp-01|temp|23.7"

## 5) Tilslutning til Raspberry Pi broker

mosquitto_pub -h <PI-IP> -p 1883 -t v1/telemetry/esp-01/temp -q 1 -m "esp-01|temp|23.7"

## 6) Tjek modtagelse (subscribe)

mosquitto_sub -h 127.0.0.1 -p 1883 -t v1/# -v
