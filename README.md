# 🍺 ESP32 Keg Level Monitor

A complete DIY keg level monitor using a hall effect flow sensor, an ESP32, MicroPython, and Home Assistant. Tracks how much beer has been poured in real time and displays the remaining volume and percentage on a live dashboard.

---

## Table of Contents

1. [Parts List](#parts-list)
2. [How It Works](#how-it-works)
3. [Wiring](#wiring)
4. [Setting Up the MQTT Broker in Home Assistant](#setting-up-the-mqtt-broker-in-home-assistant)
5. [Flashing MicroPython to the ESP32](#flashing-micropython-to-the-esp32)
6. [Installing the Firmware](#installing-the-firmware)
7. [Configuring and Deploying the Code](#configuring-and-deploying-the-code)
8. [Setting Up the Home Assistant Dashboard](#setting-up-the-home-assistant-dashboard)
9. [Resetting for a New Keg](#resetting-for-a-new-keg)
10. [Troubleshooting](#troubleshooting)

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

## Setting Up the MQTT Broker in Home Assistant

MQTT is the messaging protocol the ESP32 uses to send data to Home Assistant. Home Assistant includes its own built-in MQTT broker called **Mosquitto** that you can install as an add-on in under five minutes.

### Step 1 — Install the Mosquitto Broker Add-on

1. In Home Assistant, go to **Settings → Add-ons → Add-on Store** (button in the bottom right)
2. Search for **"Mosquitto broker"**
3. Click it and then click **Install**
4. Once installed, click **Start**
5. Toggle on **Start on boot** and **Watchdog** so it restarts automatically

### Step 2 — Create an MQTT User Account

The ESP32 needs credentials to connect to the broker. The cleanest way to do this is to create a dedicated Home Assistant user:

1. Go to **Settings → People → Users**
2. Click **Add User**
3. Fill in a name (e.g. `mqtt_esp32`), username, and password
4. Turn **off** "Can log in" — this user is for devices only, not humans
5. Click **Create**

> Write down the username and password — you'll need them in the next section.

### Step 3 — Configure the Mosquitto Add-on

1. Go back to **Settings → Add-ons → Mosquitto broker**
2. Click the **Configuration** tab
3. The default configuration works out of the box. You don't need to add anything — Mosquitto automatically allows Home Assistant users to authenticate.
4. Click **Save**, then restart the add-on

### Step 4 — Add the MQTT Integration to Home Assistant

1. Go to **Settings → Devices & Services**
2. Click **Add Integration** and search for **MQTT**
3. Click **MQTT**
4. For the broker address, enter `core-mosquitto` (if running on the same machine) or your HA's local IP address
5. Port: `1883`
6. Enter the username and password you created in Step 2
7. Click **Submit**

Home Assistant will confirm the connection. You're now ready to receive data from the ESP32.

---

## Setting Up ESP32 Development Environment

This project uses MicroPython, but if you want to develop or debug further, you'll need the ESP32 toolchain.

For full setup instructions on Linux and macOS, see the official Espressif documentation:

**https://docs.espressif.com/projects/esp-idf/en/stable/esp32/get-started/linux-macos-setup.html**

This covers installing the ESP-IDF (Espressif IoT Development Framework), required dependencies, and configuring your environment for ESP32 development.

### Connecting with minicom (Ubuntu 24.04)

To connect to the ESP32 REPL over serial using minicom:

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

## Flashing MicroPython to the ESP32

If your ESP32 doesn't already have MicroPython on it, follow these steps.

### Step 1 — Install esptool

On your computer, open a terminal and run:

```bash
pip install esptool
```

### Step 2 — Download MicroPython

Go to [micropython.org/download/ESP32_GENERIC](https://micropython.org/download/ESP32_GENERIC/) and download the latest stable `.bin` firmware file.

### Step 3 — Erase the ESP32

Plug in your ESP32 via USB, then run (replace `COM3` with your port — on macOS/Linux it will look like `/dev/ttyUSB0` or `/dev/tty.usbserial-*`):

```bash
esptool.py --port COM3 erase_flash
```

### Step 4 — Flash MicroPython

```bash
esptool.py --chip esp32 --port COM3 --baud 460800 write_flash -z 0x1000 ESP32_GENERIC-*.bin
```

Replace `ESP32_GENERIC-*.bin` with the actual filename you downloaded.

---

## Installing the Firmware

You'll use **Thonny** to connect to the ESP32 and transfer files. It's the easiest option and works on Windows, macOS, and Linux.

### Step 1 — Install Thonny

Download from [thonny.org](https://thonny.org) and install it.

### Step 2 — Connect to the ESP32

1. Open Thonny
2. Go to **Tools → Options → Interpreter**
3. Select **MicroPython (ESP32)** from the dropdown
4. Select the correct COM port
5. Click **OK**

You should see a MicroPython REPL prompt (`>>>`) at the bottom of the Thonny window.

### Step 3 — Verify umqtt is Available

In the REPL, type:

```python
import umqtt.simple
```

If you get no error, you're good. If you get `ModuleNotFoundError`, install it by typing:

```python
import mip
mip.install("umqtt.simple")
```

---

## Configuring and Deploying the Code

### Step 1 — Edit the Configuration

Open `flow_sensor.py` and fill in your details at the top of the file:

```python
WIFI_SSID     = "your_wifi_ssid"
WIFI_PASSWORD = "your_wifi_password"

MQTT_BROKER   = "192.168.1.100"   # Your Home Assistant's local IP address
MQTT_PORT     = 1883
MQTT_USER     = "mqtt_esp32"      # The user you created in Mosquitto setup
MQTT_PASSWORD = "your_password"
```

To find your Home Assistant IP address, go to **Settings → System → Network** in HA.

### Step 2 — Upload the File

In Thonny:

1. Open `flow_sensor.py`
2. Go to **File → Save As**
3. When prompted, choose **MicroPython device**
4. Save it as `main.py` — MicroPython automatically runs `main.py` on boot

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

## Setting Up the Home Assistant Dashboard

The dashboard uses the **Bar Card** custom component for the keg level bar. Install it first, then add the card.

### Step 1 — Install Bar Card via HACS

If you don't have HACS (Home Assistant Community Store) installed, follow the guide at [hacs.xyz](https://hacs.xyz) first — it takes about 5 minutes.

Once HACS is installed:

1. Go to **HACS → Frontend**
2. Click **Explore & Download Repositories**
3. Search for **"Bar Card"**
4. Click it and click **Download**
5. Restart Home Assistant

### Step 2 — Add the Dashboard Card

1. Go to your Home Assistant dashboard
2. Click the **pencil icon** (Edit) in the top right
3. Click **Add Card**
4. Scroll to the bottom and select **Manual**
5. Delete the default YAML and paste in the contents of `keg_dashboard_card.yaml`
6. Click **Save**

The card will display:
- A color-coded fill bar (amber → orange → red as the keg empties)
- A glance row with percentage, liters remaining, and current flow rate
- A "New Keg — Reset to Full" button
- A 24-hour flow rate history graph

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
Double-check your SSID and password in `flow_sensor.py`. Make sure your network is 2.4 GHz — the ESP32 does not support 5 GHz.

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
| `flow_sensor.py` | Main ESP32 firmware — deploy this as `main.py` on the device |
| `keg_dashboard_card.yaml` | Home Assistant dashboard card YAML |

---

*Built with MicroPython, Home Assistant, and Mosquitto MQTT. Cheers! 🍻*
