# Gredia 1/4" Hall Effect Flow Sensor — ESP32 MicroPython
# Publishes flow rate (L/min) and total volume (L) to Home Assistant via MQTT
#
# Wiring:
#   Red    → 3.3V or 5V
#   Black  → GND
#   Yellow → GPIO 4

import network
import time
from machine import Pin
from umqtt.simple import MQTTClient
import ujson
try:
    import secrets
except ImportError:
    raise ImportError("secrets.py not found. Copy secrets.py.example to secrets.py and configure.")

# ─── Configuration ────────────────────────────────────────────────────────────

WIFI_SSID      = secrets.WIFI_SSID
WIFI_PASSWORD  = secrets.WIFI_PASSWORD

MQTT_BROKER    = secrets.MQTT_BROKER
MQTT_PORT      = secrets.MQTT_PORT
MQTT_USER      = secrets.MQTT_USER
MQTT_PASSWORD  = secrets.MQTT_PASSWORD
MQTT_CLIENT_ID = secrets.MQTT_CLIENT_ID

# MQTT topics
TOPIC_STATE        = b"home/flow_sensor/state"
TOPIC_AVAILABILITY = b"home/flow_sensor/availability"
TOPIC_RESET        = b"home/flow_sensor/reset"

# Keg
KEG_VOLUME_LITERS = 18.93   # 5 US gallons

# Sensor
FLOW_PIN         = 4        # GPIO pin connected to yellow wire
PULSES_PER_LITER = 23 * 60  # 23 pulses/sec per L/min → 1380 pulses per liter
PUBLISH_INTERVAL = 10       # seconds between MQTT publishes
KEEPALIVE_PING   = 30       # seconds between MQTT pings to keep connection alive

# ─── Globals ──────────────────────────────────────────────────────────────────

pulse_count   = 0    # pulses in the current publish interval (reset each interval)
total_pulses  = 0    # all-time pulse count (never reset except by keg reset)
keg_baseline  = 0    # total_pulses value at the last keg reset
last_publish  = 0
last_ping     = 0

# ─── Interrupt handler ────────────────────────────────────────────────────────

def pulse_handler(pin):
    global pulse_count, total_pulses
    pulse_count  += 1
    total_pulses += 1

# ─── WiFi ─────────────────────────────────────────────────────────────────────

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to WiFi...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        for _ in range(20):
            if wlan.isconnected():
                break
            time.sleep(1)
    if wlan.isconnected():
        print("WiFi connected:", wlan.ifconfig()[0])
    else:
        raise RuntimeError("WiFi connection failed")

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
    # FIX: reset keg_baseline to current total_pulses so keg reads 100% from here.
    # Previously this reset keg_dispensed to 0.0, but keg_dispensed was also being
    # accumulated separately from pulse_count — causing double counting.
    # Now all volume math derives from a single source: total_pulses.
    global keg_baseline
    if topic == TOPIC_RESET:
        keg_baseline = total_pulses
        print("Keg reset to full (18.93 L)")

def publish_discovery(client):
    """Publish Home Assistant MQTT auto-discovery messages on startup."""
    device = {
        "identifiers": ["esp32_flow_sensor"],
        "name": "Water Flow Sensor",
        "model": "Gredia 1/4\" Hall Effect",
        "manufacturer": "Gredia"
    }

    configs = [
        (b"homeassistant/sensor/flow_sensor/flow_rate/config", {
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
        }),
        (b"homeassistant/sensor/flow_sensor/total_volume/config", {
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
        }),
        (b"homeassistant/sensor/flow_sensor/keg_level/config", {
            "name": "Keg Level",
            "unique_id": "flow_sensor_keg_level",
            "state_topic": TOPIC_STATE.decode(),
            "availability_topic": TOPIC_AVAILABILITY.decode(),
            "value_template": "{{ value_json.keg_percent }}",
            "unit_of_measurement": "%",
            "state_class": "measurement",
            "icon": "mdi:beer",
            "device": device
        }),
        (b"homeassistant/sensor/flow_sensor/keg_remaining/config", {
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
        }),
    ]

    for topic, config in configs:
        client.publish(topic, ujson.dumps(config).encode(), retain=True)

    print("Auto-discovery published to Home Assistant")

# ─── Reconnect helper ─────────────────────────────────────────────────────────

def safe_reconnect():
    """Reconnect WiFi if needed, then reconnect MQTT. Returns new client."""
    wlan = network.WLAN(network.STA_IF)
    if not wlan.isconnected():
        print("WiFi dropped, reconnecting...")
        connect_wifi()
    print("Reconnecting MQTT...")
    return connect_mqtt()

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    global pulse_count, last_publish, last_ping

    # Set up sensor pin with interrupt
    sensor_pin = Pin(FLOW_PIN, Pin.IN, Pin.PULL_UP)
    sensor_pin.irq(trigger=Pin.IRQ_RISING, handler=pulse_handler)

    connect_wifi()
    client = connect_mqtt()
    publish_discovery(client)

    last_publish = time.time()
    last_ping    = time.time()

    while True:
        now = time.time()

        # ── Keepalive ping ────────────────────────────────────────────────────
        # FIX: Without this, the broker closes the connection after the keepalive
        # timeout (~60s of silence). The resulting exception was previously
        # swallowed silently, leaving a dead client that caused a crash on the
        # next publish — which rebooted the ESP32.
        if now - last_ping >= KEEPALIVE_PING:
            try:
                client.ping()
                last_ping = now
            except Exception as e:
                print("Ping failed, reconnecting...", e)
                try:
                    client = safe_reconnect()
                    last_ping = now
                except Exception as e2:
                    print("Reconnect failed:", e2)

        # ── Check for incoming messages (e.g. keg reset) ──────────────────────
        # FIX: Previously bare `except: pass` silently swallowed connection
        # errors here, leaving client in a broken state.
        try:
            client.check_msg()
        except Exception as e:
            print("check_msg error, reconnecting...", e)
            try:
                client = safe_reconnect()
            except Exception as e2:
                print("Reconnect failed:", e2)

        # ── Publish on interval ───────────────────────────────────────────────
        elapsed = now - last_publish
        if elapsed >= PUBLISH_INTERVAL:
            # Snapshot interval pulse count and reset it
            count        = pulse_count
            pulse_count  = 0
            last_publish = now

            # Flow rate in L/min
            flow_rate = round((count / elapsed) / 23, 3)

            # FIX: All volume math now derives solely from total_pulses and
            # keg_baseline. Previously keg_dispensed was accumulated separately
            # from pulse_count AND total_pulses was also incremented in the ISR
            # for the same pulses — counting every pour twice.
            total_volume  = round(total_pulses / PULSES_PER_LITER, 3)
            keg_dispensed = round((total_pulses - keg_baseline) / PULSES_PER_LITER, 3)
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
                print("Publish error, reconnecting...", e)
                try:
                    client = safe_reconnect()
                except Exception as e2:
                    print("Reconnect failed:", e2)

        time.sleep(0.1)

main()
