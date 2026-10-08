#!/usr/bin/env bash
# Run on the Raspberry Pi: sudo bash deploy/add-pico-mqtt-users.sh
# Creates broker accounts for pico01~pico06 and narrow ACLs for pico02~pico06.
set -euo pipefail

PASSWORD_FILE=/etc/mosquitto/passwd
ACL_FILE=/etc/mosquitto/smart-cylinder.acl
STAMP=$(date +%Y%m%d_%H%M%S)

[[ $EUID -eq 0 ]] || { echo "Run with sudo."; exit 1; }
[[ -f $PASSWORD_FILE && -f $ACL_FILE ]] || { echo "Mosquitto password/ACL files not found."; exit 1; }

cp -p "$PASSWORD_FILE" "${PASSWORD_FILE}.before-pico-users-${STAMP}"
cp -p "$ACL_FILE" "${ACL_FILE}.before-pico-users-${STAMP}"

read -r -s -p "Common password for pico01~pico06: " COMMON_PASSWORD
echo
[[ -n $COMMON_PASSWORD ]] || { echo "Password cannot be empty."; exit 1; }

for NUMBER in 01 02 03 04 05 06; do
  USER="pico${NUMBER}"
  mosquitto_passwd -b "$PASSWORD_FILE" "$USER" "$COMMON_PASSWORD"
  if ! grep -qx "user ${USER}" "$ACL_FILE"; then
    cat >> "$ACL_FILE" <<EOF

# ${USER} may publish only its own data and receive only its own control messages.
user ${USER}
topic write smartCylinder/${USER}/+/raw
topic write smartCylinder/${USER}/status
topic read smartCylinder/control/${USER}/token
topic read smartCylinder/control/${USER}/ack
EOF
  fi
done

systemctl reload mosquitto
unset COMMON_PASSWORD
echo "Created/updated pico01~pico06. Broker users:"
cut -d: -f1 "$PASSWORD_FILE"
