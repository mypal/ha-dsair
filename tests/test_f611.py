"""F611 protocol regressions; no network or Home Assistant installation needed.

Protocol tests execute the actual encoder, decoder and service. The small flow
harness executes the production methods with only Home Assistant boundaries
stubbed; voluptuous remains the real schema validator.
"""
import ast
import asyncio
import json
import logging
from pathlib import Path
import select  # noqa: F401 - load stdlib before adding the component directory
import struct
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

import voluptuous as vol

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/ds_air"
sys.path.insert(0, str(COMPONENT))
from ds_air_service.config import Config
from ds_air_service.ctrl_enum import EnumCmdType, EnumControl, EnumDevice, EnumFanVolume
from ds_air_service.dao import AirCon, AirConStatus
from ds_air_service.decoder import decoder, HandShakeResult, UnknownResult
from ds_air_service.param import AirConQueryStatusParam
from ds_air_service.service import Service


def config_for(model):
    config = Config()
    config.is_c611 = model == "C611"
    config.is_d611 = model == "D611"
    config.is_f611 = model == "F611"
    config.is_new_version = True
    return config


def frame(command, body):
    # Synthetic frames: addresses and values are not a household capture.
    return struct.pack("<BHBBBBIBIBH", 2, 16 + len(body), 13, 0, 1, 0,
                       1, 8, 18, 1, command) + body + b"\x03"


def parse(command, body, model="F611"):
    result, remaining = decoder(frame(command, body), config_for(model))
    assert remaining == b""
    return result


def source_nodes(path, wanted):
    tree = ast.parse(path.read_text())
    return [n for n in tree.body if
            isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in wanted for t in n.targets)
            or isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in wanted]


def execute_nodes(nodes, namespace):
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *nodes], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), "production-harness", "exec"), namespace)


