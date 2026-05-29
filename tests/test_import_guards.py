import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ImportGuardTests(unittest.TestCase):
    def test_climate_imports_constants_used_in_platform_schema(self):
        tree = ast.parse(
            (ROOT / "custom_components" / "ds_air" / "climate.py").read_text()
        )
        const_imports = {
            alias.name
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
            and node.module == "homeassistant.const"
            for alias in node.names
        }

        self.assertIn("CONF_HOST", const_imports)
        self.assertIn("CONF_PORT", const_imports)

    def test_sensor_entities_do_not_set_entity_id_manually(self):
        tree = ast.parse(
            (ROOT / "custom_components" / "ds_air" / "sensor.py").read_text()
        )

        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                    and target.attr == "entity_id"
                ):
                    self.fail("Sensor entities should not set entity_id manually")


if __name__ == "__main__":
    unittest.main()
