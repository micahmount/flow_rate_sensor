import time
import ujson


# ─── Flow Rate ────────────────────────────────────────────────────────────────

PULSES_PER_LITER = 684  # Empirically calibrated (2026-07-01, 345ml test pour)


def calculate_flow_rate(pulse_count, elapsed, pulses_per_liter=PULSES_PER_LITER):
    """
    Calculate flow rate in L/min from pulse count and elapsed seconds.
    """
    if elapsed < 0.1:
        return 0
    frequency = pulse_count / elapsed
    return round(frequency / pulses_per_liter, 3)


# ─── Keg ──────────────────────────────────────────────────────────────────────

def calculate_keg_remaining(keg_dispensed, keg_volume):
    """Return liters remaining in the keg, clamped to 0."""
    return round(max(keg_volume - keg_dispensed, 0), 3)


def calculate_keg_percent(keg_remaining, keg_volume):
    """Return keg fullness as a percentage (0-100)."""
    return round((keg_remaining / keg_volume) * 100, 1)


# ─── Timestamp ────────────────────────────────────────────────────────────────

def format_timestamp(epoch_seconds, base_offset):
    """Format an epoch timestamp as 'YYYY-MM-DD HH:MM:SS' with DST-aware offset."""
    t = time.localtime(epoch_seconds)
    tz = get_timezone_offset(t[1], base_offset)
    t = time.localtime(epoch_seconds + tz)
    return f"{t[0]}-{t[1]:02d}-{t[2]:02d} {t[3]:02d}:{t[4]:02d}:{t[5]:02d}"


# ─── MQTT Payload ─────────────────────────────────────────────────────────────

def build_mqtt_payload(flow_rate, total_volume, keg_remaining, keg_percent, **extra):
    """Build a JSON MQTT payload string with optional extra fields."""
    payload = {
        "flow_rate":     flow_rate,
        "total_volume":  total_volume,
        "keg_remaining": keg_remaining,
        "keg_percent":   keg_percent,
    }
    payload.update(extra)
    return ujson.dumps(payload)


# ─── Timezone ─────────────────────────────────────────────────────────────────

def get_timezone_offset(month, base_offset):
    """Return timezone offset in seconds, adding 1 hour during DST (April-October)."""
    if 4 <= month <= 10:
        return base_offset + 3600
    return base_offset
