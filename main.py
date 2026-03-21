# Gredia 1/4" Hall Effect Flow Sensor — ESP32 MicroPython
# This is main.py - the primary script that runs on the ESP32 device
# Publishes flow rate (L/min) and total volume (L) to Home Assistant via MQTT
#
# Wiring:
#   Red    → 3.3V or 5V
#   Black  → GND
#   Yellow → GPIO 4

import network
import time
import ntptime
import webrepl
import esp32
from machine import Pin, deepsleep
from umqtt.simple import MQTTClient
import ujson
import calculations
try:
    import secrets
except ImportError as exc:
    raise ImportError("secrets.py not found. Copy secrets.py.example to secrets.py and configure.") from exc

# ─── Configuration ────────────────────────────────────────────────────────────

WIFI_SSID     = secrets.WIFI_SSID
WIFI_PASSWORD = secrets.WIFI_PASSWORD

MQTT_BROKER   = secrets.MQTT_BROKER
MQTT_PORT     = secrets.MQTT_PORT
MQTT_USER     = secrets.MQTT_USER
MQTT_PASSWORD = secrets.MQTT_PASSWORD
MQTT_CLIENT_ID = secrets.MQTT_CLIENT_ID

# MQTT topics
TOPIC_STATE        = b"home/flow_sensor/state"
TOPIC_AVAILABILITY = b"home/flow_sensor/availability"
TOPIC_RESET        = b"home/flow_sensor/reset"
TOPIC_WAKE         = b"home/flow_sensor/wake"

# WebREPL configured via webrepl_setup

# Keg
KEG_VOLUME_LITERS  = 18.93  # 5 US gallons

# Sensor
FLOW_PIN          = 4       # GPIO pin connected to yellow wire
PULSES_PER_LITER  = 450     # pulses per liter (calibrate: 450 is common for these sensors)
PUBLISH_INTERVAL  = 30      # seconds between MQTT publishes (battery saver)
SLEEP_INTERVAL    = 270000  # ms to sleep between cycles (4.5 minutes)
WAKE_TIMEOUT_SECONDS = 300  # stay awake for 5 minutes after wake command
COMMAND_LISTEN_SECONDS = 2   # stay connected after publish to receive HA commands
TIMEZONE_BASE    = -8 * 60 * 60  # base timezone offset in seconds (e.g., -8 for PST)
DEBOUNCE_MS       = 50      # debounce time in milliseconds (increased to prevent false triggers)
MAX_FLOW_RATE     = 30      # maximum possible flow rate in L/min (sanity check)
MIN_PULSE_MS      = 2       # minimum time between valid pulses (physical limit of sensor)

# ─── Globals ──────────────────────────────────────────────────────────────────

pulse_count     = 0
total_pulses    = 0
keg_dispensed   = 0.0
last_publish    = 0
last_pulse_time = 0
prev_count      = 0
wlan            = None
client          = None
discovery_done   = False
stay_awake      = 0
flow_detected   = False
sensor_pin      = None

# ─── Interrupt handler ────────────────────────────────────────────────────────

def log(msg):
    t = time.localtime()
    tz_offset = calculations.get_timezone_offset(t[1], TIMEZONE_BASE)
    t = time.localtime(time.time() + tz_offset)
    ts = f"{t[0]}-{t[1]:02d}-{t[2]:02d} {t[3]:02d}:{t[4]:02d}:{t[5]:02d}"
    print(f"[{ts}] {msg}")

def pulse_handler(pin):
    global pulse_count, total_pulses, last_pulse_time, flow_detected
    now = time.ticks_ms()

    # Validate timing between pulses
    pulse_diff = time.ticks_diff(now, last_pulse_time)
    if pulse_diff < MIN_PULSE_MS:  # Physically impossible, must be noise
        return
    if pulse_diff < DEBOUNCE_MS:   # Within debounce window
        return

    # Calculate instantaneous flow rate for validation
    # flow = (1 pulse / time_diff_seconds) * (60 seconds/minute) * (1 liter/PULSES_PER_LITER)
    inst_flow_rate = (1 / (pulse_diff / 1000)) * 60 / PULSES_PER_LITER

    # Reject physically impossible flow rates
    if inst_flow_rate > MAX_FLOW_RATE:
        return

    last_pulse_time = now
    pulse_count  += 1
    total_pulses += 1
    flow_detected = True

# ─── State Persistence ────────────────────────────────────────────────────────

def load_state():
    global keg_dispensed, total_pulses, stay_awake
    keg_dispensed, total_pulses, stay_awake = calculations.load_state()
    log(f"State loaded: dispensed={keg_dispensed}L, pulses={total_pulses}")


def save_state():
    global keg_dispensed, total_pulses, stay_awake
    try:
        calculations.save_state(keg_dispensed, total_pulses, stay_awake)
    except Exception as e:
        log("State save error: " + str(e))

# ─── WiFi ─────────────────────────────────────────────────────────────────────

