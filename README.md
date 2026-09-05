# 🍺 ESP32 Keg Level Monitor

A complete DIY keg level monitor using a hall effect flow sensor, an ESP32, MicroPython, and Home Assistant. Tracks how much beer has been poured in real time and displays the remaining volume and percentage on a live dashboard.

**Tested with:** Home Assistant Core 2026.2.3 / Frontend 20260128.6

---

## Prerequisites

This project uses a Python virtual environment for tooling. Set it up once:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install mpremote esptool pylint
```

All commands below assume the venv is active. Activate it with `source .venv/bin/activate` or prefix commands with `.venv/bin/` (e.g. `.venv/bin/mpremote`).

### Finding the USB Device

```bash
ls /dev/ttyUSB*   # Usually /dev/ttyUSB0
lsusb             # List USB devices (ESP32 shows as "CP2102" or "CH340")
```

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

The ESP32 automatically publishes a JSON state payload to `home/flow_sensor/state` every publish cycle:

| Entity | Payload Key | Description |
|--------|-------------|-------------|
| Flow Rate | `flow_rate` | Current flow rate in L/min |
| Dispensed | `total_volume` | Total beer dispensed from the keg (L) |
| Remaining | `keg_remaining` | Liters remaining in the keg |
| Keg Level | `keg_percent` | Keg fullness as a percentage (0-100) |
| Last Updated | `last_updated` | Timestamp of the last publish |
| Firmware Version | `version` | Firmware version string, e.g. `1.3.1` |

Home Assistant auto-discovers all of these as sensor entities — no manual configuration required. A **Reset Keg** button and a **Stay Awake** switch are auto-discovered too (see below).

### Checking the Firmware Version

The version is logged at boot (`Flow Sensor v1.3.1`) and published in the MQTT payload (visible as the **Firmware Version** sensor in HA). From a WebREPL REPL you can also run:

```python
import main
print(main.VERSION)
```

Bump the `VERSION` constant in `main.py` on every firmware change so you can always tell what's running on the device.

### Versioning

This project follows [Semantic Versioning 2.0.0](https://semver.org/). The public API is the MQTT interface — the topics published by the device and the JSON keys in the state payload. Bump accordingly:

- **MAJOR** — breaking change to the MQTT interface (a topic or payload key is removed, renamed, or changes meaning)
- **MINOR** — backward-compatible addition (e.g. a new payload key, like `version`)
- **PATCH** — backward-compatible bug fix (e.g. a calibration adjustment)

Every commit that changes firmware code is itself a version bump, so `VERSION` always reflects exactly what is deployed on the device; a commit that only touches docs, tests, or HA config keeps `VERSION`.

The `VERSION` string in `main.py` is always the semantic version, and it must stay in sync with the git release tag `v<VERSION>` (e.g. `VERSION = "1.3.1"` ↔ tag `v1.3.1`).

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

The flow sensor contains a small plastic rotor with a magnet. As beer flows through it, the rotor spins and the built-in hall effect sensor emits a pulse for every rotation. The ESP32 counts these pulses using a hardware interrupt and converts them to flow rate and volume using the sensor's calibration constant (`PULSES_PER_LITER`):

> **Flow rate (L/min) = pulse frequency (Hz) × 60 ÷ PULSES_PER_LITER**

The device deepsleeps to conserve battery, waking every 4.5 minutes — and immediately whenever a pour is detected — to publish the current flow rate, total volume dispensed from the keg, liters remaining, and keg percentage to Home Assistant over MQTT. While awake it publishes every 30 seconds. Home Assistant auto-discovers all entities — no manual configuration required.

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

Mosquitto must run somewhere on your network. If you use Home Assistant OS or Supervised, the easiest option is the **Mosquitto broker** add-on (Settings → Add-ons → Mosquitto broker). The steps below cover the Docker/Container case, running Mosquitto as a separate container.

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

MQTT_BROKER   = "192.168.1.100"   # Your MQTT broker / Home Assistant IP address
MQTT_PORT     = 1883
MQTT_USER     = "mqtt_esp32"      # Username from mosquitto_passwd command
MQTT_PASSWORD = "your_password"   # Password from mosquitto_passwd command
MQTT_CLIENT_ID = "esp32_flow_sensor"
```

To find the IP to use for `MQTT_BROKER`, run `hostname -I` on the machine running the broker (the Home Assistant VM/host).

### Step 2 — Upload the Files

Using **mpremote**:

