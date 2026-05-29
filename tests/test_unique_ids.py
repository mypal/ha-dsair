from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "ds_air"))

from ds_air_service import dao  # noqa: E402
from ds_air_service.dao import Device  # noqa: E402


class UniqueIdTests(unittest.TestCase):
    def test_same_room_and_unit_on_different_gateways_get_distinct_ids(self):
        first = Device()
        first.gateway_id = "entry_a"
        first.room_id = 1
        first.unit_id = 0

        second = Device()
        second.gateway_id = "entry_b"
        second.room_id = 1
        second.unit_id = 0

        self.assertEqual(first.unique_id, "daikin_entry_a_1_0")
        self.assertEqual(second.unique_id, "daikin_entry_b_1_0")
        self.assertNotEqual(first.unique_id, second.unique_id)

    def test_prefixed_sensor_unique_id_inserts_gateway_after_daikin(self):
        self.assertFalse(hasattr(dao, "build_prefixed_unique_id"))
        device_unique_id = dao.build_device_unique_id("entry_a", 1, 0)

        self.assertEqual(
            f"temp_{device_unique_id}",
            "temp_daikin_entry_a_1_0",
        )

    def test_default_device_names_do_not_include_gateway_prefix(self):
        self.assertTrue(hasattr(dao, "build_aircon_device_name"))
        self.assertTrue(hasattr(dao, "build_sensor_device_name"))

        self.assertEqual(dao.build_aircon_device_name("客厅"), "客厅 空调")
        self.assertEqual(dao.build_aircon_device_name("客厅空调"), "客厅空调")
        self.assertEqual(dao.build_sensor_device_name("客厅"), "客厅 传感器")


if __name__ == "__main__":
    unittest.main()
