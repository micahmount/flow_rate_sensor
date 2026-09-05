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
from calculations import PULSES_PER_LITER
import state as state_module
import mqtt as mqtt_module
try:
    import secrets
except ImportError as exc:
    raise ImportError("Copy secrets.py.example to secrets.py and configure.") from exc

# ─── Configuration ────────────────────────────────────────────────────────────

VERSION                = "1.3.0"  # Keep in sync with git tag v<VERSION> (see README)
FLOW_PIN               = 4
KEG_VOLUME_LITERS      = 18.93     # 5 US gallon corny keg
PUBLISH_INTERVAL       = 30        # seconds between publishes
SLEEP_INTERVAL         = 270000    # ms (4.5 minutes)
COMMAND_LISTEN_SECONDS = 5         # seconds to listen for HA commands after publish
MINIMUM_AWAKE_SECONDS  = 30        # minimum time device stays awake per cycle
TIMEZONE_BASE          = -8 * 3600 # PST (UTC-8)
MIN_PULSE_INTERVAL_MS  = 1         # reject pulses closer than this
MAX_FLOW_RATE          = 30        # L/min sanity cap

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
    "topic_wake_state":   b"home/flow_sensor/wake_state",
}

# ─── ISR Globals ──────────────────────────────────────────────────────────────

# pulse_count is written by the ISR — kept as a plain global for safe ISR access.
# It is accumulated into state on every publish cycle then reset to 0.
pulse_count     = 0
last_pulse_time = 0

# ─── Interrupt Handlers ──────────────────────────────────────────────────────

def pulse_handler(pin):
    global pulse_count, last_pulse_time
    now = time.ticks_ms()
    pulse_diff = time.ticks_diff(now, last_pulse_time)
    if pulse_diff < MIN_PULSE_INTERVAL_MS:
        return
    # Reject physically impossible flow rates. With PULSES_PER_LITER=5880 this
    # works out to ~0.3ms, below the 1ms debounce, so it only guards extreme flow.
    if pulse_diff < 60000 // (MAX_FLOW_RATE * PULSES_PER_LITER):
        return
    last_pulse_time = now
    pulse_count += 1


# ─── Logging ──────────────────────────────────────────────────────────────────

def log(msg):
    ts = calculations.format_timestamp(time.time(), TIMEZONE_BASE)
    print(f"[{ts}] {msg}")


def human_duration(ms):
    """Convert milliseconds to human-readable string like '4m 30s'."""
    total_seconds = ms // 1000
    if total_seconds >= 3600:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    if total_seconds >= 60:
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}m {seconds}s"
    return f"{total_seconds}s"


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
    log(f"Entering deepsleep for {human_duration(SLEEP_INTERVAL)}...")
    time.sleep_ms(100)
    deepsleep(SLEEP_INTERVAL)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def boot_init():
    """Initialize hardware, WiFi, and WebREPL. Returns (sensor_pin, wlan, boot_time)."""
    sensor_pin = Pin(FLOW_PIN, Pin.IN, Pin.PULL_UP)
    sensor_pin.irq(trigger=Pin.IRQ_RISING, handler=pulse_handler)
    boot_time = time.time()
    wlan = connect_wifi()
    if wlan is not None:
        try:
            webrepl.start()
            log(f"WebREPL at ws://{wlan.ifconfig()[0]}:8266")
        except Exception:
            pass
    return sensor_pin, wlan, boot_time


def wait_minimum_window(boot_time):
    """Sleep for any remaining time to enforce MINIMUM_AWAKE_SECONDS per cycle."""
    elapsed = time.time() - boot_time
    if elapsed < MINIMUM_AWAKE_SECONDS:
        remaining = MINIMUM_AWAKE_SECONDS - elapsed
        log(f"Waiting {remaining:.0f}s minimum awake window...")
        time.sleep(remaining)

# ─── Publish Cycle ────────────────────────────────────────────────────────────