class F611ProtocolTests(unittest.TestCase):
    def test_room_discovery_model_selection(self):
        for model, command in (("B611", 0x30), ("C611", 0x30), ("D611", 0x130), ("F611", 0x130)):
            with self.subTest(model=model):
                service = SimpleNamespace(_config=config_for(model), send_msg=Mock())
                HandShakeResult(1, EnumDevice.SYSTEM).do(service)
                self.assertEqual(service.send_msg.call_args_list[0].args[0].cmd_type.value, command)

    def test_query_commands_and_prefix_masks(self):
        for model, command in (("B611", 3), ("C611", 3), ("D611", 3), ("F611", 0x103)):
            with self.subTest(model=model):
                config = config_for(model)
                device = AirCon(config)
                device.room_id, device.unit_id = 7, 1
                device.fan_volume = EnumFanVolume.NO
                query = AirConQueryStatusParam()
                query.device = device
                encoded = query.to_string(config)
                self.assertEqual(int.from_bytes(encoded[17:19], "little"), command)
                self.assertEqual(encoded[19:21], b"\x07\x01")
                if model == "F611":
                    self.assertEqual(encoded[21] & 0xC0, 0)

    def test_query_reuse_does_not_leak_v1_to_other_targets_or_models(self):
        config = config_for("F611")
        query = AirConQueryStatusParam()
        query.device = AirCon(config)
        query.to_string(config)
        query.target = EnumDevice.BATHROOM
        self.assertEqual(int.from_bytes(query.to_string(config)[17:19], "little"), 3)
        query.target = EnumDevice.AIRCON
        self.assertEqual(int.from_bytes(query.to_string(config_for("C611"))[17:19], "little"), 3)

    def test_v1_query_flags_do_not_become_ambient_temperature(self):
        result = parse(0x103, bytes.fromhex("0701ff0100020cf50021012d00"))
        self.assertEqual(result._status.setted_temp, 245)
        self.assertEqual(result._status.mode, EnumControl.Mode.COLD)
        self.assertIsNone(result._status.current_temp)
        self.assertIsNone(result._status.humidity)

    def test_v1_query_initializes_service_instead_of_only_emitting_a_hook(self):
        service = Service()
        service._aircons = [AirCon(config_for("F611"))]
        service._aircons[0].room_id, service._aircons[0].unit_id = 7, 1
        service._none_stat_dev_cnt = 1
        parse(0x103, bytes.fromhex("070117010002f500")).do(service)
        self.assertEqual(service._none_stat_dev_cnt, 0)
        self.assertEqual(service._aircons[0].status.setted_temp, 245)
        self.assertIsNone(service._aircons[0].status.current_temp)

    def test_partial_notifications_preserve_absent_fields(self):
        for command in (2, 0x102):
            with self.subTest(command=command):
                service = SimpleNamespace(update_aircon=Mock())
                parse(command, bytes.fromhex("07010101")).do(service)
                status = service.update_aircon.call_args.kwargs["status"]
                self.assertEqual(status.switch, EnumControl.Switch.ON)
                self.assertIsNone(status.mode)
                self.assertIsNone(status.setted_temp)
                self.assertIsNone(status.current_temp)

    def test_notification_bit3_is_one_byte_and_setpoint_stays_aligned(self):
        for command in (2, 0x102):
            with self.subTest(command=command):
                result = parse(command, bytes.fromhex("0701180cf500"))
                self.assertEqual(result._status.setted_temp, 245)
                self.assertIsNone(result._status.current_temp)

    def test_missing_prefix_field_fails_without_consuming_frame_terminator(self):
        for body in (b"", bytes.fromhex("0701"), bytes.fromhex("070110f5")):
            with self.subTest(body=body):
                with self.assertRaises(BufferError):
                    parse(0x103, body)

    def test_legacy_query_keeps_kinsei_offsets_for_c_d_and_f(self):
        for model in ("C611", "D611", "F611"):
            with self.subTest(model=model):
                result = parse(3, bytes.fromhex("07011f0100020cf500"), model)
                self.assertEqual(result.setted_temp, 245)
                self.assertTrue(result.hum_allow)

    def test_b611_keeps_two_byte_measured_temperature(self):
        result = parse(3, bytes.fromhex("070118eb00f500"), "B611")
        self.assertEqual(result.current_temp, 235)
        self.assertEqual(result.setted_temp, 245)

    def test_v1_dispatch_is_not_enabled_for_unverified_models(self):
        for model in ("B611", "C611", "D611"):
            self.assertIsInstance(parse(0x103, bytes.fromhex("07010101"), model), UnknownResult)

    def test_f611_poll_includes_ordinary_indoor_units_without_changing_interval(self):
        service = Service()
        service._config = config_for("F611")
        service._new_aircons = []
        service._aircons = [AirCon(service._config)]
        service.send_msg = Mock()
        service.poll_status()
        queries = [c.args[0] for c in service.send_msg.call_args_list if isinstance(c.args[0], AirConQueryStatusParam)]
        self.assertEqual(len(queries), 1)
        self.assertEqual(queries[0].target, EnumDevice.AIRCON)
        self.assertEqual(service.get_scan_interval(), 5)


