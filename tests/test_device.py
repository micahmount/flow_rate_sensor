import time
import ujson
import calculations
import state as state_module
import main


# ─── Helpers ──────────────────────────────────────────────────────────────────

def assert_eq(label, actual, expected):
    assert actual == expected, f"FAIL [{label}]: expected {expected}, got {actual}"
    print(f"PASS: {label}")


# ─── Versioning (SemVer) ──────────────────────────────────────────────────────

print("\n=== Firmware Version ===")

def assert_valid_semver(version):
    core, _, _ = version.partition("-")
    parts = core.split(".")
    assert len(parts) == 3, f"VERSION {version!r} must be MAJOR.MINOR.PATCH"
    for part in parts:
        assert part.isdigit(), f"invalid version part {part!r}"
        assert part == "0" or not part.startswith("0"), f"leading zero in {part!r}"
    print(f"PASS: main.VERSION is valid semver: {version}")

assert_valid_semver(main.VERSION)
assert_eq("version string not empty", bool(main.VERSION), True)


# ─── Human Duration ──────────────────────────────────────────────────────────

print("\n=== Human Duration ===")

assert_eq("270000ms = 4m 30s", main.human_duration(270000), "4m 30s")
assert_eq("60000ms = 1m 0s",   main.human_duration(60000),  "1m 0s")
assert_eq("30000ms = 30s",     main.human_duration(30000),  "30s")
assert_eq("1000ms = 1s",       main.human_duration(1000),   "1s")
assert_eq("3600000ms = 1h 0m", main.human_duration(3600000), "1h 0m")
assert_eq("7500000ms = 2h 5m", main.human_duration(7500000), "2h 5m")
assert_eq("90000ms = 1m 30s",  main.human_duration(90000),  "1m 30s")


# ─── calculations.py ──────────────────────────────────────────────────────────

print("\n=== Flow Rate ===")

# flow_rate = (pulse_count / elapsed_seconds) / PULSES_PER_LITER * 60
# PULSES_PER_LITER = 5880 (datasheet: F = 98 x Q, so 98 Hz at 1 L/min = 5880 pulses/min)
# 1 L/min → 98 Hz → 5880 pulses in 60s

assert_eq("zero elapsed returns 0",
    calculations.calculate_flow_rate(pulse_count=5880, elapsed=0, pulses_per_liter=5880), 0)

assert_eq("elapsed < 0.1 returns 0",
    calculations.calculate_flow_rate(pulse_count=5880, elapsed=0.05, pulses_per_liter=5880), 0)

assert_eq("5880 pulses in 60s = 1 L/min",
    calculations.calculate_flow_rate(pulse_count=5880, elapsed=60, pulses_per_liter=5880), 1.0)

assert_eq("zero pulses returns 0",
    calculations.calculate_flow_rate(pulse_count=0, elapsed=30, pulses_per_liter=5880), 0)

assert_eq("11760 pulses in 60s = 2 L/min",
    calculations.calculate_flow_rate(pulse_count=11760, elapsed=60, pulses_per_liter=5880), 2.0)


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

payload = calculations.build_mqtt_payload(1.5, 3.0, 15.93, 84.2, "2026-07-13 10:00:00", version="1.3.1")
data = ujson.loads(payload)
assert_eq("payload flow_rate",    data["flow_rate"],    1.5)
assert_eq("payload total_volume", data["total_volume"], 3.0)
assert_eq("payload keg_remaining",data["keg_remaining"],15.93)
assert_eq("payload keg_percent",  data["keg_percent"],  84.2)
assert_eq("payload last_updated", data["last_updated"], "2026-07-13 10:00:00")
assert_eq("payload version",      data["version"],      "1.3.1")


print("\n=== Timestamp Format ===")

now = int(time.time())
ts = calculations.format_timestamp(now, 0)
assert_eq("format_timestamp returns 19-char string", len(ts), 19)
assert_eq("format_timestamp 4th char is hyphen",     ts[4],   "-")
assert_eq("format_timestamp 7th char is hyphen",     ts[7],   "-")
assert_eq("format_timestamp 10th char is space",     ts[10],  " ")
assert_eq("format_timestamp 13th char is colon",     ts[13],  ":")
assert_eq("format_timestamp 16th char is colon",     ts[16],  ":")


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