```bash
# Copy secrets.py
mpremote connect /dev/ttyUSB0 fs cp secrets.py :secrets.py

# Deploy main.py
mpremote connect /dev/ttyUSB0 fs cp main.py :main.py

# Deploy calculations.py
mpremote connect /dev/ttyUSB0 fs cp calculations.py :calculations.py

# Deploy state.py
mpremote connect /dev/ttyUSB0 fs cp state.py :state.py

# Deploy mqtt.py
mpremote connect /dev/ttyUSB0 fs cp mqtt.py :mqtt.py

# (Optional) Deploy fresh state file
mpremote connect /dev/ttyUSB0 fs cp flow_state.json :flow_state.json
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
[2026-07-13 10:01:05] Connecting to WiFi...
[2026-07-13 10:01:08] WiFi connected: 192.168.1.XXX
[2026-07-13 10:01:09] NTP synced
[2026-07-13 10:01:09] WebREPL at ws://192.168.1.XXX:8266
[2026-07-13 10:01:09] Boot — deepsleep, will sleep after publish
[2026-07-13 10:01:09]   dispensed=0.0L, pulses=0
[2026-07-13 10:01:38] Published — flow: 0.0 L/min | remaining: 18.93L (100.0%)
[2026-07-13 10:02:08] Entering deepsleep for 4m 30s...
```

In Home Assistant, go to **Settings → Devices & Services → MQTT** and you should see a new device called **Flow Rate Sensor** with these entities:

- `sensor.flow_rate` — current flow rate in L/min
- `sensor.total_volume` — total volume dispensed from the keg (L)
- `sensor.keg_remaining` — liters left in the keg
- `sensor.keg_level` — keg fullness as a percentage
- `sensor.last_updated` — timestamp of the last publish
- `sensor.version` — firmware version (e.g. `1.3.1`)
- `button.flow_sensor_reset_keg` — resets the keg dispensed counter to zero
- `switch.flow_sensor_stay_awake` — keeps the device awake for WebREPL access

---

## Setting Up the Dashboard in Home Assistant

All entities are auto-discovered, so you can use any cards you like. Two sample dashboards ship with this repo:

- **`keg_dashboard.yaml`** — simple YAML dashboard (gauge + entity list), no extra components
- **`keg_dashboard_card.yaml`** — vertical-stack that uses the HACS **bar-card** (install `custom:bar-card` from HACS first)

To load a YAML dashboard: **Settings → Dashboards → Add Dashboard → YAML**, then paste the file's contents.

To build cards in the UI, add a card and pick from these entities:

- `sensor.flow_rate`, `sensor.total_volume`, `sensor.keg_remaining`, `sensor.keg_level`, `sensor.last_updated`
- `button.flow_sensor_reset_keg` — press to zero the dispensed counter for a new keg
- `switch.flow_sensor_stay_awake` — disables deepsleep for remote WebREPL access

No `configuration.yaml` MQTT entries are needed — the button and switch are created automatically by auto-discovery.

## Resetting for a New Keg

When you put on a fresh keg, press the **Reset Keg** button in Home Assistant
(`button.flow_sensor_reset_keg`), or publish any message to `home/flow_sensor/reset` from any
MQTT client or automation. This tells the ESP32 to set the dispensed volume back to zero and
treat the keg as 100% full again.

---

## State Management

The ESP32 persists its state to flash storage so it survives deepsleep cycles and device reboots.

### State File

The device stores state in `/flow_state.json` on the ESP32's flash filesystem:

```json
{"keg_dispensed": 0.0, "total_pulses": 0, "stay_awake_enabled": false}
```

| Field | Description | Reset? |
|-------|-------------|--------|
| `keg_dispensed` | Liters poured from current keg | Yes — Reset Keg button |
| `total_pulses` | Lifetime pulse count | No — never reset |
| `stay_awake_enabled` | Whether the Stay Awake switch is ON | No — toggled in HA |

A `flow_state.json` template is included in the project directory. You can deploy it to the device:

```bash
mpremote connect /dev/ttyUSB0 fs cp flow_state.json :flow_state.json
```

### When State is Saved

- **After each MQTT publish cycle** — so state survives the sleep/wake cycle
- **After an MQTT reset command** — persists the keg reset to flash
- **After the Stay Awake switch is toggled** — persists the toggle to flash

### Resetting State

**From Home Assistant:** Press the auto-discovered **Reset Keg** button (`button.flow_sensor_reset_keg`), or publish any message to `home/flow_sensor/reset` from any MQTT client or automation.

**Manually on device:** Connect via WebREPL or mpremote:

```python
import state as state_module
s = state_module.load()
s["keg_dispensed"] = 0.0
state_module.save(s)
```

The device subscribes to `home/flow_sensor/reset` and acts on commands during the 5-second command window after each publish (`COMMAND_LISTEN_SECONDS`). Because the reset button publishes with retain, a press while the device is asleep is applied on its next wake.

