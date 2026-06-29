#!/usr/bin/env bash
# deploy-mqtt.sh — Install Mosquitto add-on in HA OS VM and configure MQTT integration
# Usage: ./deploy-mqtt.sh --mqtt-password PASSWORD [options]
# Requires: incus, running HA OS VM

set -euo pipefail

# ─── Defaults ──────────────────────────────────────────────────────────────────
VM_NAME="${HA_VM_NAME:-homeassistant}"
MQTT_USER="${MQTT_USER:-mqtt_esp32}"
HA_IP=""

# ─── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --vm-name)       VM_NAME="$2";       shift 2 ;;
    --mqtt-user)     MQTT_USER="$2";     shift 2 ;;
    --mqtt-password) MQTT_PASSWORD="$2"; shift 2 ;;
    --ha-ip)         HA_IP="$2";         shift 2 ;;
    --help)
      echo "Usage: $0 --mqtt-password PASSWORD [options]"
      echo ""
      echo "  --vm-name NAME     HA VM name (default: homeassistant)"
      echo "  --mqtt-user USER   MQTT username (default: mqtt_esp32)"
      echo "  --mqtt-password    MQTT password (required)"
      echo "  --ha-ip IP         HA VM IP (optional — auto-detected from incus)"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ─── Pre-flight ────────────────────────────────────────────────────────────────
echo "==> Checking prerequisites..."

command -v incus >/dev/null 2>&1 || { echo "ERROR: 'incus' not found in PATH."; exit 1; }

if [[ -z "${MQTT_PASSWORD:-}" ]]; then
  echo "ERROR: --mqtt-password is required"
  exit 1
fi

if ! incus info "$VM_NAME" &>/dev/null; then
  echo "ERROR: VM '$VM_NAME' does not exist. Deploy it first."
  exit 1
fi

if [[ -z "$HA_IP" ]]; then
  HA_IP=$(incus list "$VM_NAME" --format csv -c 4 2>/dev/null \
    | grep -oE '192\.168\.[0-9]+\.[0-9]+' | head -1 || true)
fi

if [[ -z "$HA_IP" ]]; then
  echo "ERROR: Could not detect IP for VM '$VM_NAME'. Provide --ha-ip."
  exit 1
fi

echo "    VM: $VM_NAME ($HA_IP)"

# ─── Install Mosquitto Add-on ──────────────────────────────────────────────────
echo "==> Installing Mosquitto MQTT broker add-on..."
incus exec "$VM_NAME" -- ha addons install core_mosquitto

# ─── Configure Credentials ─────────────────────────────────────────────────────
echo "==> Configuring Mosquitto credentials..."
incus exec "$VM_NAME" -- ha addons options core_mosquitto \
  '{"logins": [{"username": "'"$MQTT_USER"'", "password": "'"$MQTT_PASSWORD"'"}], "anonymous": false}'

# ─── Expose Port 1883 to Host ───────────────────────────────────────────────────
echo "==> Exposing port 1883 to host network..."
incus exec "$VM_NAME" -- ha addons network core_mosquitto 1883/tcp 1883

# ─── Start Add-on ──────────────────────────────────────────────────────────────
echo "==> Starting Mosquitto..."
incus exec "$VM_NAME" -- ha addons start core_mosquitto

# ─── Register MQTT Integration ─────────────────────────────────────────────────
echo "==> Configuring MQTT integration in Home Assistant..."
# Tells HA's MQTT integration to bind to the local Mosquitto add-on broker
incus exec "$VM_NAME" -- bash -c '
  curl -s -X POST http://supervisor/services/mqtt \
    -H "Content-Type: application/json" \
    -d "{\"addon\": \"core_mosquitto\", \"service\": \"mqtt\"}"
'

# ─── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════"
echo "  Mosquitto MQTT broker is ready!"
echo ""
echo "  Broker:  $HA_IP:1883"
echo "  User:    $MQTT_USER"
echo "  Password: (as provided)"
echo ""
echo "  Update secrets.py on the ESP32:"
echo "    MQTT_BROKER = \"$HA_IP\""
echo ""
echo "  Then deploy to ESP32:"
echo "    mpremote connect /dev/ttyUSB0 fs cp secrets.py :secrets.py"
echo "══════════════════════════════════════════════════════"
