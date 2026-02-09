from __future__ import annotations

import csv
import logging
import os
import queue
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional, Tuple

from flask import Flask, Response, jsonify, request, send_file
import paho.mqtt.client as mqtt

from config import settings


@dataclass
class TelemetryRow:
    ts_iso: str
    ts_unix_ms: int
    device: str
    datatype: str
    value: str


class CsvWriter:
    def __init__(self, log_dir: str, flush_interval: float, batch_size: int, logger: logging.Logger) -> None:
        self.log_dir = log_dir
        self.flush_interval = flush_interval
        self.batch_size = batch_size
        self.logger = logger
        self.queue: "queue.Queue[TelemetryRow]" = queue.Queue()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

        os.makedirs(self.log_dir, exist_ok=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=5)

    def enqueue(self, row: TelemetryRow) -> None:
        self.queue.put(row)

    def _run(self) -> None:
        buffer: List[TelemetryRow] = []
        last_flush = time.monotonic()
        current_date: Optional[str] = None
        file_handle = None
        writer = None

        while not self._stop_event.is_set():
            try:
                row = self.queue.get(timeout=0.2)
                buffer.append(row)
            except queue.Empty:
                pass

            now = time.monotonic()
            if buffer and (len(buffer) >= self.batch_size or now - last_flush >= self.flush_interval):
                try:
                    for item in buffer:
                        date_key = datetime.fromtimestamp(item.ts_unix_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                        if current_date != date_key:
                            if file_handle:
                                file_handle.flush()
                                file_handle.close()

                            current_date = date_key
                            file_path = os.path.join(self.log_dir, f"{current_date}.csv")
                            is_new = not os.path.exists(file_path)
                            file_handle = open(file_path, "a", newline="", encoding="utf-8")
                            writer = csv.writer(file_handle)
                            if is_new:
                                writer.writerow([
                                    "ts_server_iso",
                                    "ts_server_unix_ms",
                                    "device",
                                    "datatype",
                                    "value",
                                ])

                        if writer:
                            writer.writerow([item.ts_iso, item.ts_unix_ms, item.device, item.datatype, item.value])

                    if file_handle:
                        file_handle.flush()
                except Exception as exc:
                    self.logger.exception("CSV writer error: %s", exc)
                finally:
                    buffer.clear()
                    last_flush = now

        if file_handle:
            file_handle.flush()
            file_handle.close()


class State:
    def __init__(self, history_points: int) -> None:
        self.lock = threading.Lock()
        self.devices: Dict[str, Dict[str, Any]] = {}
        self.latest: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        self.history: Dict[str, Dict[str, Deque[Tuple[int, str]]]] = defaultdict(lambda: defaultdict(lambda: deque(maxlen=history_points)))

    def update_status(self, device: str, status: str, ts_unix_ms: int) -> None:
        with self.lock:
            device_entry = self.devices.setdefault(device, {})
            device_entry["status"] = status
            device_entry["last_seen"] = ts_unix_ms

    def update_telemetry(self, device: str, datatype: str, value: str, ts_unix_ms: int) -> None:
        with self.lock:
            device_entry = self.devices.setdefault(device, {})
            device_entry["last_seen"] = ts_unix_ms
            self.latest[device][datatype] = {"value": value, "ts_unix_ms": ts_unix_ms}
            self.history[device][datatype].append((ts_unix_ms, value))

    def snapshot_devices(self) -> List[Dict[str, Any]]:
        with self.lock:
            results = []
            for device_id, info in self.devices.items():
                latest_values = self.latest.get(device_id, {})
                results.append({
                    "device": device_id,
                    "status": info.get("status", "unknown"),
                    "last_seen_unix_ms": info.get("last_seen"),
                    "latest": latest_values,
                })
            return sorted(results, key=lambda x: x["device"])

    def snapshot_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            if device_id not in self.devices:
                return None
            info = self.devices[device_id]
            return {
                "device": device_id,
                "status": info.get("status", "unknown"),
                "last_seen_unix_ms": info.get("last_seen"),
                "latest": self.latest.get(device_id, {}),
                "history": {
                    datatype: list(points)
                    for datatype, points in self.history.get(device_id, {}).items()
                },
            }


def create_logger() -> logging.Logger:
    logger = logging.getLogger("edge")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    file_handler = logging.FileHandler(settings.app_log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


logger = create_logger()
state = State(history_points=settings.history_points)
writer = CsvWriter(settings.log_dir, settings.flush_interval_sec, settings.flush_batch_size, logger)


app = Flask(__name__, static_folder="../web", static_url_path="/")


@app.route("/")
def index() -> Response:
    return send_file(os.path.join(app.static_folder, "index.html"))


@app.route("/api/health")
def api_health() -> Response:
    return jsonify({"status": "ok"})


@app.route("/api/devices")
def api_devices() -> Response:
    return jsonify(state.snapshot_devices())


@app.route("/api/device/<device_id>")
def api_device(device_id: str) -> Response:
    data = state.snapshot_device(device_id)
    if not data:
        return jsonify({"error": "not_found"}), 404
    return jsonify(data)


@app.route("/api/latest")
def api_latest() -> Response:
    return jsonify({"latest": state.latest})


@app.route("/api/status")
def api_status() -> Response:
    return jsonify({"devices": state.devices})


@app.route("/api/csv")
def api_csv() -> Response:
    date = request.args.get("date")
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    file_path = os.path.join(settings.log_dir, f"{date}.csv")
    if not os.path.exists(file_path):
        return jsonify({"error": "not_found"}), 404
    return send_file(file_path, mimetype="text/csv", as_attachment=True)


def on_connect(client: mqtt.Client, _userdata: Any, _flags: Dict[str, Any], rc: int) -> None:
    if rc == 0:
        logger.info("MQTT connected")
        base = settings.topic_base
        client.subscribe(f"{base}/telemetry/+/+", qos=settings.mqtt_qos)
        client.subscribe(f"{base}/status/+", qos=settings.mqtt_qos)
        client.subscribe(f"{base}/time/request/+", qos=settings.mqtt_qos)
    else:
        logger.error("MQTT connection failed: %s", rc)


def parse_payload(payload: str) -> Optional[Tuple[str, str, str]]:
    parts = payload.split("|", 2)
    if len(parts) != 3:
        return None
    device, datatype, value = (p.strip() for p in parts)
    if not device or not datatype:
        return None
    return device, datatype, value


def handle_telemetry(payload: str) -> None:
    parsed = parse_payload(payload)
    if not parsed:
        logger.warning("Invalid telemetry payload: %s", payload)
        return

    device, datatype, value = parsed
    now = datetime.now(timezone.utc)
    ts_unix_ms = int(now.timestamp() * 1000)
    ts_iso = now.isoformat()

    state.update_telemetry(device, datatype, value, ts_unix_ms)
    writer.enqueue(TelemetryRow(ts_iso, ts_unix_ms, device, datatype, value))


def handle_status(topic: str, payload: str) -> None:
    device = topic.rsplit("/", 1)[-1]
    status = payload.strip() or "unknown"
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    state.update_status(device, status, now)


def handle_time_request(client: mqtt.Client, topic: str, payload: str) -> None:
    device = topic.rsplit("/", 1)[-1]
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    req_ts = payload.strip()
    if req_ts and req_ts.isdigit():
        response = f"unix_ms|{now_ms}|req_ts={req_ts}"
    else:
        response = f"unix_ms|{now_ms}|req_ts={now_ms}"
    base = settings.topic_base
    client.publish(f"{base}/time/response/{device}", payload=response, qos=settings.mqtt_qos)


def on_message(client: mqtt.Client, _userdata: Any, msg: mqtt.MQTTMessage) -> None:
    try:
        payload = msg.payload.decode("utf-8", errors="ignore")
        topic = msg.topic

        base = settings.topic_base
        if topic.startswith(f"{base}/telemetry/"):
            handle_telemetry(payload)
            return
        if topic.startswith(f"{base}/status/"):
            handle_status(topic, payload)
            return
        if topic.startswith(f"{base}/time/request/"):
            handle_time_request(client, topic, payload)
            return
    except Exception as exc:
        logger.exception("MQTT message handling error: %s", exc)


def create_mqtt_client() -> mqtt.Client:
    client = mqtt.Client(client_id=settings.mqtt_client_id, clean_session=True)
    if settings.mqtt_user:
        client.username_pw_set(settings.mqtt_user, settings.mqtt_password)

    client.on_connect = on_connect
    client.on_message = on_message
    return client


def main() -> None:
    writer.start()

    client = create_mqtt_client()
    client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=settings.mqtt_keepalive)
    client.loop_start()

    logger.info("HTTP server starting on %s:%s", settings.http_host, settings.http_port)
    app.run(host=settings.http_host, port=settings.http_port, threaded=True)


if __name__ == "__main__":
    main()
