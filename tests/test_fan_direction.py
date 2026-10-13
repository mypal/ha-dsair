from pathlib import Path
import select  # noqa: F401 — preload stdlib select before ds_air/select.py
import sys
import types
from typing import Any
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "custom_components" / "ds_air"))

try:
    import voluptuous as vol
except ImportError:
    vol = types.ModuleType("voluptuous")
    vol.Schema = lambda s: s
    vol.Required = lambda k, default=None: k
    vol.Optional = lambda k, default=None: k
    vol.In = lambda items: items
    vol.All = lambda *args: None
    vol.Range = lambda **kwargs: None
    sys.modules["voluptuous"] = vol

# 最小化 homeassistant mock
ha = types.ModuleType("homeassistant")
ha.__path__ = []
sys.modules.setdefault("homeassistant", ha)

ha_exceptions = types.ModuleType("homeassistant.exceptions")
ha_exceptions.ConfigEntryNotReady = Exception
ha_exceptions.HomeAssistantError = Exception
sys.modules["homeassistant.exceptions"] = ha_exceptions

ha_config_entries = types.ModuleType("homeassistant.config_entries")
ha_config_entries.ConfigEntry = types.SimpleNamespace
sys.modules["homeassistant.config_entries"] = ha_config_entries

ha_core = types.ModuleType("homeassistant.core")
ha_core.HomeAssistant = types.SimpleNamespace
ha_core.callback = lambda f: f
ha_core.CALLBACK_TYPE = Any
ha_core.ServiceCall = types.SimpleNamespace
ha_core.ServiceResponse = types.SimpleNamespace
ha_core.SupportsResponse = types.SimpleNamespace(OPTIONAL=1)
sys.modules["homeassistant.core"] = ha_core

ha_helpers = types.ModuleType("homeassistant.helpers")
ha_helpers.__path__ = []
ha_helpers.typing = types.SimpleNamespace(ConfigType=dict)
ha_helpers.entity_platform = types.SimpleNamespace(AddEntitiesCallback=types.SimpleNamespace)
ha_helpers.device_registry = types.SimpleNamespace(
    async_get=lambda hass: types.SimpleNamespace(),
    DeviceEntry=types.SimpleNamespace,
)
ha_helpers.entity_registry = types.SimpleNamespace(async_get=lambda hass: types.SimpleNamespace())
sys.modules["homeassistant.helpers"] = ha_helpers
sys.modules["homeassistant.helpers.typing"] = ha_helpers.typing
sys.modules["homeassistant.helpers.entity_platform"] = ha_helpers.entity_platform
sys.modules["homeassistant.helpers.device_registry"] = ha_helpers.device_registry
sys.modules["homeassistant.helpers.entity_registry"] = ha_helpers.entity_registry

ha_helpers_cv = types.ModuleType("homeassistant.helpers.config_validation")
ha_helpers_cv.config_entry_only_config_schema = lambda domain: lambda s: s
ha_helpers_cv.positive_int = int
ha_helpers_cv.boolean = bool
ha_helpers_cv.string = str
ha_helpers_cv.port = int
sys.modules["homeassistant.helpers.config_validation"] = ha_helpers_cv

from unittest.mock import MagicMock

ha_helpers_event = sys.modules.get("homeassistant.helpers.event")
if ha_helpers_event is None:
    ha_helpers_event = types.ModuleType("homeassistant.helpers.event")
    sys.modules["homeassistant.helpers.event"] = ha_helpers_event
if not hasattr(ha_helpers_event, "async_track_time_change"):
    ha_helpers_event.async_track_time_change = MagicMock()

class MockDataUpdateCoordinator:
    def __init__(self, hass=None, logger=None, name=None, update_interval=None, *args, **kwargs):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.data = None

    def __class_getitem__(cls, item):
        return cls

    async def async_request_refresh(self):
        pass

    async def async_config_entry_first_refresh(self):
        pass

class MockCoordinatorEntity:
    def __init__(self, coordinator=None, *args, **kwargs):
        self.coordinator = coordinator

    def __class_getitem__(cls, item):
        return cls

