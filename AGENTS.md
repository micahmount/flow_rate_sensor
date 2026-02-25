# AGENTS.md - Flow Rate Sensor Project

## Project Overview

This is a **MicroPython** project for an ESP32 microcontroller that reads a hall effect flow sensor and publishes data to Home Assistant via MQTT. The code runs directly on the ESP32 device.

- **Language**: MicroPython (subset of Python 3 for embedded devices)
- **Target Hardware**: ESP32
- **Main File**: `flow_sensor.py` (deploy as `main.py` on device)

---

## Build / Deploy Commands

### Deploying to ESP32

This project uses **Thonny** or **esptool** for deployment:

```bash
# Install esptool
pip install esptool

# Erase ESP32 flash
esptool.py --port /dev/ttyUSB0 erase_flash

# Flash MicroPython firmware
esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 460800 write_flash -z 0x1000 ESP32_GENERIC-*.bin

# Deploy flow_sensor.py as main.py using Thonny
# File → Save As → MicroPython device → main.py
```

### Testing / REPL

Connect to the ESP32 REPL via Thonny or minicom:

```bash
# Using minicom (Ubuntu)
minicom -D /dev/ttyUSB0 -b 115200
# Exit: Ctrl+A, then X, then Enter
```

### Running a Single Test

**No formal test suite exists.** This is an embedded project without automated tests. Test manually by:
1. Deploying code to the ESP32
2. Watching the serial output
3. Checking Home Assistant for MQTT entities

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

### Adding New Features

1. Edit `flow_sensor.py`
2. Deploy to ESP32 using Thonny
3. Monitor serial output
4. Verify MQTT messages arrive in Home Assistant

### Known Issues / Gotchas

- MicroPython doesn't support all standard library modules
- Memory is limited; avoid large data structures
- The flow sensor calibration constant (`23`) may need adjustment for accuracy

### Configuration Required Before Deploy

Edit these values in `flow_sensor.py`:

```python
WIFI_SSID     = "your_wifi_ssid"
WIFI_PASSWORD = "your_wifi_password"

MQTT_BROKER   = "192.168.1.100"   # Your Home Assistant IP
MQTT_PORT     = 1883
MQTT_USER     = "mqtt_esp32"
MQTT_PASSWORD = "your_password"
```

### Resources

- [MicroPython ESP32 documentation](https://docs.micropython.org/en/latest/esp32/)
- [ESP-IDF setup](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/get-started/)
- [Home Assistant MQTT integration](https://www.home-assistant.io/integrations/mqtt/)
