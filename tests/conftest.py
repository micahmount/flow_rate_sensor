import sys
from unittest.mock import MagicMock

import pytest


class MockTime:
    def localtime(self, timestamp=None):
        return (2025, 6, 15, 12, 0, 0, 0, 0)
    def time(self):
        return 0
    def sleep(self, secs):
        pass
    def sleep_ms(self, ms):
        pass
    ticks_ms = MagicMock(return_value=0)
    ticks_diff = MagicMock(return_value=100)


class MockWLAN:
    def __init__(self, *args, **kwargs):
        self._ifconfig = ("192.168.1.100", "255.255.255.0", "192.168.1.1", "8.8.8.8")
    def active(self, *args, **kwargs):
        pass
    def config(self, *args, **kwargs):
        pass
    def isconnected(self):
        return True
    def ifconfig(self):
        return self._ifconfig
    def disconnect(self):
        pass


class MockNetwork:
    STA_IF = "STA_IF"
    def WLAN(self, *args, **kwargs):
        return MockWLAN()


MOCK_MODULES = {
    "time": MockTime(),
    "ntptime": MagicMock(),
    "webrepl": MagicMock(),
    "machine": MagicMock(),
    "umqtt": MagicMock(),
    "umqtt.simple": MagicMock(),
    "network": MockNetwork(),
    "esp32": MagicMock(),
}
for name, mock in MOCK_MODULES.items():
    if name not in sys.modules:
        sys.modules[name] = mock

import machine
machine.Pin = MagicMock()
machine.deepsleep = MagicMock()
for name, mock in MOCK_MODULES.items():
    if name not in sys.modules:
        sys.modules[name] = mock


@pytest.fixture(autouse=True)
def reset_main_globals():
    import main  # noqa: F401
    main.keg_dispensed = 0.0
    main.total_pulses = 0
    main.stay_awake = 0
    yield