ha_helpers_update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")
ha_helpers_update_coordinator.DataUpdateCoordinator = MockDataUpdateCoordinator
ha_helpers_update_coordinator.CoordinatorEntity = MockCoordinatorEntity
ha_helpers_update_coordinator.UpdateFailed = Exception
sys.modules["homeassistant.helpers.update_coordinator"] = ha_helpers_update_coordinator

class MockUnitOfTemperature:
    CELSIUS = "°C"
    FAHRENHEIT = "°F"

ha_const = types.ModuleType("homeassistant.const")
ha_const.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER = "µg/m³"
ha_const.PERCENTAGE = "%"
ha_const.UnitOfTemperature = MockUnitOfTemperature
ha_const.ATTR_TEMPERATURE = "temperature"
ha_const.PRECISION_TENTHS = 0.1
ha_const.CONF_HOST = "host"
ha_const.CONF_PORT = "port"
ha_const.CONF_SCAN_INTERVAL = "scan_interval"
ha_const.Platform = types.SimpleNamespace(CLIMATE="climate", SENSOR="sensor", FAN="fan", SELECT="select", SWITCH="switch", WATER_HEATER="water_heater")
ha_const.MAJOR_VERSION = 2026
ha_const.MINOR_VERSION = 10
ha_const.UnitOfDensity = types.SimpleNamespace(
    MICROGRAMS_PER_CUBIC_METER="µg/m³", MILLIGRAMS_PER_CUBIC_METER="mg/m³"
)
ha_const.UnitOfRatio = types.SimpleNamespace(PERCENTAGE="%", PARTS_PER_MILLION="ppm")
sys.modules["homeassistant.const"] = ha_const

from dataclasses import dataclass

@dataclass(frozen=True, kw_only=True)
class MockSensorEntityDescription:
    key: str = ""
    name: Any = None
    native_unit_of_measurement: Any = None
    device_class: Any = None
    translation_key: Any = None
    icon: Any = None
    state_class: Any = None
    has_entity_name: bool = True
    suggested_display_precision: Any = None
    options: Any = None

class MockSensorStateClass:
    TOTAL_INCREASING = "total_increasing"
    MEASUREMENT = "measurement"

ha_sensor = types.ModuleType("homeassistant.components.sensor")
ha_sensor.SensorDeviceClass = types.SimpleNamespace(
    TEMPERATURE="temperature",
    HUMIDITY="humidity",
    PM25="pm25",
    VOLATILE_ORGANIC_COMPOUNDS="voc",
    VOLATILE_ORGANIC_COMPOUNDS_PARTS="voc",
    CO2="co2",
    ENUM="enum",
)
ha_sensor.SensorEntityDescription = MockSensorEntityDescription
ha_sensor.SensorStateClass = MockSensorStateClass
sys.modules["homeassistant.components.sensor"] = ha_sensor

class MockHVACAction:
    COOLING = "cooling"
    DRYING = "drying"
    FAN = "fan"
    HEATING = "heating"
    OFF = "off"
    PREHEATING = "preheating"

class MockHVACMode:
    COOL = "cool"
    DRY = "dry"
    FAN_ONLY = "fan_only"
    AUTO = "auto"
    HEAT = "heat"
    OFF = "off"

ha_climate = types.ModuleType("homeassistant.components.climate")
ha_climate.FAN_AUTO = "auto"
ha_climate.FAN_HIGH = "high"
ha_climate.FAN_LOW = "low"
ha_climate.FAN_MEDIUM = "medium"
ha_climate.PLATFORM_SCHEMA = types.SimpleNamespace(extend=lambda *args, **kwargs: None)
ha_climate.PRESET_COMFORT = "comfort"
ha_climate.PRESET_NONE = "none"
ha_climate.PRESET_SLEEP = "sleep"
ha_climate.HVACAction = MockHVACAction
ha_climate.HVACMode = MockHVACMode

class MockClimateEntity:
    def __init__(self):
        pass
    @property
    def unique_id(self):
        return getattr(self, "_attr_unique_id", None)
    def schedule_update_ha_state(self):
        pass

