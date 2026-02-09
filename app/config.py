from __future__ import annotations

import os
from dataclasses import dataclass


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    mqtt_host: str = _env("MQTT_HOST", "127.0.0.1")
    mqtt_port: int = _env_int("MQTT_PORT", 1883)
    mqtt_user: str = _env("MQTT_USER", "")
    mqtt_password: str = _env("MQTT_PASSWORD", "")
    mqtt_keepalive: int = _env_int("MQTT_KEEPALIVE", 60)
    mqtt_qos: int = _env_int("MQTT_QOS", 1)
    mqtt_client_id: str = _env("MQTT_CLIENT_ID", "edge-logger")

    topic_base: str = _env("MQTT_TOPIC_BASE", "v1")

    log_dir: str = _env("LOG_DIR", "logs")
    app_log_file: str = _env("APP_LOG_FILE", "app.log")

    flush_interval_sec: float = float(_env("FLUSH_INTERVAL_SEC", "1.0"))
    flush_batch_size: int = _env_int("FLUSH_BATCH_SIZE", 200)

    history_points: int = _env_int("HISTORY_POINTS", 300)

    http_host: str = _env("HTTP_HOST", "0.0.0.0")
    http_port: int = _env_int("HTTP_PORT", 8080)


settings = Settings()
