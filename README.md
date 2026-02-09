# MQTT Edge Logger + Dashboard (Raspberry Pi)

Denne løsning leverer:

- Mosquitto broker
- Python ingest-service + web dashboard
- CSV logging pr. dag
- Time-sync respons til ESP32

## Funktioner

- Telemetri via MQTT (QoS 1)
- LWT online/offline status
- CSV logging (batch write)
- Web dashboard med seneste værdier + mini trends
- REST endpoints til status, latest, device detail og CSV download

## MQTT topic + payload kontrakt

**Base:** `v1`

- Telemetri (ESP → Pi): `v1/telemetry/<deviceId>/<dataType>`
  - payload: `<deviceId>|<dataType>|<value>`
- Status (ESP → Pi): `v1/status/<deviceId>` (retained)
  - payload: `online` / `offline`
- Time request (ESP → Pi): `v1/time/request/<deviceId>`
- Time response (Pi → ESP): `v1/time/response/<deviceId>`
  - payload: `unix_ms|<UNIX_MS>|req_ts=<UNIX_MS>`

Parsing er robust via `split("|", 2)` og invalide payloads logges.

## CSV format

**Fil:** `logs/YYYY-MM-DD.csv`

**Kolonner:**

- `ts_server_iso`
- `ts_server_unix_ms`
- `device`
- `datatype`
- `value`

Header skrives én gang pr fil.

## Struktur

- [app/main.py](app/main.py) – ingest service + webapp
- [app/config.py](app/config.py) – env-baseret config
- [web/index.html](web/index.html) – dashboard
- [scripts/simulate_devices.py](scripts/simulate_devices.py) – 60 device simulering
- [scripts/install_pi.sh](scripts/install_pi.sh) – Pi install script
- [systemd/edge-logger.service](systemd/edge-logger.service) – systemd service
- [config/mosquitto.conf](config/mosquitto.conf) – Mosquitto config

## Kør lokalt

```bash
python -m pip install -r requirements.txt
python app/main.py
```

Åbn dashboard: `http://localhost:8080`

## Kør på Raspberry Pi

1. Kopiér repo til Pi
2. Kør install script:

```bash
bash scripts/install_pi.sh
```

3. Opdatér MQTT password i systemd service:

```bash
sudo nano /etc/systemd/system/edge-logger.service
sudo systemctl restart edge-logger.service
```

## Konfiguration (env)

- `MQTT_HOST` (default 127.0.0.1)
- `MQTT_PORT` (default 1883)
- `MQTT_USER`
- `MQTT_PASSWORD`
- `MQTT_QOS` (default 1)
- `MQTT_TOPIC_BASE` (default v1)
- `LOG_DIR` (default logs)
- `APP_LOG_FILE` (default app.log)
- `FLUSH_INTERVAL_SEC` (default 1.0)
- `FLUSH_BATCH_SIZE` (default 200)
- `HISTORY_POINTS` (default 300)
- `HTTP_HOST` (default 0.0.0.0)
- `HTTP_PORT` (default 8080)

## Tilføj ny datatype/device

1. På ESP32: publish til `v1/telemetry/<deviceId>/<dataType>`
2. Payload: `<deviceId>|<dataType>|<value>`
3. Dashboard viser automatisk nye datatyper for device.

## Minimal test – simulér 60 devices

```bash
python scripts/simulate_devices.py --host 127.0.0.1 --count 60
```

Bekræft at:

- CSV filer oprettes i `logs/`
- Dashboard opdateres

## Drift og robusthed

- Mosquitto kører som system service
- Edge service kører som systemd service (auto-restart)
- Parsing fejl logges, men stopper ikke processen
- CSV skrivning er kø-baseret (ingen disk I/O i MQTT callback)