ha_climate.ClimateEntity = MockClimateEntity
ha_climate.ClimateEntityFeature = types.SimpleNamespace(
    TARGET_TEMPERATURE=1,
    SWING_MODE=32,
    SWING_HORIZONTAL_MODE=512,
    TARGET_HUMIDITY=2,
    FAN_MODE=8,
    PRESET_MODE=16,
    TURN_ON=128,
    TURN_OFF=256,
)
sys.modules["homeassistant.components.climate"] = ha_climate

ha_core.Event = types.SimpleNamespace
ha_helpers.entity = types.ModuleType("homeassistant.helpers.entity")
ha_helpers.entity.DeviceInfo = dict
sys.modules["homeassistant.helpers.entity"] = ha_helpers.entity
ha_helpers_event.async_track_state_change_event = lambda *args, **kwargs: None

from custom_components.ds_air.const import (  # noqa: E402
    FAN_DIRECTION_LIST,
    FAN_DIRECTION_HOR_LIST,
    get_fan_direction_name,
    get_fan_direction_enum,
    get_fan_direction_hor_name,
    get_fan_direction_hor_enum,
)
from custom_components.ds_air.ds_air_service.ctrl_enum import EnumControl  # noqa: E402


class FanDirectionConstantTests(unittest.TestCase):
    def test_vertical_fan_direction_list_emojis(self):
        """垂直风向：从最高仰角到垂直向下，再到自动与摆动"""
        expected = [None, "⬆️", "↗️", "➡️", "↘️", "⬇️", "🅰️", "↕️"]
        self.assertEqual(FAN_DIRECTION_LIST, expected)

    def test_horizontal_fan_direction_list_emojis(self):
        """水平风向：从最左到最右，再到自动与左右摆动"""
        expected = [None, "⬅️", "↖️", "⬆️", "↗️", "➡️", "🅰️", "↔️"]
        self.assertEqual(FAN_DIRECTION_HOR_LIST, expected)

    def test_get_fan_direction_name_vertical(self):
        self.assertIsNone(get_fan_direction_name(None))
        self.assertIsNone(get_fan_direction_name(EnumControl.FanDirection.INVALID))
        self.assertEqual(get_fan_direction_name(EnumControl.FanDirection.P0), "⬆️")
        self.assertEqual(get_fan_direction_name(EnumControl.FanDirection.P1), "↗️")
        self.assertEqual(get_fan_direction_name(EnumControl.FanDirection.P2), "➡️")
        self.assertEqual(get_fan_direction_name(EnumControl.FanDirection.P3), "↘️")
        self.assertEqual(get_fan_direction_name(EnumControl.FanDirection.P4), "⬇️")
        self.assertEqual(get_fan_direction_name(EnumControl.FanDirection.AUTO), "🅰️")
        self.assertEqual(get_fan_direction_name(EnumControl.FanDirection.SWING), "↕️")

    def test_get_fan_direction_enum_vertical(self):
        self.assertEqual(get_fan_direction_enum("⬆️"), EnumControl.FanDirection.P0)
        self.assertEqual(get_fan_direction_enum("↗️"), EnumControl.FanDirection.P1)
        self.assertEqual(get_fan_direction_enum("➡️"), EnumControl.FanDirection.P2)
        self.assertEqual(get_fan_direction_enum("↘️"), EnumControl.FanDirection.P3)
        self.assertEqual(get_fan_direction_enum("⬇️"), EnumControl.FanDirection.P4)
        self.assertEqual(get_fan_direction_enum("🅰️"), EnumControl.FanDirection.AUTO)
        self.assertEqual(get_fan_direction_enum("↕️"), EnumControl.FanDirection.SWING)

        # 兼容性测试
        self.assertEqual(get_fan_direction_enum("自动"), EnumControl.FanDirection.AUTO)
        self.assertEqual(get_fan_direction_enum("AUTO"), EnumControl.FanDirection.AUTO)
        self.assertEqual(get_fan_direction_enum("摆动"), EnumControl.FanDirection.SWING)
        self.assertEqual(get_fan_direction_enum("上下摆动"), EnumControl.FanDirection.SWING)
        self.assertEqual(get_fan_direction_enum("🔄"), EnumControl.FanDirection.SWING)
        self.assertEqual(get_fan_direction_enum("↔️"), EnumControl.FanDirection.AUTO)

    def test_get_fan_direction_hor_name(self):
        self.assertIsNone(get_fan_direction_hor_name(None))
        self.assertIsNone(get_fan_direction_hor_name(EnumControl.FanDirection.INVALID))
        self.assertEqual(get_fan_direction_hor_name(EnumControl.FanDirection.P0), "⬅️")
        self.assertEqual(get_fan_direction_hor_name(EnumControl.FanDirection.P1), "↖️")
        self.assertEqual(get_fan_direction_hor_name(EnumControl.FanDirection.P2), "⬆️")
        self.assertEqual(get_fan_direction_hor_name(EnumControl.FanDirection.P3), "↗️")
        self.assertEqual(get_fan_direction_hor_name(EnumControl.FanDirection.P4), "➡️")
        self.assertEqual(get_fan_direction_hor_name(EnumControl.FanDirection.AUTO), "🅰️")
        self.assertEqual(get_fan_direction_hor_name(EnumControl.FanDirection.SWING), "↔️")

    def test_get_fan_direction_hor_enum(self):
        self.assertEqual(get_fan_direction_hor_enum("⬅️"), EnumControl.FanDirection.P0)
        self.assertEqual(get_fan_direction_hor_enum("↖️"), EnumControl.FanDirection.P1)
        self.assertEqual(get_fan_direction_hor_enum("⬆️"), EnumControl.FanDirection.P2)
        self.assertEqual(get_fan_direction_hor_enum("↗️"), EnumControl.FanDirection.P3)
        self.assertEqual(get_fan_direction_hor_enum("➡️"), EnumControl.FanDirection.P4)
        self.assertEqual(get_fan_direction_hor_enum("🅰️"), EnumControl.FanDirection.AUTO)
        self.assertEqual(get_fan_direction_hor_enum("↔️"), EnumControl.FanDirection.SWING)

        # 兼容性测试
        self.assertEqual(get_fan_direction_hor_enum("自动"), EnumControl.FanDirection.AUTO)
        self.assertEqual(get_fan_direction_hor_enum("左右摆动"), EnumControl.FanDirection.SWING)
        self.assertEqual(get_fan_direction_hor_enum("SWING"), EnumControl.FanDirection.SWING)


