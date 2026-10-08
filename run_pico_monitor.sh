#!/usr/bin/env bash

set -u

PROJECT_DIR="/home/mother/SmartCylinder"

if [[ ! -d "$PROJECT_DIR" ]]; then
    echo "Smart Cylinder project not found: $PROJECT_DIR"
    read -r -p "Press Enter to close..."
    exit 1
fi

exec 9>/tmp/smart-cylinder-pico-monitor.lock
if ! flock -n 9; then
    echo "Smart Cylinder Pico Monitor is already running."
    echo "Close the existing monitor window before opening another one."
    read -r -p "Press Enter to close..."
    exit 1
fi

read -r -p "MQTT username [pi-subscriber]: " PICO_MONITOR_MQTT_USERNAME
PICO_MONITOR_MQTT_USERNAME="${PICO_MONITOR_MQTT_USERNAME:-pi-subscriber}"
read -r -s -p "MQTT password: " PICO_MONITOR_MQTT_PASSWORD
echo

if [[ -z "$PICO_MONITOR_MQTT_PASSWORD" ]]; then
    echo "MQTT password is required."
    read -r -p "Press Enter to close..."
    exit 1
fi

export PICO_MONITOR_MQTT_USERNAME
export PICO_MONITOR_MQTT_PASSWORD

cleanup() {
    unset PICO_MONITOR_MQTT_USERNAME
    unset PICO_MONITOR_MQTT_PASSWORD
}
trap cleanup EXIT INT TERM

cd "$PROJECT_DIR" || exit 1
python3 -m system.MQTT.pico_status_monitor \
    --broker-host 127.0.0.1 \
    --username "$PICO_MONITOR_MQTT_USERNAME"
exit_code=$?

cleanup
trap - EXIT INT TERM
echo
echo "Pico Monitor finished with exit code $exit_code."
read -r -p "Press Enter to close..."
exit "$exit_code"
