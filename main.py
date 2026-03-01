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
import webrepl
import websocket_helper  # Required for WebREPL password
from machine import Pin, lightsleep, RTC
from umqtt.simple import MQTTClient
import ujson
try:
    import secrets
except ImportError:
    raise ImportError("secrets.py not found. Copy secrets.py.example to secrets.py and configure.")

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
TOPIC_RESET        = b"home/flow_sensor/reset"   # publish any message here to reset keg to full

# WebREPL
WEBREPL_PASSWORD = secrets.WEBREPL_PASSWORD

# Keg
KEG_VOLUME_LITERS  = 18.93  # 5 US gallons

# Sensor
FLOW_PIN          = 4       # GPIO pin connected to yellow wire
PULSES_PER_LITER  = 450     # pulses per liter (calibrate: 450 is common for these sensors)
PUBLISH_INTERVAL  = 30      # seconds between MQTT publishes (battery saver)
SLEEP_INTERVAL    = 5000    # ms to sleep between cycles (5 seconds)
DEBOUNCE_MS       = 50      # debounce time in milliseconds (increased to prevent false triggers)
MAX_FLOW_RATE     = 30      # maximum possible flow rate in L/min (sanity check)
MIN_PULSE_MS      = 2       # minimum time between valid pulses (physical limit of sensor)

# ─── Globals ──────────────────────────────────────────────────────────────────

rtc = RTC()  # For persisting data during light sleep
if not hasattr(rtc, 'pulse_count'):
    rtc.pulse_count = 0
    rtc.total_pulses = 0
    rtc.keg_dispensed = 0.0
    rtc.last_publish = 0

pulse_count     = rtc.pulse_count
total_pulses    = rtc.total_pulses
keg_dispensed   = rtc.keg_dispensed   # liters dispensed from current keg
last_publish    = rtc.last_publish
last_pulse_time = 0
prev_count      = 0     # previous pulse count to detect flow changes
flow_detected   = False # Flag to wake from sleep on flow

# ─── Interrupt handler ────────────────────────────────────────────────────────

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
    rtc.pulse_count = pulse_count
    rtc.total_pulses = total_pulses
    flow_detected = True  # Set flag to wake from sleep

# ─── WiFi ─────────────────────────────────────────────────────────────────────

