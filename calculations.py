import ujson


# ─── Flow Rate ────────────────────────────────────────────────────────────────

# Sensor formula from datasheet: F = 98 * Q
# Where F = frequency (Hz), Q = flow rate (L/min)
# Therefore: Q = F / 98 = (pulse_count / elapsed) / 98
PULSES_PER_LITER_PER_MINUTE = 98


def calculate_flow_rate(pulse_count, elapsed, pulses_per_liter_per_minute=PULSES_PER_LITER_PER_MINUTE):
    """
    Calculate flow rate in L/min from pulse count and elapsed seconds.
    Uses sensor formula: F = 98 * Q => Q = (pulses/elapsed) / 98
    """
    if elapsed < 0.1:
        return 0
    frequency = pulse_count / elapsed
    return round(frequency / pulses_per_liter_per_minute, 3)


# ─── Keg ──────────────────────────────────────────────────────────────────────

def calculate_keg_remaining(keg_dispensed, keg_volume):
    """Return liters remaining in the keg, clamped to 0."""
    return round(max(keg_volume - keg_dispensed, 0), 3)


def calculate_keg_percent(keg_remaining, keg_volume):
    """Return keg fullness as a percentage (0-100)."""
    return round((keg_remaining / keg_volume) * 100, 1)


# ─── MQTT Payload ─────────────────────────────────────────────────────────────

def build_mqtt_payload(flow_rate, total_volume, keg_remaining, keg_percent):
    """Build a JSON MQTT payload string."""
    return ujson.dumps({
        "flow_rate":     flow_rate,
        "total_volume":  total_volume,
        "keg_remaining": keg_remaining,
        "keg_percent":   keg_percent,
    })


# ─── Timezone ─────────────────────────────────────────────────────────────────

def get_timezone_offset(month, base_offset):
    """Return timezone offset in seconds, adding 1 hour during DST (April-October)."""
    if 4 <= month <= 10:
        return base_offset + 3600
    return base_offset
