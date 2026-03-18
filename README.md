# 🍺 ESP32 Keg Level Monitor

A complete DIY keg level monitor using a hall effect flow sensor, an ESP32, MicroPython, and Home Assistant. Tracks how much beer has been poured in real time and displays the remaining volume and percentage on a live dashboard.

**Tested with:** Home Assistant Core 2026.2.3 / Frontend 20260128.6

---

## Table of Contents

1. [Parts List](#parts-list)
2. [How It Works](#how-it-works)
3. [Wiring](#wiring)
4. [Home Assistant Setup](#home-assistant-setup)
5. [ESP32 Setup](#esp32-setup)
6. [Configuring and Deploying the Code](#configuring-and-deploying-the-code)
7. [Setting Up the Dashboard](#setting-up-the-dashboard)
8. [Resetting for a New Keg](#resetting-for-a-new-keg)
9. [Troubleshooting](#troubleshooting)

---

## What Gets Reported to Home Assistant

The ESP32 automatically publishes the following data to Home Assistant via MQTT:

| Entity | MQTT Topic | Description |
|--------|------------|-------------|
| Flow Rate | `home/flow_sensor/flow_rate` | Current flow rate in L/min |
| Dispensed | `home/flow_sensor/total_volume` | Total beer dispensed from the keg (L) |
| Remaining | `home/flow_sensor/keg_remaining` | Liters remaining in the keg |
| Keg Level | `home/flow_sensor/keg_level` | Keg fullness as a percentage (0-100%) |

Home Assistant auto-discovers these as sensor entities automatically — no manual configuration required. A wake button is also auto-discovered to keep the device awake for WebREPL access.

---

## Parts List

| Part | Notes |
|---|---|
| ESP32 development board | Any standard ESP32 board works (e.g. ESP32-WROOM-32) |
| Gredia 1/4" Hall Effect Flow Sensor | Food-grade, 0.3–6 L/min range |
| 1/4" barbed fittings | To splice the sensor into your beer line |
| Jumper wires | 3 wires needed (power, ground, signal) |
| Home Assistant instance | Running on a Raspberry Pi, NUC, VM, etc. |
| USB cable | For flashing the ESP32 |

> **Note on keg size:** This guide is configured for a **5 US gallon corny keg (18.93 L)**. If you use a different size, update the `KEG_VOLUME_LITERS` constant in `main.py`.

---

## How It Works

The flow sensor contains a small plastic rotor with a magnet. As beer flows through it, the rotor spins and the built-in hall effect sensor emits a pulse for every rotation. The ESP32 counts these pulses using a hardware interrupt and converts them to flow rate and volume using the sensor's calibration formula:

> **Flow rate (L/min) = pulse frequency (Hz) ÷ 23**

Every 30 seconds (or on flow detection), the ESP32 wakes up, publishes the current flow rate, total volume dispensed from the keg, liters remaining, and keg percentage to Home Assistant over MQTT, then enters lightsleep to conserve battery. Home Assistant auto-discovers these as sensor entities — no manual configuration required.

---

## Wiring

Install the sensor in your beer line between the keg and the faucet. Flow direction is marked by an arrow on the sensor body.

Connect the sensor's wires to the ESP32 as follows:

| Sensor Wire | ESP32 Pin |
|---|---|
| Red | 3.3V (or 5V if your board exposes it) |
| Black | GND |
| Yellow | GPIO 4 |

> The sensor works on both 3.3V and 5V. If you notice erratic readings, try 5V if your board has a 5V pin available.

---

## Home Assistant Setup

Since you're running Home Assistant Container (without the Apps panel), you'll run Mosquitto as a separate Docker container using docker-compose.

### Step 1 — Set Up Mosquitto with Docker Compose

MQTT is the messaging protocol the ESP32 uses to send data to Home Assistant.

1. Copy the `mosquitto` folder from this repository to your Docker host (e.g., `~/mosquitto`)

2. Create directories and generate the password file:

```bash
# Create directories
mkdir -p ~/mosquitto/config ~/mosquitto/data ~/mosquitto/log

# Generate password file
docker run --rm -it -v ~/mosquitto/config:/mosquitto/config eclipse-mosquitto:latest mosquitto_passwd -c /mosquitto/config/mosquitto.passwd mqtt_esp32
```

Enter your desired password when prompted.

3. Fix ownership (required for Mosquitto to write to log/data directories):

```bash
sudo chown -R 1883:1883 ~/mosquitto
```

4. Start Mosquitto:

```bash
cd ~/mosquitto
docker-compose up -d
```

### Step 2 — Add the MQTT Integration to Home Assistant

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration** and search for **MQTT**
3. Click **MQTT**
4. For the broker address, enter your Docker host's IP address (e.g., `192.168.1.100`)
5. Port: `1883`
6. Enter the username (`mqtt_esp32`) and password you created
7. Click **Submit**

Home Assistant will confirm the connection. You're now ready to receive data from the ESP32.

---

## ESP32 Setup

### Step 1 — Install esptool

On your computer, open a terminal and run:

```bash
pip install esptool
```

### Step 2 — Download MicroPython

Go to [micropython.org/download/ESP32_GENERIC](https://micropython.org/download/ESP32_GENERIC/) and download the latest stable `.bin` firmware file.

### Step 3 — Erase the ESP32

Plug in your ESP32 via USB, then run (check `ls /dev/ttyUSB*` to find your device):

```bash
esptool --port /dev/ttyUSB0 erase-flash
```

### Step 4 — Flash MicroPython

```bash
esptool --port /dev/ttyUSB0 --chip esp32  --baud 460800 write-flash -z 0x1000 ESP32_GENERIC-*.bin
```

Replace `ESP32_GENERIC-*.bin` with the actual filename you downloaded.

### Step 5 — Verify umqtt is Available

In the REPL (using mpremote or minicom), type:

```python
import umqtt.simple
```

If you get no error, you're good. If you get `ModuleNotFoundError`, install it by typing:

```python
import mip
mip.install("umqtt.simple")
```

### Optional — Connecting with minicom (Ubuntu 24.04)

```bash
sudo apt install minicom
sudo usermod -a -G dialout $USER
```

Log out and back in for the group change to take effect, then run:

```bash
minicom -D /dev/ttyUSB0 -b 115200
```

- **Device:** `/dev/ttyUSB0`
- **Baudrate:** `115200`

To exit minicom, press `Ctrl+A`, then `X`, then `Enter`.

---

## Configuring and Deploying the Code

### Step 1 — Configure Credentials

Copy `secrets.py.example` to `secrets.py` and fill in your details:

```python
WIFI_SSID     = "your_wifi_ssid"
WIFI_PASSWORD = "your_wifi_password"

MQTT_BROKER   = "192.168.1.100"   # Your Docker host's IP address
MQTT_PORT     = 1883
MQTT_USER     = "mqtt_esp32"      # Username from mosquitto_passwd command
MQTT_PASSWORD = "your_password"   # Password from mosquitto_passwd command
MQTT_CLIENT_ID = "esp32_flow_sensor"
```

To find your Docker host IP address, run `hostname -I` on the machine running Docker.

To find your Home Assistant IP address, go to **Settings → System → Network** in HA.

### Step 2 — Upload the Files

Using **mpremote**:

```bash
# Copy secrets.py
mpremote connect /dev/ttyUSB0 fs cp secrets.py :secrets.py

# Deploy main.py
mpremote connect /dev/ttyUSB0 fs cp main.py :main.py

```

### Step 3 — (Optional) Enable WebREPL

To enable wireless debugging, enable WebREPL once (run this command then follow the prompts):

```bash
mpremote connect /dev/ttyUSB0 repl
```

In the REPL, type:

```python
import webrepl_setup
```

Follow the prompts:

- Would you like to enable WebREPL? → **E** to enable
- Set a password (e.g., "esp32pw")

After enabling, you can connect to `http://<esp32-ip>:8266/` from your browser.

### Step 4 — Run It

Reset the ESP32 to start the flow sensor:

```bash
mpremote connect /dev/ttyUSB0 reset
```

Or press the Reset button on the ESP32. Watch the output — you should see:

```bash
Connecting to WiFi...
WiFi connected: 192.168.1.XXX
MQTT connected
Auto-discovery published to Home Assistant
Published → flow: 0.0 L/min | keg: 18.93L (100.0%)
Entering lightsleep for 270000ms...
```

In Home Assistant, go to **Settings → Devices & Services → MQTT** and you should see a new device called **Water Flow Sensor** with four entities:

- `sensor.water_flow_rate` — current flow rate in L/min
- `sensor.water_total_volume` — all-time total volume in L
- `sensor.keg_level` — keg fullness as a percentage
- `sensor.keg_remaining` — liters left in the keg

---

## Setting Up the Dashboard in Home Assistant

### Option 1: Using the UI (Recommended)

The easiest way to create a dashboard is using Home Assistant's built-in UI:

1. Go to **Settings** → **Dashboards**
2. Click **Add Dashboard**
3. Choose **Sections** view (recommended) or **Masonry**
4. Click **Add Card** and add the following cards:

**Card 1 - Keg Level Gauge:**

- Card type: **Gauge**
- Entity: `sensor.keg_level`
- Min: 0, Max: 100
- Unit: `%`
- Color: Amber (or use theme colors)

**Card 2 - Flow Stats:**

- Card type: **Entities** (or **Statistic** card if available)
- Add entities:
  - `sensor.keg_remaining` (liters left)
  - `sensor.flow_rate` (L/min)
  - `sensor.total_volume` (total dispensed)

**Card 3 - Reset Button:**

- Card type: **Button**
- Entity: Create a helper (Settings → Devices & Services → Helpers → Button) with MQTT action
- Or use an **MQTT Button** (see configuration below)

### Option 2: Using YAML (Advanced)

If you prefer YAML mode dashboards:

```yaml
# configuration.yaml
mqtt:
  button:
    - name: "Reset Keg"
      command_topic: "home/flow_sensor/reset"
      payload_press: "RESET"
```

Then add a YAML dashboard:

```yaml
# dashboards/keg.yaml
title: Keg Monitor
views:
  - title: Keg
    cards:
      - type: gauge
        entity: sensor.keg_level
        min: 0
        max: 100
        unit: '%'
      - type: entities
        entities:
          - entity: sensor.keg_remaining
            name: Remaining
          - entity: sensor.flow_rate
            name: Flow Rate
          - entity: sensor.total_volume
            name: Total Volume
```

### Reset Button via MQTT

To add a reset button that appears in HA:

```yaml
# configuration.yaml
mqtt:
  button:
    - name: "Reset Keg"
      command_topic: "home/flow_sensor/reset"
      payload_press: "RESET"
```

After adding to configuration.yaml, restart Home Assistant.

---

## Resetting for a New Keg

When you put on a fresh keg, tap the **🔄 New Keg — Reset to Full** button on the dashboard. This publishes a reset message to `home/flow_sensor/reset` via MQTT, which tells the ESP32 to set the dispensed volume back to zero and treat the keg as 100% full.

You can also trigger the reset from any MQTT client, or via a Home Assistant automation, by publishing any message to:

```bash
home/flow_sensor/reset
```

---

## Waking the Device for WebREPL Access

The ESP32 spends most of its time in lightsleep to conserve battery. To access WebREPL or make code changes:

### Option 1: MQTT Wake Button (Recommended)

Add an MQTT Button to Home Assistant to wake the device:

```yaml
# configuration.yaml
mqtt:
  button:
    - name: "Flow Sensor Wake"
      command_topic: "home/flow_sensor/wake"
      payload_press: "WAKE"
```

Restart Home Assistant, then click the button to wake the device. It will stay awake for 5 minutes, giving you time to connect to WebREPL at `ws://<esp32-ip>:8266`.

#### MQTT Reset Button

To add a reset button in Home Assistant:

```yaml
# configuration.yaml
mqtt:
  button:
    - name: "Flow Sensor Wake"
      command_topic: "home/flow_sensor/wake"
      payload_press: "WAKE"
    - name: "Reset Keg"
      command_topic: "home/flow_sensor/reset"
      payload_press: "RESET"
```

Restart Home Assistant after adding these buttons.

### Option 2: Wait for Next Wake Cycle

The device wakes every 4.5 minutes to publish data. During this window, you can connect to WebREPL.

---

## Battery Optimization

The ESP32 uses **lightsleep** mode to achieve long battery life:

- **Active:** ~150-250mA (WiFi + MQTT publishing, ~2 seconds per cycle)
- **Sleep:** ~1mA (lightsleep with CPU suspended)

On a 10,000 mAh battery bank, expect **~3 months** of operation under normal use.

### Configuration

Key settings in `main.py`:

| Constant | Default | Description |
| ---------- | --------- | ------------- |
| `PUBLISH_INTERVAL` | 30s | Time between MQTT publishes |
| `SLEEP_INTERVAL` | 270000ms | Lightsleep duration (4.5 minutes) |
| `WAKE_TIMEOUT_SECONDS` | 300 | Time to stay awake after wake command (5 min) |
| `TIMEZONE_SECONDS` | -28800 | Timezone offset in seconds (-8×60×60 for PST) |
| `PULSES_PER_LITER` | 450 | Sensor calibration (pulses per liter) |

---

## Troubleshooting

**ESP32 won't connect to WiFi**
Double-check your SSID and password in `secrets.py`. Make sure your network is 2.4 GHz — the ESP32 does not support 5 GHz.

**MQTT connection refused**
Verify the broker IP address is your Home Assistant machine's local IP, not `localhost`. Confirm the username and password match what you set up in the Mosquitto configuration. Make sure port 1883 isn't blocked by a firewall.

**Sensor entities don't appear in Home Assistant**
Check that the MQTT integration is connected (Settings → Devices & Services → MQTT should show "Connected"). Try restarting the ESP32 — it publishes auto-discovery messages on every boot.

**Flow readings are zero even when pouring**
Check your wiring — particularly the yellow signal wire on GPIO 4. Make sure the sensor is installed in the correct flow direction (follow the arrow on the body). Confirm the sensor is getting power (red wire).

**Keg percentage goes below zero**
This can happen if the keg was tapped when already partially empty and then reset at that point rather than when full. Just hit the Reset button when you put on a known-full keg going forward.

**Readings seem inaccurate**
The sensor's calibration constant (450 pulses per liter) is nominal. If you want higher accuracy, you can calibrate it yourself by pouring a known volume (e.g. exactly 1 liter into a measuring jug) and adjusting the `PULSES_PER_LITER` constant in `main.py` based on the actual pulse count observed.

---

## File Reference

| File | Description |
| --- | --- |
| `main.py` | Main ESP32 firmware — deploy as `main.py` on the device |
| `secrets.py.example` | Template for WiFi/MQTT credentials — copy to `secrets.py` and configure |
| `mosquitto/` | Docker Compose config for Mosquitto broker — copy to Docker host and run |
| `keg_dashboard_card.yaml` | Home Assistant dashboard YAML with Bar Card (requires HACS) |
| `keg_dashboard.yaml` | Simple YAML dashboard without custom cards (fallback option) |

---

*Built with MicroPython, Home Assistant, and Mosquitto MQTT. Cheers! 🍻*
