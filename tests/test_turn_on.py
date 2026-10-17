"""Regression tests for the real turn-on method and its encoded wire command.

The AST harness avoids requiring a full Home Assistant installation. It executes
methods extracted unchanged from the integration and pinned Core source; it does
not replace the production encoder with a mock.
"""
import ast
import asyncio
from enum import StrEnum
from pathlib import Path
import select  # noqa: F401 - prevent integration select.py shadowing stdlib
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/ds_air"
sys.path.insert(0, str(COMPONENT))
from ds_air_service.config import Config
from ds_air_service.ctrl_enum import EnumControl
from ds_air_service.dao import AirCon, AirConStatus
from ds_air_service.param import AirConControlParam, Encode


class HVACMode(StrEnum):
    OFF = "off"
    COOL = "cool"
    HEAT = "heat"
    DRY = "dry"
    AUTO = "auto"
    FAN_ONLY = "fan_only"
    HEAT_COOL = "heat_cool"


class HomeAssistantError(Exception):
    pass


def extract(path, class_name, methods, namespace):
    tree = ast.parse(path.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    cls.body = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in methods]
    cls.bases = []
    cls.keywords = []
    cls.decorator_list = []
    code = ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[]))
    exec(compile(code, str(path), "exec"), namespace)
    return namespace[class_name]


const_tree = ast.parse((COMPONENT / "const.py").read_text())
const_nodes = [n for n in const_tree.body if
               isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "_MODE_NAME_LIST" for t in n.targets)
               or isinstance(n, ast.FunctionDef) and n.name == "get_mode_name"]
NS = dict(HVACMode=HVACMode, HomeAssistantError=HomeAssistantError,
          EnumControl=EnumControl, AirConStatus=AirConStatus)
exec(compile(ast.Module(body=const_nodes, type_ignores=[]), "const.py", "exec"), NS)
DsAir = extract(COMPONENT / "climate.py", "DsAir", {"turn_on", "hvac_modes"}, NS)


class TurnOnTests(unittest.TestCase):
    def entity(self, mode=EnumControl.Mode.COLD, on=False):
        config = Config()
        config.is_c611 = True
        device = AirCon(config)
        device.room_id = 2
        device.unit_id = 0
        device.cool_mode = device.heat_mode = device.dry_mode = 1
        device.ventilation_mode = device.auto_mode = 1
        device.auto_dry_mode = device.relax_mode = device.sleep_mode = 1
        device.pre_heat_mode = device.more_dry_mode = 1
        device.status = AirConStatus(switch=EnumControl.Switch.ON if on else EnumControl.Switch.OFF,
                                    mode=mode, setted_temp=265, air_flow=EnumControl.AirFlow.AUTO)
        entity = DsAir()
        entity._device_info = device
        entity.service = SimpleNamespace(control=Mock())
        entity.schedule_update_ha_state = Mock()
        return entity

    def test_every_mode_preserves_raw_mode_and_only_encodes_power(self):
        for mode in EnumControl.Mode:
            for on in (False, True):
                for modern in (False, True):
                    with self.subTest(mode=mode, on=on, modern=modern):
                        entity = self.entity(mode, on)
                        device = entity._device_info
                        device.config.is_new_version = modern
                        before = dict(device.status.__dict__)
                        entity.turn_on()
                        target, sent = entity.service.control.call_args.args
                        self.assertIs(target, device)
                        self.assertEqual({k: v for k, v in vars(sent).items() if v is not None}, {"switch": EnumControl.Switch.ON})
                        encoder = Encode()
                        AirConControlParam(target, sent).generate_subbody(encoder, device.config)
                        self.assertEqual(encoder.pack(False), bytes([2, 0, 1, 1]))
                        self.assertEqual(vars(device.status), {**before, "switch": EnumControl.Switch.ON})
                        entity.schedule_update_ha_state.assert_called_once_with()

    def test_unknown_or_invalid_modes_fail_without_a_command(self):
        for mode in (None, -1, 10, "heat"):
            with self.subTest(mode=mode):
                entity = self.entity(mode)
                with self.assertRaises(HomeAssistantError):
                    entity.turn_on()
                entity.service.control.assert_not_called()
                self.assertEqual(entity._device_info.status.switch, EnumControl.Switch.OFF)

    def test_unavailable_heat_fails_without_selecting_cooling(self):
        entity = self.entity(EnumControl.Mode.HEAT)
        entity._device_info.heat_mode = 0
        with self.assertRaises(HomeAssistantError):
            entity.turn_on()
        entity.service.control.assert_not_called()

    def test_send_error_does_not_claim_power_on(self):
        entity = self.entity()
        entity.service.control.side_effect = OSError("disconnected")
        with self.assertRaises(OSError):
            entity.turn_on()
        self.assertEqual(entity._device_info.status.switch, EnumControl.Switch.OFF)
        entity.schedule_update_ha_state.assert_not_called()

    def test_disabled_raw_modes_fail_even_when_a_grouped_sibling_is_supported(self):
        for mode, capability in (
            (EnumControl.Mode.COLD, "cool_mode"),
            (EnumControl.Mode.DRY, "dry_mode"),
            (EnumControl.Mode.VENTILATION, "ventilation_mode"),
            (EnumControl.Mode.AUTO, "auto_mode"),
            (EnumControl.Mode.HEAT, "heat_mode"),
            (EnumControl.Mode.AUTODRY, "auto_dry_mode"),
            (EnumControl.Mode.RELAX, "relax_mode"),
            (EnumControl.Mode.SLEEP, "sleep_mode"),
            (EnumControl.Mode.PREHEAT, "pre_heat_mode"),
            (EnumControl.Mode.MOREDRY, "more_dry_mode"),
        ):
            with self.subTest(mode=mode):
                entity = self.entity(mode)
                setattr(entity._device_info, capability, 0)
                with self.assertRaises(HomeAssistantError):
                    entity.turn_on()
                entity.service.control.assert_not_called()

    def test_pinned_core_delegates_to_sync_override_without_selecting_heat(self):
        core_path = Path(__file__).parent / "fixtures" / "core-climate-2026.9.4.py"
        namespace = {"HVACMode": HVACMode}
        core = extract(core_path, "ClimateEntity", {"turn_on", "async_turn_on"}, namespace)
        class Combined(DsAir, core):
            async def async_set_hvac_mode(self, mode):
                raise AssertionError("Core fallback must not select any HVAC mode")
        entity = self.entity()
        entity.__class__ = Combined
        async def executor(fn):
            fn()
        entity.hass = SimpleNamespace(async_add_executor_job=executor)
        asyncio.run(entity.async_turn_on())
        self.assertEqual(entity._device_info.status.mode, EnumControl.Mode.COLD)
        entity.service.control.assert_called_once()


if __name__ == "__main__":
    unittest.main()
