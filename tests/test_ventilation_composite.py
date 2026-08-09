from pathlib import Path
import sys
import unittest
import select  # noqa: F401 — preload stdlib select to prevent clash with custom_components/ds_air/select.py


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "ds_air"))

from ds_air_service.config import Config  # noqa: E402
from ds_air_service.ctrl_enum import EnumDevice  # noqa: E402
from ds_air_service.decoder import VentilationQueryCompositeSituationResult  # noqa: E402


class FakeService:
    def __init__(self):
        self.room = None
        self.unit = None
        self.status = None

    def set_ventilation_status(self, room, unit, status):
        self.room = room
        self.unit = unit
        self.status = status


class VentilationCompositeTests(unittest.TestCase):
    def test_d611_composite_payload_with_bound_air_sensor(self):
        config = Config()
        config.is_d611 = True
        payload = bytes.fromhex(
            "010060db88c200ff020202fb000102040003022a00040240020502c300"
            "060234000702040000010300ec94cb5ce00c0fe7a9bae6b094e4bca0"
            "e6849fe599a8010200010202c3010302020304020700050249000601040000"
        )
        result = VentilationQueryCompositeSituationResult(1, EnumDevice.SMALL_VAM)
        service = FakeService()

        result.load_bytes(payload, config)
        result.do(service)

        self.assertEqual(service.room, 1)
        self.assertEqual(service.unit, 0)
        self.assertEqual(service.status.in_door_temp, 256)
        self.assertEqual(service.status.out_door_temp, 195)
        self.assertEqual(service.status.out_door_humidity, 52)
        self.assertEqual(service.status.pm25, 4)

    def test_d611_composite_payload_without_bound_air_sensor(self):
        config = Config()
        config.is_d611 = True
        payload = bytes.fromhex(
            "010060db88c200ff020202fb000102040003022a00040240020502c300"
            "060234000702040000"
        )
        result = VentilationQueryCompositeSituationResult(1, EnumDevice.SMALL_VAM)
        service = FakeService()

        result.load_bytes(payload, config)
        result.do(service)

        self.assertEqual(service.room, 1)
        self.assertEqual(service.unit, 0)
        self.assertIsNone(service.status.in_door_temp)
        self.assertEqual(service.status.out_door_temp, 195)
        self.assertEqual(service.status.out_door_humidity, 52)
        self.assertEqual(service.status.pm25, 4)

    def test_legacy_composite_payload_keeps_existing_mapping(self):
        config = Config()
        payload = bytes.fromhex("01000102fa00020234000302c3000402070000")
        result = VentilationQueryCompositeSituationResult(1, EnumDevice.SMALL_VAM)
        service = FakeService()

        result.load_bytes(payload, config)
        result.do(service)

        self.assertEqual(service.room, 1)
        self.assertEqual(service.unit, 0)
        self.assertEqual(service.status.in_door_temp, 250)
        self.assertEqual(service.status.out_door_temp, 195)
        self.assertEqual(service.status.out_door_humidity, 52)
        self.assertEqual(service.status.pm25, 7)


if __name__ == "__main__":
    unittest.main()
