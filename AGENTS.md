# AGENTS.md - Flow Rate Sensor Project

## Prerequisites

This project uses a Python virtual environment. Set it up once:

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

## Testing

**All tests require the ESP32 device connected to `/dev/ttyUSB0`.**

Deploy and run tests on the device:

```bash
# Deploy all files
mpremote connect /dev/ttyUSB0 fs cp main.py :main.py
mpremote connect /dev/ttyUSB0 fs cp calculations.py :calculations.py
mpremote connect /dev/ttyUSB0 fs cp state.py :state.py
mpremote connect /dev/ttyUSB0 fs cp mqtt.py :mqtt.py
mpremote connect /dev/ttyUSB0 fs cp secrets.py :secrets.py
mpremote connect /dev/ttyUSB0 fs cp tests/test_device.py :test_device.py

# Run tests on device
mpremote connect /dev/ttyUSB0 run test_device.py

# Clean up
mpremote connect /dev/ttyUSB0 fs rm :test_device.py
```

Tests cover: flow rate calculations, keg math, MQTT payload, state persistence,
state transitions (on_reset, on_pulse, on_publish), and predicates (should_publish, should_sleep).

---

This is a **MicroPython** project for an ESP32 microcontroller that reads a hall effect flow sensor and publishes data to Home Assistant via MQTT. The code runs directly on the ESP32 device.

- **Language**: MicroPython (subset of Python 3 for embedded devices)
- **Target Hardware**: ESP32
- **Main File**: `main.py` (the default entry point for MicroPython devices)

---

## Build / Deploy Commands

### Step 1: Set Up Mosquitto MQTT Broker in HA

The ESP32 publishes to the Mosquitto broker running as a Home Assistant add-on.
Install it once via **Settings → Add-ons → Mosquitto broker** in HA, then configure
credentials and update `secrets.py` with the HA VM's IP address.

### Step 2: Deploy Code to ESP32

This project uses **mpremote** for deployment:

```bash
# Install mpremote
.venv/bin/pip install mpremote

# Deploy all files
mpremote connect /dev/ttyUSB0 fs cp main.py :main.py
mpremote connect /dev/ttyUSB0 fs cp calculations.py :calculations.py
mpremote connect /dev/ttyUSB0 fs cp state.py :state.py
mpremote connect /dev/ttyUSB0 fs cp mqtt.py :mqtt.py
mpremote connect /dev/ttyUSB0 fs cp secrets.py :secrets.py

# Reset the device
mpremote connect /dev/ttyUSB0 reset
```

Or use **esptool** to flash firmware:

```bash
# Install esptool
.venv/bin/pip install esptool

# Erase ESP32 flash
esptool.py --port /dev/ttyUSB0 erase_flash

# Flash MicroPython firmware
esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 460800 write_flash -z 0x1000 ESP32_GENERIC-*.bin
```

### Testing / REPL

The device deepsleeps whenever the Stay Awake switch is OFF, so it only accepts
connections while awake. To connect over the network, enable the **Stay Awake** switch
in Home Assistant first, then find the device's IP (in the WebREPL boot log or HA).

