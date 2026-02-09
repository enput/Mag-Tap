from __future__ import annotations

import argparse
import random
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--user", default="")
    parser.add_argument("--password", default="")
    parser.add_argument("--count", type=int, default=60)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--topic-base", default="v1")
    args = parser.parse_args()

    client = mqtt.Client(client_id="simulator")
    if args.user:
        client.username_pw_set(args.user, args.password)

    client.connect(args.host, args.port, keepalive=60)
    client.loop_start()

    device_ids = [f"esp-{i:02d}" for i in range(1, args.count + 1)]
    for device_id in device_ids:
        client.publish(f"{args.topic_base}/status/{device_id}", payload="online", qos=1, retain=True)

    try:
        while True:
            for device_id in device_ids:
                temp = round(random.uniform(20, 35), 2)
                humidity = round(random.uniform(30, 70), 2)
                now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

                payload_temp = f"{device_id}|temp|{temp}"
                payload_hum = f"{device_id}|humidity|{humidity}"

                client.publish(f"{args.topic_base}/telemetry/{device_id}/temp", payload=payload_temp, qos=1)
                client.publish(f"{args.topic_base}/telemetry/{device_id}/humidity", payload=payload_hum, qos=1)

                if random.random() < 0.05:
                    client.publish(f"{args.topic_base}/time/request/{device_id}", payload=str(now_ms), qos=1)

            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        for device_id in device_ids:
            client.publish(f"{args.topic_base}/status/{device_id}", payload="offline", qos=1, retain=True)
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