def connect_wifi():
    global wlan
    if wlan is not None and wlan.isconnected():
        return wlan
        
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.config(pm=0)  # Disable power management to prevent modem sleep
    if not wlan.isconnected():
        print("Connecting to WiFi...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        for _ in range(20):
            if wlan.isconnected():
                break
            time.sleep(1)
    if wlan.isconnected():
        print("WiFi connected:", wlan.ifconfig()[0])
        return wlan
    else:
        print("WiFi connection failed, retrying...")
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
    client.publish(TOPIC_AVAILABILITY, b"online", retain=True)
    print("MQTT connected")
    return client

def mqtt_callback(topic, msg):
    global keg_dispensed
    if topic == TOPIC_RESET:
        keg_dispensed = 0.0
        rtc.keg_dispensed = 0.0  # Persist the reset
        print("Keg reset to full (18.93 L)")

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
        "name": "Water Flow Rate",
        "unique_id": "flow_sensor_rate",
        "state_topic": TOPIC_STATE.decode(),
        "availability_topic": TOPIC_AVAILABILITY.decode(),
        "value_template": "{{ value_json.flow_rate }}",
        "unit_of_measurement": "L/min",
        "device_class": "volume_flow_rate",
        "state_class": "measurement",
        "icon": "mdi:water-pump",
        "device": device
    }

    # Total volume sensor
    volume_config = {
        "name": "Water Total Volume",
        "unique_id": "flow_sensor_volume",
        "state_topic": TOPIC_STATE.decode(),
        "availability_topic": TOPIC_AVAILABILITY.decode(),
        "value_template": "{{ value_json.total_volume }}",
        "unit_of_measurement": "L",
        "device_class": "water",
        "state_class": "total_increasing",
        "icon": "mdi:water",
        "device": device
    }

    # Keg level sensor
    keg_config = {
        "name": "Keg Level",
        "unique_id": "flow_sensor_keg_level",
        "state_topic": TOPIC_STATE.decode(),
        "availability_topic": TOPIC_AVAILABILITY.decode(),
        "value_template": "{{ value_json.keg_percent }}",
        "unit_of_measurement": "%",
        "state_class": "measurement",
        "icon": "mdi:beer",
        "device": device
    }

    # Keg remaining (liters)
    keg_liters_config = {
        "name": "Keg Remaining",
        "unique_id": "flow_sensor_keg_remaining",
        "state_topic": TOPIC_STATE.decode(),
        "availability_topic": TOPIC_AVAILABILITY.decode(),
        "value_template": "{{ value_json.keg_remaining }}",
        "unit_of_measurement": "L",
        "device_class": "water",
        "state_class": "measurement",
        "icon": "mdi:beer-outline",
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
    print("Auto-discovery published to Home Assistant")

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    global pulse_count, last_publish, keg_dispensed, total_pulses, last_pulse_time, prev_count, wlan, client

    # Set up sensor pin with interrupt
    sensor_pin = Pin(FLOW_PIN, Pin.IN, Pin.PULL_UP)
    sensor_pin.irq(trigger=Pin.IRQ_RISING, handler=pulse_handler)

    # Initialize WiFi and WebREPL
    wlan = connect_wifi()
    if wlan is not None:
        try:
            # Configure and start WebREPL
            websocket_helper.password(WEBREPL_PASSWORD)
            webrepl.start(password=WEBREPL_PASSWORD)
            print(f"WebREPL started at ws://{wlan.ifconfig()[0]}:8266")
        except Exception as e:
            print("WebREPL error:", e)

    client = None
    discovery_done = False

    while True:
        try:
            now = time.time()
            elapsed = now - last_publish

            # Check if there's flow happening
            current_count = pulse_count
            has_flow = current_count > prev_count
            prev_count = current_count

            # Publish if interval reached OR if flow just started
            should_publish = elapsed >= PUBLISH_INTERVAL or (has_flow and elapsed >= 5)

            if should_publish:
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
                    print("MQTT connection failed:", e)
                    client = None
                    time.sleep(5)
                    continue

                # Check for reset command before publishing
                client.check_msg()

                # Snapshot and reset interval pulse count
                count = pulse_count
                pulse_count = 0
                rtc.pulse_count = 0
                last_publish = now
                rtc.last_publish = now
                prev_count = 0

                # Flow rate: (pulses / elapsed_seconds) * 60 / PULSES_PER_LITER = L/min
                # Sanity check the elapsed time to prevent division by very small numbers
                if elapsed < 0.1:  # Less than 100ms is too short for accurate measurement
                    flow_rate = 0
                else:
                    flow_rate = round((count / elapsed) * 60 / PULSES_PER_LITER, 3)
                    flow_rate = min(flow_rate, MAX_FLOW_RATE)  # Cap at physical maximum

                # Track how much has been dispensed from this keg
                liters_this_interval = round(count / PULSES_PER_LITER, 4)
                keg_dispensed       += liters_this_interval
                rtc.keg_dispensed    = keg_dispensed
                total_volume         = round(total_pulses / PULSES_PER_LITER, 3)

                keg_remaining = round(max(KEG_VOLUME_LITERS - keg_dispensed, 0), 3)
                keg_percent   = round((keg_remaining / KEG_VOLUME_LITERS) * 100, 1)

                payload = ujson.dumps({
                    "flow_rate":     flow_rate,
                    "total_volume":  total_volume,
                    "keg_remaining": keg_remaining,
                    "keg_percent":   keg_percent
                })

                try:
                    client.publish(TOPIC_STATE, payload.encode())
                    print(f"Published → flow: {flow_rate} L/min | keg: {keg_remaining}L ({keg_percent}%)")
                except Exception as e:
                    print("MQTT publish error:", e)

                # Disconnect MQTT but keep WiFi for WebREPL
                try:
                    client.publish(TOPIC_AVAILABILITY, b"offline", retain=True)
                    client.disconnect()
                except Exception as e:
                    print("MQTT disconnect error:", e)
                client = None

            # Use light sleep for power saving, wake on GPIO or timer
            if flow_detected:
                flow_detected = False  # Reset flag
                time.sleep(0.1)  # Brief sleep to allow more pulses
            else:
                lightsleep(SLEEP_INTERVAL)  # Wake on either GPIO interrupt or timer
            
        except Exception as e:
            print("Main loop error:", e)
            time.sleep(5)

main()
