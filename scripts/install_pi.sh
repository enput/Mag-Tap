#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/opt/edge-logger

sudo apt-get update
sudo apt-get install -y mosquitto mosquitto-clients python3 python3-pip

sudo mkdir -p ${APP_DIR}
sudo rsync -a ./ ${APP_DIR}/

sudo python3 -m pip install -r ${APP_DIR}/requirements.txt

sudo cp ${APP_DIR}/config/mosquitto.conf /etc/mosquitto/mosquitto.conf

if [ ! -f /etc/mosquitto/passwd ]; then
  sudo touch /etc/mosquitto/passwd
  sudo mosquitto_passwd -b /etc/mosquitto/passwd edge changeme
fi

sudo systemctl restart mosquitto

sudo cp ${APP_DIR}/systemd/edge-logger.service /etc/systemd/system/edge-logger.service
sudo systemctl daemon-reload
sudo systemctl enable edge-logger.service
sudo systemctl restart edge-logger.service

echo "Install completed. Update MQTT_PASSWORD in /etc/systemd/system/edge-logger.service and restart the service."