from custom_components.ds_air.ds_air_service.config import Config  # noqa: E402
from custom_components.ds_air.ds_air_service.ctrl_enum import (  # noqa: E402
    EnumDevice,
    EnumFanDirection,
    EnumFanVolume,
)
from custom_components.ds_air.ds_air_service.dao import AirCon, AirConStatus  # noqa: E402
from custom_components.ds_air.ds_air_service.param import (  # noqa: E402
    AirConControlParam,
    AirConQueryStatusParam,
    Encode,
)


class FanDirectionParamTests(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.config.is_new_version = True

    def test_control_param_with_only_direction1(self):
        """测试仅设置垂直风向：水平风向为 None 时不能抛 TypeError 崩溃，并应继承现有状态"""
        aircon = AirCon(self.config)
        aircon.room_id = 1
        aircon.unit_id = 2
        aircon.status.fan_direction1 = EnumControl.FanDirection.P1  # 2
        aircon.status.fan_direction2 = EnumControl.FanDirection.P2  # 3

        new_status = AirConStatus()
        new_status.fan_direction1 = EnumControl.FanDirection.P0  # 1
        new_status.fan_direction2 = None  # 未修改水平风向

        param = AirConControlParam(aircon, new_status)
        encoder = Encode()
        param.generate_subbody(encoder, self.config)
        data = encoder.pack(False)

        # 报文结构: room_id(1B) + unit_id(1B) + flag(1B) + li payload
        flag = data[2]
        self.assertTrue(flag & EnumControl.Type.FAN_DIRECTION)
        # 负载第4字节 (index 3) 为风向控制字节:
        # 低4位 = direction1 (1), 高4位 = direction2 (3) -> 0x31 (49)
        val = data[3]
        self.assertEqual(val & 0x0F, 1)
        self.assertEqual((val >> 4) & 0x0F, 3)

    def test_control_param_with_only_direction2(self):
        """测试仅设置水平风向：垂直风向为 None 时仍能正确生成 FAN_DIRECTION 标志，并继承垂直风向"""
        aircon = AirCon(self.config)
        aircon.room_id = 1
        aircon.unit_id = 2
        aircon.status.fan_direction1 = EnumControl.FanDirection.P4  # 5
        aircon.status.fan_direction2 = EnumControl.FanDirection.P1  # 2

        new_status = AirConStatus()
        new_status.fan_direction1 = None  # 未修改垂直风向
        new_status.fan_direction2 = EnumControl.FanDirection.SWING  # 7

        param = AirConControlParam(aircon, new_status)
        encoder = Encode()
        param.generate_subbody(encoder, self.config)
        data = encoder.pack(False)

        flag = data[2]
        self.assertTrue(flag & EnumControl.Type.FAN_DIRECTION)
        # 低4位 = direction1 (5), 高4位 = direction2 (7) -> 0x75 (117)
        val = data[3]
        self.assertEqual(val & 0x0F, 5)
        self.assertEqual((val >> 4) & 0x0F, 7)

    def test_control_param_with_both_directions(self):
        """测试同时设置垂直与水平风向"""
        aircon = AirCon(self.config)
        aircon.room_id = 1
        aircon.unit_id = 2
        aircon.status.fan_direction1 = EnumControl.FanDirection.P1
        aircon.status.fan_direction2 = EnumControl.FanDirection.P1

        new_status = AirConStatus()
        new_status.fan_direction1 = EnumControl.FanDirection.AUTO  # 6
        new_status.fan_direction2 = EnumControl.FanDirection.SWING  # 7

        param = AirConControlParam(aircon, new_status)
        encoder = Encode()
        param.generate_subbody(encoder, self.config)
        data = encoder.pack(False)

        flag = data[2]
        self.assertTrue(flag & EnumControl.Type.FAN_DIRECTION)
        val = data[3]
        self.assertEqual(val & 0x0F, 6)
        self.assertEqual((val >> 4) & 0x0F, 7)

    def test_status_param_fan_direction_query_condition(self):
        """查询状态参数：任一风向支持（不为 FIX）即应查询 FAN_DIRECTION"""
        aircon = AirCon(self.config)
        aircon.room_id = 1
        aircon.unit_id = 2
        aircon.fan_volume = EnumFanVolume.STEP_3

        # 1. 仅垂直支持
        aircon.fan_direction1 = EnumFanDirection.STEP_5
        aircon.fan_direction2 = EnumFanDirection.FIX
        param1 = AirConQueryStatusParam()
        param1.device = aircon
        enc1 = Encode()
        param1.generate_subbody(enc1, self.config)
        flag1 = enc1.pack(False)[2]
        self.assertTrue(flag1 & EnumControl.Type.FAN_DIRECTION)

        # 2. 仅水平支持
        aircon.fan_direction1 = EnumFanDirection.FIX
        aircon.fan_direction2 = EnumFanDirection.STEP_5
        param2 = AirConQueryStatusParam()
        param2.device = aircon
        enc2 = Encode()
        param2.generate_subbody(enc2, self.config)
        flag2 = enc2.pack(False)[2]
        self.assertTrue(flag2 & EnumControl.Type.FAN_DIRECTION)

        # 3. 均不支持 (FIX)
        aircon.fan_direction1 = EnumFanDirection.FIX
        aircon.fan_direction2 = EnumFanDirection.FIX
        param3 = AirConQueryStatusParam()
        param3.device = aircon
        enc3 = Encode()
        param3.generate_subbody(enc3, self.config)
        flag3 = enc3.pack(False)[2]
        self.assertFalse(flag3 & EnumControl.Type.FAN_DIRECTION)


from custom_components.ds_air.climate import DsAir  # noqa: E402


class MockClimateService:
    def __init__(self):
        self.last_control = None

    def register_status_hook(self, aircon, hook):
        pass

    def control(self, aircon, new_status):
        self.last_control = new_status


class FanDirectionClimateTests(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.config.is_new_version = True
        self.service = MockClimateService()
        self.aircon = AirCon(self.config)
        self.aircon.room_id = 1
        self.aircon.unit_id = 2
        self.aircon.alias = "Test Room"
        self.aircon.gateway_id = "gw_1"
        self.aircon.status.switch = EnumControl.Switch.ON

    def test_swing_mode_reads_fan_direction1(self):
        """swing_mode 必须读取垂直风向 (fan_direction1) 并返回垂直 Emoji"""
        self.aircon.status.fan_direction1 = EnumControl.FanDirection.P1  # 2 -> ↗️
        self.aircon.status.fan_direction2 = EnumControl.FanDirection.P4  # 5 -> ➡️
        climate = DsAir(self.service, self.aircon)

        self.assertEqual(climate.swing_mode, "↗️")

    def test_set_swing_mode_modifies_fan_direction1_and_preserves_fan_direction2(self):
        """set_swing_mode 必须修改 fan_direction1，且保留原有的水平风向 fan_direction2"""
        self.aircon.status.fan_direction1 = EnumControl.FanDirection.P0  # 1 -> ⬆️
        self.aircon.status.fan_direction2 = EnumControl.FanDirection.P3  # 4 -> 偏右
        climate = DsAir(self.service, self.aircon)

        climate.set_swing_mode("⬇️")  # P4 (5)

        sent = self.service.last_control
        self.assertIsNotNone(sent)
        self.assertEqual(sent.fan_direction1, EnumControl.FanDirection.P4)
        # 必须保留原有水平风向 P3，不能被写成新模式或清空！
        self.assertEqual(sent.fan_direction2, EnumControl.FanDirection.P3)

    def test_swing_horizontal_mode_reads_fan_direction2(self):
        """swing_horizontal_mode 必须读取水平风向 (fan_direction2) 并返回水平 Emoji"""
        self.aircon.status.fan_direction1 = EnumControl.FanDirection.P0  # 1 -> ⬆️
        self.aircon.status.fan_direction2 = EnumControl.FanDirection.P0  # 1 -> ⬅️ (最左)
        climate = DsAir(self.service, self.aircon)

        self.assertEqual(climate.swing_horizontal_mode, "⬅️")

    def test_set_swing_horizontal_mode_modifies_fan_direction2_and_preserves_fan_direction1(self):
        """set_swing_horizontal_mode 必须修改 fan_direction2，且保留原有的垂直风向 fan_direction1"""
        self.aircon.status.fan_direction1 = EnumControl.FanDirection.P2  # 3 -> ➡️ (居中)
        self.aircon.status.fan_direction2 = EnumControl.FanDirection.P1  # 2 -> ↖️
        climate = DsAir(self.service, self.aircon)

        climate.set_swing_horizontal_mode("↔️")  # SWING (7)

        sent = self.service.last_control
        self.assertIsNotNone(sent)
        self.assertEqual(sent.fan_direction2, EnumControl.FanDirection.SWING)
        # 必须保留原有垂直风向 P2
        self.assertEqual(sent.fan_direction1, EnumControl.FanDirection.P2)

    def test_supported_features_swing_modes(self):
        """supported_features 必须根据设备能力独立置位 SWING_MODE 与 SWING_HORIZONTAL_MODE"""
        # 1. 仅垂直支持
        self.aircon.fan_direction1 = EnumFanDirection.STEP_5
        self.aircon.fan_direction2 = EnumFanDirection.FIX
        climate1 = DsAir(self.service, self.aircon)
        features1 = climate1.supported_features
        self.assertTrue(features1 & ha_climate.ClimateEntityFeature.SWING_MODE)
        self.assertFalse(features1 & ha_climate.ClimateEntityFeature.SWING_HORIZONTAL_MODE)

        # 2. 垂直与水平均支持
        self.aircon.fan_direction1 = EnumFanDirection.STEP_5
        self.aircon.fan_direction2 = EnumFanDirection.STEP_5
        climate2 = DsAir(self.service, self.aircon)
        features2 = climate2.supported_features
        self.assertTrue(features2 & ha_climate.ClimateEntityFeature.SWING_MODE)
        self.assertTrue(features2 & ha_climate.ClimateEntityFeature.SWING_HORIZONTAL_MODE)


if __name__ == "__main__":
    unittest.main()
