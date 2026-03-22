import ujson
import calculations
import state as state_module


# ─── Helpers ──────────────────────────────────────────────────────────────────

def fresh_state():
    return {
        "keg_dispensed": 0.0,
        "total_pulses":  0,
        "stay_awake":    0,
        "last_publish":  0,
    }

def assert_eq(label, actual, expected):
    assert actual == expected, f"FAIL [{label}]: expected {expected}, got {actual}"
    print(f"PASS: {label}")


# ─── calculations.py ──────────────────────────────────────────────────────────

print("\n=== Flow Rate ===")

# Sensor formula: F = 98 * Q, so Q = F / 98 = (pulses/elapsed) / 98
# Q in L/min, F in Hz
# 1 L/min for 1 second = 98 pulses

assert_eq("zero elapsed returns 0",
    calculations.calculate_flow_rate(pulse_count=98, elapsed=0), 0)

assert_eq("elapsed < 0.1 returns 0",
    calculations.calculate_flow_rate(pulse_count=98, elapsed=0.05), 0)

assert_eq("98 pulses in 60s = 1 L/min",
    calculations.calculate_flow_rate(pulse_count=98*60, elapsed=60), 1.0)

assert_eq("zero pulses returns 0",
    calculations.calculate_flow_rate(pulse_count=0, elapsed=30), 0)

assert_eq("196 pulses in 60s = 2 L/min",
    calculations.calculate_flow_rate(pulse_count=196*60, elapsed=60), 2.0)


print("\n=== Keg Calculations ===")

assert_eq("full keg remaining",
    calculations.calculate_keg_remaining(keg_dispensed=0, keg_volume=18.93), 18.93)

assert_eq("partial keg remaining",
    calculations.calculate_keg_remaining(keg_dispensed=5, keg_volume=18.93), 13.93)

assert_eq("overflow clamped to 0",
    calculations.calculate_keg_remaining(keg_dispensed=20, keg_volume=18.93), 0)

assert_eq("full keg = 100%",
    calculations.calculate_keg_percent(keg_remaining=18.93, keg_volume=18.93), 100.0)

assert_eq("half keg = 50%",
    calculations.calculate_keg_percent(keg_remaining=9.465, keg_volume=18.93), 50.0)

assert_eq("empty keg = 0%",
    calculations.calculate_keg_percent(keg_remaining=0, keg_volume=18.93), 0.0)


print("\n=== MQTT Payload ===")

payload = calculations.build_mqtt_payload(1.5, 3.0, 15.93, 84.2)
data = ujson.loads(payload)
assert_eq("payload flow_rate", data["flow_rate"], 1.5)
assert_eq("payload total_volume", data["total_volume"], 3.0)
assert_eq("payload keg_remaining", data["keg_remaining"], 15.93)
assert_eq("payload keg_percent", data["keg_percent"], 84.2)


print("\n=== Timezone Offset ===")

assert_eq("july is DST (+1h)",
    calculations.get_timezone_offset(7, -8 * 3600), -7 * 3600)

assert_eq("december is not DST",
    calculations.get_timezone_offset(12, -8 * 3600), -8 * 3600)

assert_eq("april is DST boundary",
    calculations.get_timezone_offset(4, -8 * 3600), -7 * 3600)

assert_eq("november is not DST",
    calculations.get_timezone_offset(11, -8 * 3600), -8 * 3600)


# ─── state.py ─────────────────────────────────────────────────────────────────

print("\n=== State: Persistence ===")

s = fresh_state()
state_module.save(s)
loaded = state_module.load()
assert_eq("load/save roundtrip keg_dispensed", loaded["keg_dispensed"], 0.0)
assert_eq("load/save roundtrip total_pulses", loaded["total_pulses"], 0)
assert_eq("load/save roundtrip stay_awake", loaded["stay_awake"], 0)
assert_eq("last_publish reset to 0 on load", loaded["last_publish"], 0)

s2 = {"keg_dispensed": 5.5, "total_pulses": 2475, "stay_awake": 60, "last_publish": 9999}
state_module.save(s2)
loaded2 = state_module.load()
assert_eq("persist keg_dispensed", loaded2["keg_dispensed"], 5.5)
assert_eq("persist total_pulses", loaded2["total_pulses"], 2475)
assert_eq("persist stay_awake", loaded2["stay_awake"], 60)
assert_eq("last_publish always 0 on load", loaded2["last_publish"], 0)


print("\n=== State: on_reset ===")