### Viewing State

```bash
mpremote connect /dev/ttyUSB0 eval "open('/flow_state.json').read()"
```

---

## Waking the Device for WebREPL Access

The ESP32 spends most of its time in deepsleep to conserve battery. It is only
reachable over the network while awake.

### Enable the Stay Awake Switch

Turn on the **Stay Awake** switch in Home Assistant (auto-discovered as a switch).
This disables deepsleep indefinitely, keeping the device awake for WebREPL access.

### Connect via WebREPL

Find the device IP (`WebREPL at ws://<esp32-ip>:8266` in the boot log, or in
Home Assistant). Then connect (WebREPL password is in 1Password):

```bash
# REPL over the network
python webrepl_cli.py <esp32-ip>    # interactive REPL
# Exit: Ctrl+] or Ctrl+X

# Copy files to the device over the network:
#   get  <remote> <local>   → download from device
#   put  <local> <remote>   → upload to device
python webrepl_cli.py <esp32-ip> put main.py /main.py
```

Toggle the Stay Awake switch off when done to resume normal deepsleep operation.

### Wait for Next Wake Cycle

The device wakes every 4.5 minutes to publish data. During this window, you can connect to WebREPL.

---

## Battery Optimization

The ESP32 uses **deepsleep** mode to achieve long battery life:

- **Active:** ~150-250mA (WiFi + MQTT publishing, ~30 seconds per cycle)
- **Sleep:** ~10µA (deepsleep with RAM off, only RTC running)

On a 10,000 mAh battery bank, expect **~4-6 months** of operation under normal use.

> **Note:** The device shows "offline" in Home Assistant while in deepsleep. It only appears "online" during the ~30-second minimum awake window every 4.5 minutes (`MINIMUM_AWAKE_SECONDS`).

### Configuration

Key settings in `main.py`:

| Constant | Default | Description |
| ---------- | --------- | ------------- |
| `VERSION` | `1.3.1` | Firmware version — bump every commit that changes firmware, matches git tag |
| `PUBLISH_INTERVAL` | 30s | Time between MQTT publishes while awake |
| `SLEEP_INTERVAL` | 270000ms | Deepsleep duration (4.5 minutes) |
| `COMMAND_LISTEN_SECONDS` | 5 | Seconds to listen for HA commands after each publish |
| `MINIMUM_AWAKE_SECONDS` | 30 | Minimum time the device stays awake per cycle |
| `TIMEZONE_BASE` | -28800 | Timezone offset in seconds (-8×60×60 for PST) |
| `PULSES_PER_LITER` | 5880 | Sensor calibration (pulses per liter) — in `calculations.py` |

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
The sensor's calibration constant (`PULSES_PER_LITER = 5880` in `calculations.py`) comes from the datasheet formula `F (Hz) = 98 × Q (L/min)` — so 5880 pulses per liter. If you want to check/refine it, pour a precisely measured volume (e.g. exactly 1 liter into a measuring jug) and set `PULSES_PER_LITER` to the pulse count actually observed.

**State not persisting across deepsleep**
The state file (`/flow_state.json`) should exist on the device. If it's missing or corrupt, the device falls back to a fresh state on boot — redeploy it: `mpremote connect /dev/ttyUSB0 fs cp flow_state.json :flow_state.json`

**Device shows offline in Home Assistant**
This is expected behavior — the device is in deepsleep most of the time. It only appears online during the ~30-second minimum awake window every 4.5 minutes. Turn on the Stay Awake switch (`switch.flow_sensor_stay_awake`) to keep it online for WebREPL access.

---

## File Reference

| File | Description |
| --- | --- |
| `main.py` | Main ESP32 firmware — deploy as `main.py` on the device |
| `calculations.py` | Flow rate, keg math, MQTT payload, timestamps |
| `state.py` | State persistence and transitions (`on_reset`, `on_pulse`, `on_publish`) |
| `mqtt.py` | MQTT connect/disconnect, publishing, HA auto-discovery |
| `webrepl_cli.py` | WebREPL client for remote connection and file transfer |
| `secrets.py.example` | Template for WiFi/MQTT credentials — copy to `secrets.py` and configure |
| `flow_state.json` | Persisted device state — deploy to device for a fresh start |
| `tests/test_device.py` | On-device tests (run with `mpremote`, see AGENTS.md) |
| `keg_dashboard_card.yaml` | Home Assistant dashboard YAML with bar-card (requires HACS) |
| `keg_dashboard.yaml` | Simple YAML dashboard without custom cards |

---

*Built with MicroPython, Home Assistant, and Mosquitto MQTT. Cheers! 🍻*