def connect_wifi():
    global wlan
    if wlan is not None and wlan.isconnected():
        return wlan

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.config(pm=0)
    if not wlan.isconnected():
        log("Connecting to WiFi...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        for _ in range(20):
            if wlan.isconnected():
                break
            time.sleep(1)
    if wlan.isconnected():
        log("WiFi connected: " + wlan.ifconfig()[0])
        try:
            ntptime.settime()
            log("NTP time synced")
        except Exception as e:
            log("NTP sync failed: " + str(e))
        return wlan
    log("WiFi connection failed, retrying...")
    return None

# ─── MQTT ─────────────────────────────────────────────────────────────────────

def connect_mqtt():
    client = MQTTClient(
        MQTT_CLIENT_ID,
        MQTT_BROKER,
        port=MQTT_PORT,
        user=MQTT_USER,
        password=MQTT_PASSWORD,
        keepalive=60
    )
    client.set_last_will(TOPIC_AVAILABILITY, b"offline", retain=True)
    client.set_callback(mqtt_callback)
    client.connect()
    client.subscribe(TOPIC_RESET)
    client.subscribe(TOPIC_WAKE)
    client.publish(TOPIC_AVAILABILITY, b"online", retain=True)
    log("MQTT connected")
    return client

def mqtt_callback(topic, msg):
    global keg_dispensed, stay_awake
    if topic == TOPIC_RESET:
        calculations.reset_keg(keg_dispensed, total_pulses, stay_awake)
        keg_dispensed = 0.0
        log("Keg reset to full (18.93 L)")
    elif topic == TOPIC_WAKE:
        stay_awake = WAKE_TIMEOUT_SECONDS
        save_state()
        log("Wake command received, staying awake for " + str(WAKE_TIMEOUT_SECONDS) + "s")

def publish_discovery(client):
    """
    Publish Home Assistant MQTT auto-discovery messages.
    Call once on startup — HA will automatically create two sensor entities.
    """
    device = {
        "identifiers": ["esp32_flow_sensor"],
        "name": "Water Flow Sensor",
        "model": "Gredia 1/4\" Hall Effect",
        "manufacturer": "Gredia"
    }

    # Flow rate sensor
    rate_config = {
        "name": "Flow Rate",
        "unique_id": "water_flow_rate",
        "state_topic": TOPIC_STATE.decode(),
        "availability_topic": TOPIC_AVAILABILITY.decode(),
        "value_template": "{{ value_json.flow_rate }}",
        "unit_of_measurement": "L/min",
        "device_class": "volume_flow_rate",
        "state_class": "measurement",
        "icon": "mdi:water-pump",
        "force_update": True,
        "device": device
    }

    # Total volume sensor
    volume_config = {
        "name": "Dispensed",
        "unique_id": "water_total_volume",
        "state_topic": TOPIC_STATE.decode(),
        "availability_topic": TOPIC_AVAILABILITY.decode(),
        "value_template": "{{ value_json.total_volume }}",
        "unit_of_measurement": "L",
        "device_class": "water",
        "state_class": "total_increasing",
        "icon": "mdi:water",
        "force_update": True,
        "device": device
    }

    # Keg level sensor
    keg_config = {
        "name": "Keg Level",
        "unique_id": "keg_level",
        "state_topic": TOPIC_STATE.decode(),
        "availability_topic": TOPIC_AVAILABILITY.decode(),
        "value_template": "{{ value_json.keg_percent }}",
        "unit_of_measurement": "%",
        "state_class": "measurement",
        "icon": "mdi:beer",
        "force_update": True,
        "device": device
    }

    # Keg remaining (liters)
    keg_liters_config = {
        "name": "Remaining",
        "unique_id": "keg_remaining",
        "state_topic": TOPIC_STATE.decode(),
        "availability_topic": TOPIC_AVAILABILITY.decode(),
        "value_template": "{{ value_json.keg_remaining }}",
        "unit_of_measurement": "L",
        "device_class": "water",
        "state_class": "measurement",
        "icon": "mdi:beer-outline",
        "force_update": True,
        "device": device
    }

    client.publish(
        b"homeassistant/sensor/flow_sensor/keg_level/config",
        ujson.dumps(keg_config).encode(),
        retain=True
    )
    client.publish(
        b"homeassistant/sensor/flow_sensor/keg_remaining/config",
        ujson.dumps(keg_liters_config).encode(),
        retain=True
    )
    client.publish(
        b"homeassistant/sensor/flow_sensor/flow_rate/config",
        ujson.dumps(rate_config).encode(),
        retain=True
    )
    client.publish(
        b"homeassistant/sensor/flow_sensor/total_volume/config",
        ujson.dumps(volume_config).encode(),
        retain=True
    )

    # Wake button
    wake_config = {
        "name": "Flow Sensor Wake",
        "unique_id": "flow_sensor_wake",
        "command_topic": TOPIC_WAKE.decode(),
        "payload_press": "WAKE",
        "device": device
    }
    client.publish(
        b"homeassistant/button/flow_sensor_wake/config",
        ujson.dumps(wake_config).encode(),
        retain=True
    )
    log("Auto-discovery published to Home Assistant")

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    global pulse_count, last_publish, keg_dispensed, total_pulses
    global last_pulse_time, prev_count, wlan, client, discovery_done, stay_awake
    global flow_detected, sensor_pin

    # Load persisted state
    load_state()

    # Set up sensor pin with interrupt
    sensor_pin = Pin(FLOW_PIN, Pin.IN, Pin.PULL_UP)
    sensor_pin.irq(trigger=Pin.IRQ_RISING, handler=pulse_handler)

    # Initialize WiFi and WebREPL
    wlan = connect_wifi()
    if wlan is not None:
        try:
            webrepl.start()
            log(f"WebREPL started at ws://{wlan.ifconfig()[0]}:8266")
        except Exception as e:
            log("WebREPL error: " + str(e))

    client = None
    discovery_done = False

    # Initialize last_publish to ensure first loop publishes
    if last_publish == 0:
        last_publish = time.time() - PUBLISH_INTERVAL

    while True:
        try:
            flow_detected = False  # Reset each cycle
            now = time.time()
            elapsed = now - last_publish

            # Check if there's flow happening
            current_count = pulse_count
            has_flow = current_count > prev_count
            prev_count = current_count

            # Publish if interval reached OR if flow just started
            should_publish = elapsed >= PUBLISH_INTERVAL or (has_flow and elapsed >= 5)

            if should_publish:
                log(f"Attempting publish... elapsed={elapsed:.1f}s, has_flow={has_flow}")
                # Connect WiFi
                wlan = connect_wifi()
                if wlan is None:
                    time.sleep(5)
                    continue

                # Connect MQTT
                try:
                    client = connect_mqtt()
                    if not discovery_done:
                        publish_discovery(client)
                        discovery_done = True
                except Exception as e:
                    log("MQTT connection failed: " + str(e))
                    client = None
                    time.sleep(5)
                    continue

                # Check for reset command before publishing
                client.check_msg()

                # Snapshot and reset interval pulse count
                count = pulse_count
                pulse_count = 0
                last_publish = now
                prev_count = 0

                flow_rate = calculations.calculate_flow_rate(count, elapsed, PULSES_PER_LITER)
                flow_rate = min(flow_rate, MAX_FLOW_RATE)

                liters_this_interval = round(count / PULSES_PER_LITER, 4)
                keg_dispensed       += liters_this_interval
                total_volume         = round(total_pulses / PULSES_PER_LITER, 3)

                keg_remaining = calculations.calculate_keg_remaining(keg_dispensed, KEG_VOLUME_LITERS)
                keg_percent   = calculations.calculate_keg_percent(keg_remaining, KEG_VOLUME_LITERS)

                payload = calculations.build_mqtt_payload(
                    flow_rate, total_volume, keg_remaining, keg_percent
                )

                try:
                    client.publish(TOPIC_STATE, payload.encode())
                    log(f"Published → flow: {flow_rate} L/min | dispensed: {total_volume}L | "
                        f"remaining: {keg_remaining}L ({keg_percent}%)")
                except Exception as e:
                    log("MQTT publish error: " + str(e))

                # Stay connected for COMMAND_LISTEN_SECONDS to receive HA commands (reset, wake)
                for _ in range(COMMAND_LISTEN_SECONDS):
                    try:
                        client.check_msg()
                    except Exception:
                        pass
                    time.sleep(1)

            # Decrement stay_awake counter
            if stay_awake > 0:
                stay_awake -= 1
                save_state()
                time.sleep(1)
            elif flow_detected:
                # Flow detected — stay awake to keep publishing
                flow_detected = False
                save_state()
                time.sleep(1)
            else:
                # No flow, no wake — go to deepsleep
                save_state()
                # Disconnect MQTT and WiFi
                if client is not None:
                    try:
                        client.disconnect()
                    except Exception as e:
                        log("MQTT disconnect error: " + str(e))
                    client = None
                if wlan is not None and wlan.isconnected():
                    wlan.disconnect()
                    wlan.active(False)
                # Configure GPIO wake so device wakes when flow sensor detects pulses
                esp32.wake_on_ext0(pin=sensor_pin, level=esp32.WAKEUP_ALL_LOW)
                log(f"Entering deepsleep for {SLEEP_INTERVAL}ms... (GPIO wake armed)")
                time.sleep(2)  # Allow log to finish flushing
                deepsleep(SLEEP_INTERVAL)  # Reboots on wake (GPIO or timer)
                # Reset flow_detected on wake (globals reset on reboot)

        except Exception as e:
            log("Main loop error: " + str(e))
            time.sleep(5)

if __name__ == "__main__":
    main()
