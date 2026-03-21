import pytest
import ujson

import calculations


class TestFlowRate:
    def test_zero_elapsed_returns_zero(self):
        result = calculations.calculate_flow_rate(pulse_count=10, elapsed=0)
        assert result == 0

    def test_too_short_elapsed_returns_zero(self):
        result = calculations.calculate_flow_rate(pulse_count=10, elapsed=0.05)
        assert result == 0

    def test_normal_flow_rate(self):
        """450 pulses per liter, 450 pulses in 60 seconds = 1 L/min"""
        result = calculations.calculate_flow_rate(pulse_count=450, elapsed=60, pulses_per_liter=450)
        assert result == 1.0

    def test_fractional_flow_rate(self):
        """450 pulses per liter, 225 pulses in 60 seconds = 0.5 L/min"""
        result = calculations.calculate_flow_rate(pulse_count=225, elapsed=60, pulses_per_liter=450)
        assert result == 0.5

    def test_zero_pulses_returns_zero(self):
        result = calculations.calculate_flow_rate(pulse_count=0, elapsed=30, pulses_per_liter=450)
        assert result == 0

    def test_rounds_to_three_decimals(self):
        """Verify precision doesn't drift"""
        result = calculations.calculate_flow_rate(pulse_count=100, elapsed=17, pulses_per_liter=450)
        assert result == round(100 / 17 * 60 / 450, 3)


class TestKegCalculations:
    def test_keg_remaining_full_keg(self):
        result = calculations.calculate_keg_remaining(keg_dispensed=0, keg_volume=18.93)
        assert result == 18.93

    def test_keg_remaining_partial(self):
        result = calculations.calculate_keg_remaining(keg_dispensed=5, keg_volume=18.93)
        assert result == 13.93

    def test_keg_remaining_empty(self):
        result = calculations.calculate_keg_remaining(keg_dispensed=18.93, keg_volume=18.93)
        assert result == 0

    def test_keg_remaining_overflow_clamped(self):
        result = calculations.calculate_keg_remaining(keg_dispensed=20, keg_volume=18.93)
        assert result == 0

    def test_keg_percent_full(self):
        result = calculations.calculate_keg_percent(keg_remaining=18.93, keg_volume=18.93)
        assert result == 100.0

    def test_keg_percent_half(self):
        result = calculations.calculate_keg_percent(keg_remaining=9.465, keg_volume=18.93)
        assert result == 50.0

    def test_keg_percent_empty(self):
        result = calculations.calculate_keg_percent(keg_remaining=0, keg_volume=18.93)
        assert result == 0.0

    def test_rounds_to_one_decimal(self):
        result = calculations.calculate_keg_percent(keg_remaining=6.28, keg_volume=18.93)
        assert result == round(6.28 / 18.93 * 100, 1)


class TestMQTTPayload:
    def test_payload_structure(self):
        payload = calculations.build_mqtt_payload(
            flow_rate=1.5,
            total_volume=3.0,
            keg_remaining=15.93,
            keg_percent=84.2
        )
        data = ujson.loads(payload)
        assert data["flow_rate"] == 1.5
        assert data["total_volume"] == 3.0
        assert data["keg_remaining"] == 15.93
        assert data["keg_percent"] == 84.2

    def test_payload_is_valid_json(self):
        payload = calculations.build_mqtt_payload(1.0, 2.0, 16.93, 89.5)
        data = ujson.loads(payload)
        assert isinstance(data, dict)
        assert len(data) == 4