s = dict(state_module.DEFAULT_STATE)
state_module.save(s)
loaded = state_module.load()
assert_eq("load/save roundtrip keg_dispensed",    loaded["keg_dispensed"],      0.0)
assert_eq("load/save roundtrip total_pulses",     loaded["total_pulses"],       0)
assert_eq("load/save roundtrip stay_awake_enabled",loaded["stay_awake_enabled"],False)
assert_eq("last_publish reset to 0 on load",      loaded["last_publish"],       0)

s2 = {"keg_dispensed": 5.5, "total_pulses": 2475, "stay_awake_enabled": True, "last_publish": 9999}
state_module.save(s2)
loaded2 = state_module.load()
assert_eq("persist keg_dispensed",         loaded2["keg_dispensed"],      5.5)
assert_eq("persist total_pulses",          loaded2["total_pulses"],       2475)
assert_eq("persist stay_awake_enabled",    loaded2["stay_awake_enabled"], True)
assert_eq("last_publish always 0 on load", loaded2["last_publish"],       0)


print("\n=== State: on_reset ===")

s = {"keg_dispensed": 8.0, "total_pulses": 5000, "stay_awake_enabled": True, "last_publish": 100}
result = state_module.on_reset(s)
assert_eq("on_reset zeroes keg_dispensed",       result["keg_dispensed"],      0.0)
assert_eq("on_reset preserves total_pulses",     result["total_pulses"],       5000)
assert_eq("on_reset preserves stay_awake_enabled",result["stay_awake_enabled"],True)
assert_eq("on_reset preserves last_publish",     result["last_publish"],       100)
assert_eq("on_reset does not mutate original",   s["keg_dispensed"],           8.0)


print("\n=== State: on_pulse ===")

s = {"keg_dispensed": 0.0, "total_pulses": 0, "stay_awake_enabled": False, "last_publish": 0}
result = state_module.on_pulse(s, pulse_count=98, pulses_per_liter=98)
assert_eq("on_pulse increments total_pulses",            result["total_pulses"],  98)
assert_eq("on_pulse increments keg_dispensed by 1L",     result["keg_dispensed"], 1.0)
assert_eq("on_pulse does not mutate original total_pulses", s["total_pulses"],    0)

s2 = {"keg_dispensed": 1.0, "total_pulses": 98, "stay_awake_enabled": False, "last_publish": 0}
result2 = state_module.on_pulse(s2, pulse_count=49, pulses_per_liter=98)
assert_eq("on_pulse accumulates keg_dispensed", result2["keg_dispensed"], 1.5)
assert_eq("on_pulse accumulates total_pulses",  result2["total_pulses"],  147)


print("\n=== State: on_publish ===")

s = {"keg_dispensed": 2.0, "total_pulses": 200, "stay_awake_enabled": False, "last_publish": 0}
result = state_module.on_publish(s, now=12345)
assert_eq("on_publish sets last_publish",        result["last_publish"],  12345)
assert_eq("on_publish preserves keg_dispensed",  result["keg_dispensed"], 2.0)
assert_eq("on_publish does not mutate original", s["last_publish"],       0)


print("\n=== State: should_publish ===")

s_fresh = {"keg_dispensed": 0.0, "total_pulses": 0, "stay_awake_enabled": False, "last_publish": 0}
assert_eq("always publish when last_publish=0",
    state_module.should_publish(s_fresh, now=0, interval=30), True)

s_pub = {"keg_dispensed": 0.0, "total_pulses": 0, "stay_awake_enabled": False, "last_publish": 100}
assert_eq("should_publish when interval elapsed",
    state_module.should_publish(s_pub, now=131, interval=30), True)

assert_eq("should not publish before interval",
    state_module.should_publish(s_pub, now=129, interval=30), False)


print("\n=== State: should_sleep ===")

s_awake = {"keg_dispensed": 0.0, "total_pulses": 0, "stay_awake_enabled": True,  "last_publish": 0}
assert_eq("should not sleep when stay_awake_enabled",
    state_module.should_sleep(s_awake), False)

s_sleep = {"keg_dispensed": 0.0, "total_pulses": 0, "stay_awake_enabled": False, "last_publish": 0}
assert_eq("should sleep when stay_awake_enabled=False",
    state_module.should_sleep(s_sleep), True)


print("\n=== All Tests Passed! ===")
