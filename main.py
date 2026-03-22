# Gredia 1/4" Hall Effect Flow Sensor — ESP32 MicroPython
# Publishes flow rate and keg level to Home Assistant via MQTT.
#
# Wiring:
#   Red    → 3.3V (or 5V)
#   Black  → GND
#   Yellow → GPIO 4

import time
import network
import ntptime
import webrepl
import esp32
from machine import Pin, deepsleep
import calculations
import state as state_module
import mqtt as mqtt_module
try:
    import secrets
except ImportError as exc:
    raise ImportError("Copy secrets.py.example to secrets.py and configure.") from exc

# ─── Configuration ────────────────────────────────────────────────────────────

FLOW_PIN              = 4
PULSES_PER_LITER      = 98        # F = 98 * Q per datasheet (pulses/liter/minute)
KEG_VOLUME_LITERS     = 18.93     # 5 US gallon corny keg
PUBLISH_INTERVAL      = 30        # seconds between publishes
SLEEP_INTERVAL        = 270000    # ms (4.5 minutes)
WAKE_TIMEOUT_SECONDS  = 300       # seconds to stay awake after wake command
COMMAND_LISTEN_SECONDS = 5        # seconds to listen for HA commands after publish
TIMEZONE_BASE         = -8 * 3600 # PST (UTC-8)
DEBOUNCE_MS           = 50
MIN_PULSE_MS          = 2
MAX_FLOW_RATE         = 30        # L/min sanity cap

MQTT_CONFIG = {
    "client_id":          secrets.MQTT_CLIENT_ID,
    "broker":             secrets.MQTT_BROKER,
    "port":               secrets.MQTT_PORT,
    "user":               secrets.MQTT_USER,
    "password":           secrets.MQTT_PASSWORD,
    "topic_state":        b"home/flow_sensor/state",
    "topic_availability": b"home/flow_sensor/availability",
    "topic_reset":        b"home/flow_sensor/reset",
    "topic_wake":         b"home/flow_sensor/wake",
}

# ─── ISR Global ───────────────────────────────────────────────────────────────

# pulse_count is written by the ISR — kept as a plain global for safe ISR access.
# It is accumulated into state on every publish cycle then reset to 0.
pulse_count     = 0
last_pulse_time = 0

# ─── Interrupt Handler ────────────────────────────────────────────────────────

def pulse_handler(pin):
    global pulse_count, last_pulse_time
    now = time.ticks_ms()
    pulse_diff = time.ticks_diff(now, last_pulse_time)

    if pulse_diff < MIN_PULSE_MS:
        return
    if pulse_diff < DEBOUNCE_MS:
        return

    # Reject physically impossible flow rates
    inst_flow = (1 / (pulse_diff / 1000)) * 60 / PULSES_PER_LITER
    if inst_flow > MAX_FLOW_RATE:
        return

    last_pulse_time = now
    pulse_count += 1

# ─── Logging ──────────────────────────────────────────────────────────────────

def log(msg):
    t = time.localtime()
    tz_offset = calculations.get_timezone_offset(t[1], TIMEZONE_BASE)
    t = time.localtime(time.time() + tz_offset)
    ts = f"{t[0]}-{t[1]:02d}-{t[2]:02d} {t[3]:02d}:{t[4]:02d}:{t[5]:02d}"
    print(f"[{ts}] {msg}")

# ─── WiFi ─────────────────────────────────────────────────────────────────────

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.config(pm=0)
    if not wlan.isconnected():
        log("Connecting to WiFi...")
        wlan.connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
        for _ in range(20):
            if wlan.isconnected():
                break
            time.sleep(1)
    if wlan.isconnected():
        log("WiFi connected: " + wlan.ifconfig()[0])
        try:
            ntptime.settime()
            log("NTP synced")
        except Exception as e:
            log("NTP failed: " + str(e))
        return wlan
    log("WiFi failed")
    return None


def disconnect_wifi(wlan):
    if wlan is not None:
        try:
            wlan.disconnect()
            wlan.active(False)
        except Exception:
            pass

# ─── Deepsleep ────────────────────────────────────────────────────────────────

