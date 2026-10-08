#!/usr/bin/env bash
set -euo pipefail
if [[ ${EUID} -ne 0 ]]; then
  echo "Run with sudo: sudo bash deploy/install-pi5.sh"
  exit 1
fi
id -u acoustic >/dev/null 2>&1 || useradd --system --home /var/lib/acoustic --shell /usr/sbin/nologin acoustic
install -d -o acoustic -g acoustic -m 0750 /var/lib/acoustic /var/log/acoustic
install -d -o root -g acoustic -m 0750 /etc/acoustic
cd /opt/acoustic
apt-get update
apt-get install -y mosquitto mosquitto-clients python3-venv libopenblas0
install -m 0644 deploy/mosquitto-smart-cylinder.conf /etc/mosquitto/conf.d/smart-cylinder.conf
install -m 0640 -o root -g mosquitto deploy/mosquitto-smart-cylinder.acl /etc/mosquitto/smart-cylinder.acl
if [[ ! -f /etc/acoustic/analytics.env ]]; then install -m 0640 -o root -g acoustic .env.example /etc/acoustic/analytics.env; fi
set -a
source /etc/acoustic/analytics.env
set +a
mosquitto_passwd -b -c /etc/mosquitto/passwd "$MQTT_USERNAME" "$MQTT_PASSWORD"
chown mosquitto:mosquitto /etc/mosquitto/passwd
chmod 0640 /etc/mosquitto/passwd
systemctl enable mosquitto
systemctl restart mosquitto
python3 -m venv venv
venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install -r requirements.txt
install -m 0644 deploy/smart-cylinder.service /etc/systemd/system/smart-cylinder.service
systemctl daemon-reload
chown -R acoustic:acoustic /opt/acoustic/venv
echo "Set the service-role key only in /etc/acoustic/analytics.env, then enable smart-cylinder."