s = {"keg_dispensed": 8.0, "total_pulses": 5000, "stay_awake": 30, "last_publish": 100}
result = state_module.on_reset(s)
assert_eq("on_reset zeroes keg_dispensed", result["keg_dispensed"], 0.0)
assert_eq("on_reset preserves total_pulses", result["total_pulses"], 5000)
assert_eq("on_reset preserves stay_awake", result["stay_awake"], 30)
assert_eq("on_reset preserves last_publish", result["last_publish"], 100)
assert_eq("on_reset does not mutate original", s["keg_dispensed"], 8.0)


print("\n=== State: on_wake_command ===")

s = {"keg_dispensed": 2.0, "total_pulses": 100, "stay_awake": 0, "last_publish": 50}
result = state_module.on_wake_command(s, timeout=300)
assert_eq("on_wake_command sets stay_awake", result["stay_awake"], 300)
assert_eq("on_wake_command preserves keg_dispensed", result["keg_dispensed"], 2.0)
assert_eq("on_wake_command preserves total_pulses", result["total_pulses"], 100)
assert_eq("on_wake_command does not mutate original", s["stay_awake"], 0)


print("\n=== State: on_pulse ===")

s = {"keg_dispensed": 0.0, "total_pulses": 0, "stay_awake": 0, "last_publish": 0}
result = state_module.on_pulse(s, pulse_count=98, pulses_per_liter=98)
assert_eq("on_pulse increments total_pulses", result["total_pulses"], 98)
assert_eq("on_pulse increments keg_dispensed by 1L", result["keg_dispensed"], 1.0)
assert_eq("on_pulse does not mutate original total_pulses", s["total_pulses"], 0)

s2 = {"keg_dispensed": 1.0, "total_pulses": 98, "stay_awake": 0, "last_publish": 0}
result2 = state_module.on_pulse(s2, pulse_count=49, pulses_per_liter=98)
assert_eq("on_pulse accumulates keg_dispensed", result2["keg_dispensed"], 1.5)
assert_eq("on_pulse accumulates total_pulses", result2["total_pulses"], 147)


print("\n=== State: on_publish ===")

s = {"keg_dispensed": 2.0, "total_pulses": 200, "stay_awake": 0, "last_publish": 0}
result = state_module.on_publish(s, now=12345)
assert_eq("on_publish sets last_publish", result["last_publish"], 12345)
assert_eq("on_publish preserves keg_dispensed", result["keg_dispensed"], 2.0)
assert_eq("on_publish does not mutate original", s["last_publish"], 0)


print("\n=== State: on_sleep_tick ===")

s = {"keg_dispensed": 0.0, "total_pulses": 0, "stay_awake": 10, "last_publish": 0}
result = state_module.on_sleep_tick(s)
assert_eq("on_sleep_tick decrements stay_awake", result["stay_awake"], 9)
assert_eq("on_sleep_tick does not mutate original", s["stay_awake"], 10)

s2 = {"keg_dispensed": 0.0, "total_pulses": 0, "stay_awake": 0, "last_publish": 0}
result2 = state_module.on_sleep_tick(s2)
assert_eq("on_sleep_tick clamps at 0", result2["stay_awake"], 0)


print("\n=== State: should_publish ===")

s = {"keg_dispensed": 0.0, "total_pulses": 0, "stay_awake": 0, "last_publish": 0}
s_fresh = {"keg_dispensed": 0.0, "total_pulses": 0, "stay_awake": 0, "last_publish": 0}
assert_eq("always publish when last_publish=0",
    state_module.should_publish(s_fresh, now=0, interval=30), True)

s_published = {"keg_dispensed": 0.0, "total_pulses": 0, "stay_awake": 0, "last_publish": 100}
assert_eq("should_publish when interval elapsed",
    state_module.should_publish(s_published, now=131, interval=30), True)

assert_eq("should not publish before interval",
    state_module.should_publish(s_published, now=129, interval=30), False)


print("\n=== State: should_sleep ===")

s_awake = {"keg_dispensed": 0.0, "total_pulses": 0, "stay_awake": 10, "last_publish": 0}
assert_eq("should not sleep when stay_awake > 0",
    state_module.should_sleep(s_awake), False)

s_sleep = {"keg_dispensed": 0.0, "total_pulses": 0, "stay_awake": 0, "last_publish": 0}
assert_eq("should sleep when stay_awake == 0",
    state_module.should_sleep(s_sleep), True)


print("\n=== All Tests Passed! ===")