def enter_deepsleep(sensor_pin):
    esp32.wake_on_ext0(pin=sensor_pin, level=esp32.WAKEUP_ALL_LOW)
    log(f"Entering deepsleep for {SLEEP_INTERVAL}ms...")
    time.sleep_ms(100)
    deepsleep(SLEEP_INTERVAL)

# ─── MQTT Callback ────────────────────────────────────────────────────────────

def make_callback(get_state, set_state):
    """
    Returns an MQTT callback that closes over state accessors.
    get_state() returns current state dict.
    set_state(s) replaces state with new dict and persists it.
    """
    def callback(topic, msg):
        s = get_state()
        if topic == MQTT_CONFIG["topic_reset"]:
            s = state_module.on_reset(s)
            log("Keg reset")
        elif topic == MQTT_CONFIG["topic_wake"]:
            s = state_module.on_wake_command(s, WAKE_TIMEOUT_SECONDS)
            log(f"Wake command — staying awake for {WAKE_TIMEOUT_SECONDS}s")
        set_state(s)
    return callback

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    global pulse_count

    # Hardware init — must happen before any path that calls enter_deepsleep
    sensor_pin = Pin(FLOW_PIN, Pin.IN, Pin.PULL_UP)
    sensor_pin.irq(trigger=Pin.IRQ_RISING, handler=pulse_handler)

    # Load persisted state
    state = state_module.load()
    log(f"Boot — dispensed={state['keg_dispensed']}L, "
        f"pulses={state['total_pulses']}, stay_awake={state['stay_awake']}")

    # Connect WiFi and start WebREPL
    wlan = connect_wifi()
    if wlan is not None:
        try:
            webrepl.start()
            log(f"WebREPL at ws://{wlan.ifconfig()[0]}:8266")
        except Exception as e:
            log("WebREPL error: " + str(e))

    discovery_done = False

    # State accessors for MQTT callback closure
    # Using a single-element list so the closure can rebind state
    state_ref = [state]

    def get_state():
        return state_ref[0]

    def set_state(s):
        state_ref[0] = s
        state_module.save(s)

    while True:
        state = state_ref[0]
        now = time.time()

        if state_module.should_publish(state, now, PUBLISH_INTERVAL):
            # Accumulate ISR pulses into state, reset global
            count = pulse_count
            pulse_count = 0
            state = state_module.on_pulse(state, count, PULSES_PER_LITER)
            state_ref[0] = state

            # Compute derived values
            elapsed = now - state["last_publish"] if state["last_publish"] else PUBLISH_INTERVAL
            flow_rate = min(
                calculations.calculate_flow_rate(count, elapsed, PULSES_PER_LITER),
                MAX_FLOW_RATE
            )
            total_volume  = round(state["total_pulses"] / PULSES_PER_LITER, 3)
            keg_remaining = calculations.calculate_keg_remaining(
                state["keg_dispensed"], KEG_VOLUME_LITERS
            )
            keg_percent = calculations.calculate_keg_percent(keg_remaining, KEG_VOLUME_LITERS)
            payload = calculations.build_mqtt_payload(
                flow_rate, total_volume, keg_remaining, keg_percent
            )

            # Connect, publish, listen, disconnect
            try:
                client = mqtt_module.connect(MQTT_CONFIG)
                if not discovery_done:
                    mqtt_module.publish_discovery(client, MQTT_CONFIG)
                    discovery_done = True
                mqtt_module.publish_state(client, payload, MQTT_CONFIG)
                log(f"Published — flow: {flow_rate} L/min | "
                    f"remaining: {keg_remaining}L ({keg_percent}%)")
                mqtt_module.listen(client, make_callback(get_state, set_state), COMMAND_LISTEN_SECONDS)
                mqtt_module.disconnect(client)
            except Exception as e:
                log("MQTT error: " + str(e))

            # Record publish time and persist
            state = state_module.on_publish(state_ref[0], now)
            set_state(state)

        # Sleep or tick
        if state_module.should_sleep(state_ref[0]):
            state_module.save(state_ref[0])
            disconnect_wifi(wlan)
            enter_deepsleep(sensor_pin)
        else:
            state = state_module.on_sleep_tick(state_ref[0])
            set_state(state)
            time.sleep(1)

if __name__ == "__main__":
    main()
