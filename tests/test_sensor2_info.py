from pathlib import Path
import select  # noqa: F401 — preload stdlib select before ds_air/select.py
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "ds_air"))

from ds_air_service.config import Config  # noqa: E402
from ds_air_service.ctrl_enum import EnumDevice  # noqa: E402
from ds_air_service.decoder import Sensor2InfoResult  # noqa: E402


class FakeService:
    def __init__(self):
        self.sensors = None

    def set_sensors_status(self, sensors):
        self.sensors = sensors


class Sensor2InfoTests(unittest.TestCase):
    def test_type4_sensor_stores_tvoc_and_hcho(self):
        payload = bytes.fromhex(
            "0102213b030001020304050606726f6f6d2d617f000d0125024000e001"
            "0121000000011801ff7fff7fff7f4b000000e8030000023c000a00010101"
            "16000800213a04010708090a0b0c06726f6f6d2d626f010401a8022c01fb"
            "02c3000100011801ff7fff7fff7f4b000000e8030000023c000800010101"
            "16000800"
        )
        result = Sensor2InfoResult(1, EnumDevice.SENSOR)
        service = FakeService()

        result.load_bytes(payload, Config())
        result.do(service)

        self.assertEqual(len(service.sensors), 2)
        old_sensor, new_sensor = service.sensors
        self.assertEqual(old_sensor.sensor_type, 3)
        self.assertEqual(old_sensor.tvoc, 33)
        self.assertEqual(old_sensor.hcho, 0)
        self.assertEqual(new_sensor.sensor_type, 4)
        self.assertEqual(new_sensor.tvoc, 195)
        self.assertEqual(new_sensor.hcho, 1)
        self.assertEqual(new_sensor.tvoc_upper, 60)
        self.assertEqual(new_sensor.hcho_upper, 8)


if __name__ == "__main__":
    unittest.main()