class TestStatePersistence:
    def test_load_state_defaults(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        monkeypatch.setattr(calculations, "STATE_FILE", str(state_file))
        keg, total, awake = calculations.load_state()
        assert keg == 0.0
        assert total == 0
        assert awake == 0

    def test_load_state_existing_file(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        state_file.write_text(ujson.dumps({
            "keg_dispensed": 5.5,
            "total_pulses": 2475,
            "stay_awake": 120
        }))
        monkeypatch.setattr(calculations, "STATE_FILE", str(state_file))
        keg, total, awake = calculations.load_state()
        assert keg == 5.5
        assert total == 2475
        assert awake == 120

    def test_load_state_partial_file(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        state_file.write_text(ujson.dumps({"keg_dispensed": 2.0}))
        monkeypatch.setattr(calculations, "STATE_FILE", str(state_file))
        keg, total, awake = calculations.load_state()
        assert keg == 2.0
        assert total == 0
        assert awake == 0

    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        monkeypatch.setattr(calculations, "STATE_FILE", str(state_file))
        calculations.save_state(keg_dispensed=3.7, total_pulses=1665, stay_awake=45)
        keg, total, awake = calculations.load_state()
        assert keg == 3.7
        assert total == 1665
        assert awake == 45

    def test_save_state_overwrites(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        monkeypatch.setattr(calculations, "STATE_FILE", str(state_file))
        calculations.save_state(keg_dispensed=1.0, total_pulses=100, stay_awake=10)
        calculations.save_state(keg_dispensed=5.0, total_pulses=500, stay_awake=0)
        keg, total, awake = calculations.load_state()
        assert keg == 5.0
        assert total == 500
        assert awake == 0


class TestTimezoneOffset:
    def test_winter_pacific(self):
        """December in PST (UTC-8)"""
        result = calculations.get_timezone_offset(month=12, base_offset=-8 * 3600)
        assert result == -8 * 3600

    def test_summer_pacific(self):
        """July in PDT (UTC-7)"""
        result = calculations.get_timezone_offset(month=7, base_offset=-8 * 3600)
        assert result == -7 * 3600

    def test_april_dst_boundary(self):
        """April is DST"""
        result = calculations.get_timezone_offset(month=4, base_offset=-5 * 3600)
        assert result == -4 * 3600

    def test_november_no_dst(self):
        """November is not DST"""
        result = calculations.get_timezone_offset(month=11, base_offset=-5 * 3600)
        assert result == -5 * 3600

    def test_january_no_dst(self):
        """January is not DST"""
        result = calculations.get_timezone_offset(month=1, base_offset=-5 * 3600)
        assert result == -5 * 3600


class TestResetKeg:
    def test_reset_keg_returns_zero_dispensed(self):
        """Reset should return keg_dispensed = 0.0"""
        result = calculations.reset_keg(keg_dispensed=5.0, total_pulses=100, stay_awake=0)
        assert result == 0.0

    def test_reset_keg_preserves_total_pulses(self):
        """Reset should NOT reset total_pulses — it's a lifetime counter"""
        calculations.reset_keg(keg_dispensed=3.0, total_pulses=500, stay_awake=0)
        # No assertion on return — total_pulses is preserved (not touched)

    def test_reset_keg_saves_to_file(self, tmp_path, monkeypatch):
        """Reset should persist keg_dispensed = 0.0 to state file"""
        state_file = tmp_path / "state.json"
        monkeypatch.setattr(calculations, "STATE_FILE", str(state_file))
        calculations.save_state(keg_dispensed=10.0, total_pulses=1000, stay_awake=0)
        calculations.reset_keg(keg_dispensed=10.0, total_pulses=1000, stay_awake=0)
        keg, total, awake = calculations.load_state()
        assert keg == 0.0
        assert total == 1000
        assert awake == 0

    def test_reset_keg_preserves_stay_awake(self, tmp_path, monkeypatch):
        """Reset should NOT reset stay_awake — device keeps awake status"""
        state_file = tmp_path / "state.json"
        monkeypatch.setattr(calculations, "STATE_FILE", str(state_file))
        calculations.save_state(keg_dispensed=5.0, total_pulses=500, stay_awake=120)
        calculations.reset_keg(keg_dispensed=5.0, total_pulses=500, stay_awake=120)
        keg, total, awake = calculations.load_state()
        assert awake == 120