Remote WebREPL connection (WebREPL password is stored in 1Password, item
["ESP32 WebREPL"](https://start.1password.com/open/i?a=ZA7QIWQDIRFJ3I2ODNWLZZEHRE&v=72wcldx66iirrhlsaai6p27xfq&i=llo7hiepf7xyttplo2uhhsjmri&h=the-mounts.1password.com)):

```bash
# REPL over the network
python webrepl_cli.py <esp32-ip>    # interactive REPL
# Exit: Ctrl+] or Ctrl+X

# Copy files to the device over the network:
#   get  <remote> <local>   → download from device
#   put  <local> <remote>   → upload to device
python webrepl_cli.py <esp32-ip> put main.py /main.py
```

Serial connection (only when the device is physically attached via USB):

```bash
# Using mpremote
mpremote connect /dev/ttyUSB0 repl

# Using minicom (Ubuntu)
minicom -D /dev/ttyUSB0 -b 115200
# Exit: Ctrl+A, then X, then Enter
```

### Manual Hardware Testing

Hardware integration tests (WiFi, MQTT, deepsleep) must be tested manually:

1. Deploy code to the ESP32
2. Watch the serial output
3. Check Home Assistant for MQTT entities

---

## Code Style Guidelines

### General Principles

- This is **MicroPython** (not full Python). Use `ujson` instead of `json`, `umqtt.simple` instead of `paho-mqtt`.
- Keep code simple and memory-efficient for embedded constraints.
- Use underscores (`snake_case`) for all identifiers.

### Imports

```python
# Standard library (MicroPython-compatible only)
import network
import time
from machine import Pin
from umqtt.simple import MQTTClient
import ujson
```

- Group imports: stdlib → external (machine, umqtt)
- Use blank line between groups

### Formatting

- **Max line length**: 120 characters (but prefer shorter when readable)
- **Indentation**: 4 spaces (no tabs)
- **Section headers**: Use comment blocks like `# ─── WiFi ─────────────────────────────────────`
- **Constants**: ALL_CAPS with underscores (e.g., `WIFI_SSID`, `KEG_VOLUME_LITERS`)
- **Globals**: Descriptive names, defined at module level (e.g., `pulse_count`, `keg_dispensed`)

### Types

- MicroPython is dynamically typed, but use type hints where beneficial
- Literal types for constants: `int`, `float`
- Document expected types in docstrings

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Constants | UPPER_SNAKE_CASE | `KEG_VOLUME_LITERS` |
| Variables | snake_case | `pulse_count` |
| Functions | snake_case | `connect_wifi()` |
| Classes | PascalCase | `MQTTClient` (from library) |
| Module-level globals | snake_case | `keg_dispensed` |
| MQTT topics | lowercase with slashes | `home/flow_sensor/state` |

### Functions

- Use concise, single-purpose functions
- Document with docstrings for public APIs
- Keep functions under 50 lines

### Error Handling

- Use minimal error handling for embedded reliability
- Catch broad exceptions only when necessary
- Print errors to console for debugging
- Use `try/except` sparingly around I/O operations (WiFi, MQTT)

```python
# Good: minimal error handling
try:
    client.check_msg()
except Exception:
    pass
```

### Configuration

- Put all configurable constants at the top of the file under `# ─── Configuration ────────────────────────────────────────────────────────────`
- Users should only need to modify the configuration section
- Include comments explaining each setting

### MQTT Topics

- Use bytes (`b"topic"`) for topic literals
- Follow Home Assistant conventions: `home/flow_sensor/<entity>`

### File Structure

```
# ─── Section Name ────────────────────────────────────────────────────────────

# Imports
# Configuration
# Globals
# Helper functions
# Main functions
# Entry point (main())
```

---

## Working with This Project

### Linting

```bash
# Install pylint (first time)
.venv/bin/pip install pylint

# Run lint
.venv/bin/pylint main.py
```

### Adding New Features

1. Run `pylint main.py` — target 10/10
2. Bump `VERSION` in `main.py` on **every commit** — every commit is a version bump (no carve-out for docs or tests) — using [Semantic Versioning](https://semver.org/), and keep it in sync with the git release tag (`v<VERSION>`). Rules: **MAJOR** = breaking MQTT-interface change (topic/payload key removed or renamed), **MINOR** = backward-compatible feature (e.g. new payload key), **PATCH** = backward-compatible bug fix (e.g. calibration). Verify with `import main; main.VERSION` or the HA Firmware Version sensor
3. Deploy to ESP32 using mpremote
4. Test on device (see Testing section)
5. Monitor serial output
6. Verify MQTT messages arrive in Home Assistant
7. When releasing, tag the release commit with exactly `v<VERSION>`: `git tag -a v<VERSION> -m "Release v<VERSION>"` and push the tag. The tag and `main.VERSION` must always match.

### Known Issues / Gotchas

- MicroPython doesn't support all standard library modules
- Memory is limited; avoid large data structures
- The flow sensor calibration constant (`PULSES_PER_LITER`) lives in `calculations.py` and may need adjustment for accuracy

### Configuration Required Before Deploy

Edit these values in `secrets.py`:

```python
WIFI_SSID     = "your_wifi_ssid"
WIFI_PASSWORD = "your_wifi_password"

MQTT_BROKER   = "192.168.1.100"   # Your Home Assistant VM's IP
MQTT_PORT     = 1883
MQTT_USER     = "mqtt_esp32"
MQTT_PASSWORD = "your_password"
MQTT_CLIENT_ID = "esp32_flow_sensor"
```

### Resources

- [MicroPython ESP32 documentation](https://docs.micropython.org/en/latest/esp32/)
- [ESP-IDF setup](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/get-started/)
- [Home Assistant MQTT integration](https://www.home-assistant.io/integrations/mqtt/)

---

## Home Assistant Configuration

No manual HA config needed — install the Mosquitto add-on once via the HA UI,
then the ESP32 publishes auto-discovery topics automatically.
All entities (Flow Rate, Dispensed, Keg Level, Last Updated, Firmware Version, Reset button, Stay Awake switch)
appear automatically in HA.

### Stay Awake Switch

The Stay Awake switch keeps the device awake indefinitely (disables deepsleep) for WebREPL
access or debugging. Turn it on to connect to the device remotely via WebREPL
(`python webrepl_cli.py <esp32-ip>`); the device will not sleep until you toggle it off.
Toggle it off when done to resume normal deepsleep operation.
