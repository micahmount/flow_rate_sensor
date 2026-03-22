import ujson


# ─── Schema ───────────────────────────────────────────────────────────────────

STATE_FILE = "/flow_state.json"

DEFAULT_STATE = {
    "keg_dispensed": 0.0,
    "total_pulses":  0,
    "stay_awake":    0,
    "last_publish":  0,
}


# ─── Persistence ──────────────────────────────────────────────────────────────

def load():
    """
    Load state from flash. Returns DEFAULT_STATE on any error.
    last_publish is always reset to 0 — device should always publish on wake.
    """
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            data = ujson.load(f)
            return {
                "keg_dispensed": data.get("keg_dispensed", 0.0),
                "total_pulses":  data.get("total_pulses", 0),
                "stay_awake":    data.get("stay_awake", 0),
                "last_publish":  0,
            }
    except Exception:
        return dict(DEFAULT_STATE)


def save(state):
    """Persist state to flash. Silently ignores write errors."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            ujson.dump({
                "keg_dispensed": state["keg_dispensed"],
                "total_pulses":  state["total_pulses"],
                "stay_awake":    state["stay_awake"],
                "last_publish":  state["last_publish"],
            }, f)
    except Exception:
        pass


# ─── Pure Transitions ─────────────────────────────────────────────────────────

def _copy(state):
    return {
        "keg_dispensed": state["keg_dispensed"],
        "total_pulses":  state["total_pulses"],
        "stay_awake":    state["stay_awake"],
        "last_publish":  state["last_publish"],
    }


def on_reset(state):
    """Reset keg_dispensed to 0. Preserves total_pulses and stay_awake."""
    s = _copy(state)
    s["keg_dispensed"] = 0.0
    return s


def on_wake_command(state, timeout):
    """Set stay_awake to timeout seconds."""
    s = _copy(state)
    s["stay_awake"] = timeout
    return s


def on_pulse(state, pulse_count, pulses_per_liter):
    """
    Accumulate pulse_count into total_pulses and keg_dispensed.
    Returns new state — caller is responsible for resetting pulse_count global.
    """
    liters = round(pulse_count / pulses_per_liter, 4)
    s = _copy(state)
    s["total_pulses"]  = state["total_pulses"] + pulse_count
    s["keg_dispensed"] = round(state["keg_dispensed"] + liters, 4)
    return s


def on_publish(state, now):
    """Record the time of the last successful publish."""
    s = _copy(state)
    s["last_publish"] = now
    return s


def on_sleep_tick(state):
    """Decrement stay_awake by 1, clamped at 0."""
    s = _copy(state)
    s["stay_awake"] = max(0, state["stay_awake"] - 1)
    return s


# ─── Predicates ───────────────────────────────────────────────────────────────

def should_publish(state, now, interval):
    """True if publish interval has elapsed or device just woke (last_publish=0)."""
    return state["last_publish"] == 0 or (now - state["last_publish"]) >= interval


def should_sleep(state):
    """True if no wake command is active."""
    return state["stay_awake"] == 0
