#!/bin/bash
set -euo pipefail
set +e
sudo /opt/acoustic/venv/bin/python /opt/acoustic/tools/check_all_picos_mqtt.py
STATUS=$?
set -e
echo
read -r -p "Press Enter to close..."
exit "$STATUS"
