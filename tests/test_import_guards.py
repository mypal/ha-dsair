import ast
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ImportGuardTests(unittest.TestCase):
    def test_default_gateway_name_is_jzkq(self):
        tree = ast.parse(
            (ROOT / "custom_components" / "ds_air" / "const.py").read_text()
        )

        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if not any(
                isinstance(target, ast.Name) and target.id == "CN_GATEWAY_NAME"
                for target in node.targets
            ):
                continue
            self.assertIsInstance(node.value, ast.Constant)
            self.assertEqual(node.value.value, "金制空气")
            break
        else:
            self.fail("CN_GATEWAY_NAME is not defined")

    def test_gateway_name_compatibility_code_is_removed(self):
        tree = ast.parse(
            (ROOT / "custom_components" / "ds_air" / "const.py").read_text()
        )
        names = {
            target.id
            for node in tree.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        functions = {
            node.name for node in tree.body if isinstance(node, ast.FunctionDef)
        }

        self.assertNotIn("OLD_CN_GATEWAY_NAME", names)
        self.assertNotIn("LEGACY_GATEWAY_TITLES", names)
        self.assertNotIn("is_legacy_gateway_title", functions)
        self.assertNotIn("get_gateway_name", functions)

    def test_translation_files_are_retained_without_new_english_titles(self):
        translation_files = {
            path.name
            for path in (
                ROOT / "custom_components" / "ds_air" / "translations"
            ).glob("*.json")
        }
        self.assertEqual(translation_files, {"en.json", "zh-Hans.json"})

        chinese_translations = json.loads(
            (
                ROOT
                / "custom_components"
                / "ds_air"
                / "translations"
                / "zh-Hans.json"
            ).read_text()
        )
        english_translations = json.loads(
            (
                ROOT
                / "custom_components"
                / "ds_air"
                / "translations"
                / "en.json"
            ).read_text()
        )

        self.assertEqual(
            chinese_translations["config"]["step"]["user"]["title"], "金制空气"
        )
        self.assertEqual(chinese_translations["config"]["flow_title"], "金制空气")
        self.assertEqual(
            chinese_translations["options"]["step"]["init"]["title"], "金制空气"
        )
        self.assertEqual(
            english_translations["config"]["step"]["user"]["title"], "DS-AIR"
        )
        self.assertEqual(english_translations["config"]["flow_title"], "DS-AIR")
        self.assertEqual(
            english_translations["options"]["step"]["init"]["title"], "DS-AIR"
        )

    def test_config_entry_migration_code_is_removed(self):
        init_tree = ast.parse(
            (ROOT / "custom_components" / "ds_air" / "__init__.py").read_text()
        )
        dao_tree = ast.parse(
            (
                ROOT
                / "custom_components"
                / "ds_air"
                / "ds_air_service"
                / "dao.py"
            ).read_text()
        )
        function_names = {
            node.name
            for tree in (init_tree, dao_tree)
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        self.assertNotIn("async_migrate_entry", function_names)
        self.assertFalse(
            any("migrate" in function_name for function_name in function_names)
        )

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

    def test_init_uses_single_device_registry_import(self):
        tree = ast.parse(
            (ROOT / "custom_components" / "ds_air" / "__init__.py").read_text()
        )

        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                self.assertNotEqual(
                    node.module, "homeassistant.helpers.device_registry"
                )

    def test_config_flow_does_not_set_minor_version(self):
        tree = ast.parse(
            (ROOT / "custom_components" / "ds_air" / "config_flow.py").read_text()
        )
        class_defs = {
            node.name: node for node in tree.body if isinstance(node, ast.ClassDef)
        }
        flow_class = class_defs["DsAirFlowHandler"]
        class_assignments = {
            target.id
            for node in flow_class.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }

        self.assertNotIn("MINOR_VERSION", class_assignments)

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
