import ujson


STATE_FILE = "/flow_state.json"


def calculate_flow_rate(pulse_count, elapsed, pulses_per_liter=450):
    if elapsed < 0.1:
        return 0
    return round((pulse_count / elapsed) * 60 / pulses_per_liter, 3)


def calculate_keg_remaining(keg_dispensed, keg_volume):
    return round(max(keg_volume - keg_dispensed, 0), 3)


def calculate_keg_percent(keg_remaining, keg_volume):
    return round((keg_remaining / keg_volume) * 100, 1)


def build_mqtt_payload(flow_rate, total_volume, keg_remaining, keg_percent):
    return ujson.dumps({
        "flow_rate":     flow_rate,
        "total_volume":  total_volume,
        "keg_remaining": keg_remaining,
        "keg_percent":   keg_percent
    })


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            state = ujson.load(f)
            return (
                state.get("keg_dispensed", 0.0),
                state.get("total_pulses", 0),
                state.get("stay_awake", 0)
            )
    except Exception:
        return (0.0, 0, 0)


def save_state(keg_dispensed, total_pulses, stay_awake):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            ujson.dump({
                "keg_dispensed": keg_dispensed,
                "total_pulses":  total_pulses,
                "stay_awake":     stay_awake
            }, f)
    except Exception:
        pass


def get_timezone_offset(month, base_offset):
    if 4 <= month <= 10:
        return base_offset + 3600
    return base_offset


def reset_keg(keg_dispensed, total_pulses, stay_awake):
    save_state(0.0, total_pulses, stay_awake)
    return 0.0
