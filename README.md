# 🍺 ESP32 Keg Level Monitor

A complete DIY keg level monitor using a hall effect flow sensor, an ESP32, MicroPython, and Home Assistant. Tracks how much beer has been poured in real time and displays the remaining volume and percentage on a live dashboard.

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

## Parts List

| Part | Notes |
|---|---|
| ESP32 development board | Any standard ESP32 board works (e.g. ESP32-WROOM-32) |
| Gredia 1/4" Hall Effect Flow Sensor | Food-grade, 0.3–6 L/min range |
| 1/4" barbed fittings | To splice the sensor into your beer line |
| Jumper wires | 3 wires needed (power, ground, signal) |
| Home Assistant instance | Running on a Raspberry Pi, NUC, VM, etc. |
| USB cable | For flashing the ESP32 |

> **Note on keg size:** This guide is configured for a **5 US gallon corny keg (18.93 L)**. If you use a different size, update the `KEG_VOLUME_LITERS` constant in `flow_sensor.py`.

---

## How It Works

The flow sensor contains a small plastic rotor with a magnet. As beer flows through it, the rotor spins and the built-in hall effect sensor emits a pulse for every rotation. The ESP32 counts these pulses using a hardware interrupt and converts them to flow rate and volume using the sensor's calibration formula:

> **Flow rate (L/min) = pulse frequency (Hz) ÷ 23**

Every 10 seconds, the ESP32 publishes the current flow rate, total volume dispensed from the keg, liters remaining, and keg percentage to Home Assistant over MQTT. Home Assistant auto-discovers these as sensor entities — no manual configuration required.

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

Since you're running Home Assistant Container (without the Apps panel), you'll run Mosquitto as a separate Docker container.

### Step 1 — Run Mosquitto as a Docker Container

MQTT is the messaging protocol the ESP32 uses to send data to Home Assistant. Run the Mosquitto broker in Docker with authentication:

First, create a password file for Mosquitto:

```bash
# Create a directory for the config
mkdir -p ~/mosquitto/config

# Generate password file (replace mqtt_esp32 with your desired username)
docker run --rm -it eclipse-mosquitto:latest mosquitto_passwd -c ~/mosquitto/config/mosquitto.passwd mqtt_esp32
```

Create `~/mosquitto/config/mosquitto.conf`:

```
listener 1883
allow_anonymous false
password_file /mosquitto/config/mosquitto.passwd
```

Now run the container:

```bash
docker run -d \
  --name mosquitto \
  --restart unless-stopped \
  -p 1883:1883 \
  -v ~/mosquitto/config:/mosquitto/config \
  eclipse-mosquitto:latest \
  mosquitto -c /mosquitto/config/mosquitto.conf
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
esptool.py --port /dev/ttyUSB0 erase_flash
```

### Step 4 — Flash MicroPython

```bash
esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 460800 write_flash -z 0x1000 ESP32_GENERIC-*.bin
```

Replace `ESP32_GENERIC-*.bin` with the actual filename you downloaded.

### Step 5 — Install Thonny

Download from [thonny.org](https://thonny.org) and install it. Thonny is the easiest way to connect to the ESP32 and transfer files.

### Step 6 — Connect to the ESP32

1. Open Thonny
2. Go to **Tools → Options → Interpreter**
3. Select **MicroPython (ESP32)** from the dropdown
4. Select the correct COM port
5. Click **OK**

You should see a MicroPython REPL prompt (`>>>`) at the bottom of the Thonny window.

### Step 7 — Verify umqtt is Available

In the REPL, type:

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

In Thonny:

1. Open `flow_sensor.py` and save it as `main.py` on the MicroPython device
2. Open `secrets.py` and save it on the MicroPython device

### Step 3 — Test It

Press the **Reset** button on your ESP32 (or unplug and replug it). Watch the Thonny console — you should see:

```
Connecting to WiFi...
WiFi connected: 192.168.1.XXX
MQTT connected
Auto-discovery published to Home Assistant
Published → flow: 0.0 L/min | keg: 18.93L (100.0%)
```

In Home Assistant, go to **Settings → Devices & Services → MQTT** and you should see a new device called **Water Flow Sensor** with four entities:

- `sensor.water_flow_rate` — current flow rate in L/min
- `sensor.water_total_volume` — all-time total volume in L
- `sensor.keg_level` — keg fullness as a percentage
- `sensor.keg_remaining` — liters left in the keg

---

## Setting Up the Dashboard

Add the sensors to your Home Assistant dashboard:

1. Go to your Home Assistant dashboard
2. Click **Edit Dashboard** (three dots menu → Edit Dashboard)
3. Click **Add Card**
4. Search for and add an **Entities Card**
5. Select these entities:
   - `sensor.water_flow_rate` — current flow rate in L/min
   - `sensor.water_total_volume` — all-time total volume in L
   - `sensor.keg_level` — keg fullness as a percentage
   - `sensor.keg_remaining` — liters left in the keg
6. Click **Save**

You can also add individual **Sensor Cards** for each entity to customize the display.

---

## Resetting for a New Keg

When you put on a fresh keg, tap the **🔄 New Keg — Reset to Full** button on the dashboard. This publishes a reset message to `home/flow_sensor/reset` via MQTT, which tells the ESP32 to set the dispensed volume back to zero and treat the keg as 100% full.

You can also trigger the reset from any MQTT client, or via a Home Assistant automation, by publishing any message to:

```
home/flow_sensor/reset
```

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
The sensor's calibration constant (23 Hz per L/min) is nominal. If you want higher accuracy, you can calibrate it yourself by pouring a known volume (e.g. exactly 1 liter into a measuring jug) and adjusting the `PULSES_PER_LITER` constant in `flow_sensor.py` based on the actual pulse count observed.

---

## File Reference

| File | Description |
|---|---|
| `flow_sensor.py` | Main ESP32 firmware — deploy as `main.py` on the device |
| `secrets.py.example` | Template for WiFi/MQTT credentials — copy to `secrets.py` and configure |

---

*Built with MicroPython, Home Assistant, and Mosquitto MQTT. Cheers! 🍻*
