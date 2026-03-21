import pytest

import main  # noqa: F401 - needed for TOPIC_RESET, TOPIC_WAKE
from main import TOPIC_RESET, TOPIC_WAKE


class TestMQTTCallback:
    def test_reset_calls_reset_keg(self, monkeypatch):
        """TOPIC_RESET should call calculations.reset_keg() with current state"""
        main.keg_dispensed = 5.0
        main.total_pulses = 1000
        main.stay_awake = 60

        called_with = {}
        def mock_reset(keg_dispensed, total_pulses, stay_awake):
            called_with["keg_dispensed"] = keg_dispensed
            called_with["total_pulses"] = total_pulses
            called_with["stay_awake"] = stay_awake
        monkeypatch.setattr(main.calculations, "reset_keg", mock_reset)

        main.mqtt_callback(TOPIC_RESET, b"")

        assert called_with["keg_dispensed"] == 5.0
        assert called_with["total_pulses"] == 1000
        assert called_with["stay_awake"] == 60

    def test_reset_sets_global_keg_dispensed(self, monkeypatch):
        """TOPIC_RESET should set global keg_dispensed = 0.0"""
        main.keg_dispensed = 10.0
        main.total_pulses = 500
        main.stay_awake = 0
        monkeypatch.setattr(main.calculations, "reset_keg", lambda *args: 0.0)

        main.mqtt_callback(TOPIC_RESET, b"")

        assert main.keg_dispensed == 0.0

    def test_reset_leaves_total_pulses_unchanged(self, monkeypatch):
        """TOPIC_RESET should NOT reset total_pulses"""
        main.total_pulses = 5000
        monkeypatch.setattr(main.calculations, "reset_keg", lambda *args: 0.0)

        main.mqtt_callback(TOPIC_RESET, b"")

        assert main.total_pulses == 5000

    def test_wake_sets_stay_awake(self, monkeypatch):
        """TOPIC_WAKE should set stay_awake to WAKE_TIMEOUT_SECONDS"""
        main.stay_awake = 0
        monkeypatch.setattr(main.calculations, "save_state", lambda *args: None)

        main.mqtt_callback(TOPIC_WAKE, b"WAKE")

        assert main.stay_awake == main.WAKE_TIMEOUT_SECONDS

    def test_wake_saves_state(self, monkeypatch):
        """TOPIC_WAKE should call save_state after setting stay_awake"""
        main.keg_dispensed = 3.0
        main.total_pulses = 200
        main.stay_awake = 0

        called_with = {}
        def mock_save(keg, total, awake):
            called_with["keg"] = keg
            called_with["total"] = total
            called_with["awake"] = awake
        monkeypatch.setattr(main.calculations, "save_state", mock_save)

        main.mqtt_callback(TOPIC_WAKE, b"WAKE")

        assert called_with["keg"] == 3.0
        assert called_with["total"] == 200
        assert called_with["awake"] == main.WAKE_TIMEOUT_SECONDS