class F611FlowTests(unittest.TestCase):
    def namespace(self):
        ns = {"vol": vol, "Any": object, "FlowResult": dict, "CONF_GW": "gw",
              "CONF_HOST": "host", "CONF_ENTRY_TYPE": "entry_type",
              "ENTRY_TYPE_GATEWAY": "gateway"}
        execute_nodes(source_nodes(COMPONENT / "const.py", {"B611", "C611", "D611", "F611", "DEFAULT_GW", "GW_LIST"}), ns)
        tree = ast.parse((COMPONENT / "config_flow.py").read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "DsAirFlowHandler")
        cls.body = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in {"__init__", "async_step_reconfigure"}]
        cls.bases, cls.keywords = [], []
        execute_nodes([cls], ns)
        return ns

    def test_reconfigure_changes_only_model_on_the_existing_entry(self):
        ns = self.namespace()
        entry = SimpleNamespace(data={"gw": ns["C611"], "scan_interval": 5, "host": "example.invalid"})
        flow = ns["DsAirFlowHandler"]()
        flow._get_reconfigure_entry = lambda: entry
        flow.async_update_reload_and_abort = Mock(return_value={"type": "abort"})
        asyncio.run(flow.async_step_reconfigure({"gw": ns["F611"]}))
        flow.async_update_reload_and_abort.assert_called_once_with(entry, data_updates={"gw": ns["F611"]})
        self.assertEqual(entry.data["scan_interval"], 5)

    def test_reconfigure_schema_accepts_f611_and_retains_current_default(self):
        ns = self.namespace()
        flow = ns["DsAirFlowHandler"]()
        flow._get_reconfigure_entry = lambda: SimpleNamespace(data={"gw": ns["C611"], "host": "example.invalid"})
        flow.async_show_form = lambda **kwargs: kwargs
        result = asyncio.run(flow.async_step_reconfigure())
        schema = result["data_schema"]
        self.assertEqual(schema({})["gw"], ns["C611"])
        self.assertEqual(schema({"gw": ns["F611"]})["gw"], ns["F611"])

    def test_reconfigure_rejects_power_entries_without_changing_data(self):
        ns = self.namespace()
        for data in ({"entry_type": "power", "token": "synthetic-token"}, {}):
            with self.subTest(data=data):
                entry = SimpleNamespace(data=data)
                flow = ns["DsAirFlowHandler"]()
                flow._get_reconfigure_entry = lambda: entry
                flow.async_abort = Mock(return_value={"type": "abort"})
                flow.async_update_reload_and_abort = Mock()
                asyncio.run(flow.async_step_reconfigure({"gw": ns["F611"]}))
                flow.async_abort.assert_called_once_with(reason="reconfigure_not_supported")
                flow.async_update_reload_and_abort.assert_not_called()

    def test_setup_selects_f611_profile_without_aliasing_it_to_b611_or_d611(self):
        service = SimpleNamespace(init=Mock(), get_aircons=lambda: [])
        ns = {"Config": Config, "Service": lambda: service, "DOMAIN": "ds_air", "MANUFACTURER": "Daikin", "PLATFORMS": [],
              "CONF_HOST": "host", "CONF_PORT": "port", "CONF_GW": "gw", "CONF_SCAN_INTERVAL": "scan_interval",
              "C611": "DTA117C611", "D611": "DTA117D611", "F611": "DTA117F611", "_LOGGER": logging.getLogger(__name__),
              "dr": SimpleNamespace(async_get=lambda hass: SimpleNamespace(async_get_or_create=Mock())),
              "_migrate_legacy_sensor_links": lambda *args: None, "update_listener": Mock(),
              "_async_register_services": Mock(), "CONF_ENTRY_TYPE": "entry_type", "ENTRY_TYPE_POWER": "power"}
        execute_nodes(source_nodes(COMPONENT / "__init__.py", {"async_setup_entry"}), ns)
        async def executor(fn, *args):
            return fn(*args)
        hass = SimpleNamespace(data={}, async_add_executor_job=executor, config_entries=SimpleNamespace(async_forward_entry_setups=AsyncMock()))
        entry = SimpleNamespace(data={"host": "example.invalid", "port": 8008, "gw": "DTA117F611", "scan_interval": 5},
                                entry_id="synthetic-entry", title="Example", async_on_unload=Mock(), add_update_listener=Mock())
        self.assertTrue(asyncio.run(ns["async_setup_entry"](hass, entry)))
        config = service.init.call_args.args[3]
        self.assertTrue(config.is_f611)
        self.assertTrue(config.is_kinsei)
        self.assertFalse(config.is_c611)
        self.assertFalse(config.is_d611)


if __name__ == "__main__":
    unittest.main()
