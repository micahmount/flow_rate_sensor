import time
import ujson
from umqtt.simple import MQTTClient


# ─── Connect / Disconnect ─────────────────────────────────────────────────────

def connect(config, callback):
    """
    Connect to MQTT broker. Sets callback, LWT, subscribes to command topics,
    publishes availability=online. Returns connected client.
    callback must be set before subscribe() so messages are not missed.
    """
    client = MQTTClient(
        config["client_id"],
        config["broker"],
        port=config["port"],
        user=config["user"],
        password=config["password"],
        keepalive=60,
    )
    client.set_callback(callback)
    client.set_last_will(config["topic_availability"], b"offline", retain=True)
    client.connect()
    client.subscribe(config["topic_reset"])
    client.subscribe(config["topic_wake"])
    client.publish(config["topic_availability"], b"online", retain=True)
    return client


def disconnect(client):
    """Disconnect from MQTT broker. Silently ignores errors."""
    try:
        client.disconnect()
    except Exception:
        pass


# ─── Publish ──────────────────────────────────────────────────────────────────

def publish_state(client, payload, config):
    """Publish state JSON payload to state topic."""
    client.publish(config["topic_state"], payload.encode())


def listen(client, seconds):
    """
    Poll for incoming MQTT messages for `seconds` seconds.
    Callback must already be set via connect().
    """
    for _ in range(seconds):
        try:
            client.check_msg()
        except Exception:
            pass
        time.sleep(1)


# ─── Discovery ────────────────────────────────────────────────────────────────

def publish_discovery(client, config):
    """
    Publish Home Assistant MQTT auto-discovery messages for all entities.
    Should be called once per boot.
    """
    device = {
        "identifiers":    [config["client_id"]],
        "name":           "Water Flow Sensor",
        "model":          "Gredia 1/4\" Hall Effect",
        "manufacturer":   "Gredia",
    }

    entities = [
        (
            b"homeassistant/sensor/flow_sensor/flow_rate/config",
            {
                "name":                 "Flow Rate",
                "unique_id":            "water_flow_rate",
                "state_topic":          config["topic_state"].decode(),
                "availability_topic":   config["topic_availability"].decode(),
                "value_template":       "{{ value_json.flow_rate }}",
                "unit_of_measurement":  "L/min",
                "device_class":         "volume_flow_rate",
                "state_class":          "measurement",
                "icon":                 "mdi:water-pump",
                "force_update":         True,
                "device":               device,
            },
        ),
        (
            b"homeassistant/sensor/flow_sensor/total_volume/config",
            {
                "name":                 "Dispensed",
                "unique_id":            "water_total_volume",
                "state_topic":          config["topic_state"].decode(),
                "availability_topic":   config["topic_availability"].decode(),
                "value_template":       "{{ value_json.total_volume }}",
                "unit_of_measurement":  "L",
                "device_class":         "water",
                "state_class":          "total_increasing",
                "icon":                 "mdi:water",
                "force_update":         True,
                "device":               device,
            },
        ),
        (
            b"homeassistant/sensor/flow_sensor/keg_level/config",
            {
                "name":                 "Keg Level",
                "unique_id":            "keg_level",
                "state_topic":          config["topic_state"].decode(),
                "availability_topic":   config["topic_availability"].decode(),
                "value_template":       "{{ value_json.keg_percent }}",
                "unit_of_measurement":  "%",
                "state_class":          "measurement",
                "icon":                 "mdi:beer",
                "force_update":         True,
                "device":               device,
            },
        ),
        (
            b"homeassistant/sensor/flow_sensor/keg_remaining/config",
            {
                "name":                 "Remaining",
                "unique_id":            "keg_remaining",
                "state_topic":          config["topic_state"].decode(),
                "availability_topic":   config["topic_availability"].decode(),
                "value_template":       "{{ value_json.keg_remaining }}",
                "unit_of_measurement":  "L",
                "device_class":         "water",
                "state_class":          "measurement",
                "icon":                 "mdi:beer-outline",
                "force_update":         True,
                "device":               device,
            },
        ),
        (
            b"homeassistant/button/flow_sensor/reset/config",
            {
                "name":             "Reset Keg",
                "unique_id":        "flow_sensor_reset",
                "command_topic":    config["topic_reset"].decode(),
                "payload_press":    "RESET",
                "retain":           True,
                "device":           device,
            },
        ),
        (
            b"homeassistant/button/flow_sensor/wake/config",
            {
                "name":             "Stay Awake",
                "unique_id":        "flow_sensor_wake",
                "command_topic":    config["topic_wake"].decode(),
                "payload_press":    "WAKE",
                "retain":           True,
                "device":           device,
            },
        ),
    ]

    for topic, cfg in entities:
        client.publish(topic, ujson.dumps(cfg).encode(), retain=True)