def publish_cycle(state_ref, callback, discovery_done, now):
    """
    Accumulate pulses, compute payload, publish to MQTT, listen for commands,
    clear retained wake message. Returns updated_discovery_done.
    state_ref is a one-element list shared with the callback so mutations
    during listen() are visible after the cycle.
    """
    global pulse_count

    # Snapshot + reset pulse_count, accumulate into state
    count = pulse_count
    pulse_count = 0
    state_ref[0] = state_module.on_pulse(state_ref[0], count, PULSES_PER_LITER)
    state = state_ref[0]

    # Compute derived values and payload
    elapsed = now - state["last_publish"] if state["last_publish"] else PUBLISH_INTERVAL
    flow_rate = min(
        calculations.calculate_flow_rate(count, elapsed, PULSES_PER_LITER),
        MAX_FLOW_RATE
    )
    total_volume = round(state["total_pulses"] / PULSES_PER_LITER, 3)
    keg_remaining = calculations.calculate_keg_remaining(state["keg_dispensed"], KEG_VOLUME_LITERS)
    keg_percent = calculations.calculate_keg_percent(keg_remaining, KEG_VOLUME_LITERS)
    last_updated = calculations.format_timestamp(now, TIMEZONE_BASE)
    payload = calculations.build_mqtt_payload(
        flow_rate, total_volume, keg_remaining, keg_percent, last_updated, version=VERSION
    )

    # Connect MQTT — fail fast, skip publish if connect fails
    try:
        client = mqtt_module.connect(MQTT_CONFIG, callback)
    except Exception as e:
        log(f"MQTT connect failed: {e}")
        return discovery_done

    # Publish + listen + clear retained — separate scope from connect
    try:
        if not discovery_done:
            mqtt_module.publish_discovery(client, MQTT_CONFIG)
            discovery_done = True
        mqtt_module.publish_state(client, payload, MQTT_CONFIG)
        wake_state = "ON" if state["stay_awake_enabled"] else "OFF"
        client.publish(MQTT_CONFIG["topic_wake_state"], wake_state.encode(), retain=True)
        log(f"Published — flow: {flow_rate} L/min | "
            f"remaining: {keg_remaining}L ({keg_percent}%)")
        mqtt_module.listen(client, COMMAND_LISTEN_SECONDS)
        client.publish(MQTT_CONFIG["topic_wake"], b"", retain=True)
        client.publish(MQTT_CONFIG["topic_reset"], b"", retain=True)
    except Exception as e:
        log(f"MQTT error: {e}")

    mqtt_module.disconnect(client)

    state_ref[0] = state_module.on_publish(state_ref[0], now)
    state_module.save(state_ref[0])
    return discovery_done

# ─── Sleep/Tick ───────────────────────────────────────────────────────────────

def sleep_or_tick(state, wlan, boot_time, sensor_pin):
    """Either enter deepsleep or sleep 1s while toggle is active."""
    if state_module.should_sleep(state):
        wait_minimum_window(boot_time)
        disconnect_wifi(wlan)
        enter_deepsleep(sensor_pin)
    else:
        time.sleep(1)

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    global pulse_count

    sensor_pin, wlan, boot_time = boot_init()
    state = state_module.load()

    log(f"Flow Sensor v{VERSION}")
    if state["stay_awake_enabled"]:
        log("Boot — wake toggle ON")
    else:
        log("Boot — deepsleep, will sleep after publish")
    log(f"  dispensed={state['keg_dispensed']}L, pulses={state['total_pulses']}")

    discovery_done = False
    state_ref = [state]

    def callback(topic, msg):
        if topic == MQTT_CONFIG["topic_reset"]:
            state_ref[0] = state_module.on_reset(state_ref[0])
            state_module.save(state_ref[0])
            log("Keg reset")
        elif topic == MQTT_CONFIG["topic_wake"]:
            if msg == b"ON":
                state_ref[0]["stay_awake_enabled"] = True
                state_module.save(state_ref[0])
                log("Wake mode ON (toggled)")
            elif msg == b"OFF":
                state_ref[0]["stay_awake_enabled"] = False
                state_module.save(state_ref[0])
                log("Wake mode OFF (toggled)")

    while True:
        now = time.time()
        if state_module.should_publish(state_ref[0], now, PUBLISH_INTERVAL):
            discovery_done = publish_cycle(state_ref, callback, discovery_done, now)
        sleep_or_tick(state_ref[0], wlan, boot_time, sensor_pin)

if __name__ == "__main__":
    main()
