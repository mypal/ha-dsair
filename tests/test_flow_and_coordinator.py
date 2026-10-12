from datetime import datetime
from pathlib import Path
import sys
from typing import Any
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "custom_components" / "ds_air"))

# 构造最小化的 homeassistant mock 环境以支持脱机测试 flow 与 coordinator
ha = types.ModuleType("homeassistant")
ha.__path__ = []
ha_exceptions = types.ModuleType("homeassistant.exceptions")
ha_exceptions.ConfigEntryNotReady = Exception
ha_exceptions.HomeAssistantError = Exception
sys.modules["homeassistant.exceptions"] = ha_exceptions

ha_config_entries = types.ModuleType("homeassistant.config_entries")
ha_const = types.ModuleType("homeassistant.const")
ha_core = types.ModuleType("homeassistant.core")
ha_data_entry_flow = types.ModuleType("homeassistant.data_entry_flow")
ha_helpers = types.ModuleType("homeassistant.helpers")
ha_helpers_event = types.ModuleType("homeassistant.helpers.event")
ha_helpers_update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")
ha_components = types.ModuleType("homeassistant.components")
ha_components_sensor = types.ModuleType("homeassistant.components.sensor")
ha_components_climate = types.ModuleType("homeassistant.components.climate")


class MockConfigFlow:
    def __init_subclass__(cls, domain=None, **kwargs):
        super().__init_subclass__(**kwargs)

    def async_show_menu(self, step_id, menu_options):
        return {"type": "menu", "step_id": step_id, "menu_options": menu_options}

    def async_show_form(self, step_id, data_schema=None, errors=None):
        return {"type": "form", "step_id": step_id, "data_schema": data_schema, "errors": errors or {}}

    def async_create_entry(self, title, data):
        return {"type": "create_entry", "title": title, "data": data}

    async def async_set_unique_id(self, unique_id):
        self._unique_id = unique_id

    def _abort_if_unique_id_configured(self):
        pass


class MockOptionsFlow:
    def __init__(self, *args, **kwargs):
        pass


ha_config_entries.ConfigFlow = MockConfigFlow
ha_config_entries.OptionsFlow = MockOptionsFlow
ha_config_entries.ConfigEntry = MagicMock

class MockPlatform:
    CLIMATE = "climate"
    SENSOR = "sensor"
    FAN = "fan"
    SELECT = "select"
    SWITCH = "switch"
    WATER_HEATER = "water_heater"


ha_const.Platform = MockPlatform
ha_const.CONF_HOST = "host"
ha_const.CONF_PORT = "port"
ha_const.CONF_SCAN_INTERVAL = "scan_interval"
ha_const.CONF_SENSORS = "sensors"
ha_const.ATTR_DEVICE_CLASS = "device_class"
ha_const.ATTR_FRIENDLY_NAME = "friendly_name"
ha_const.UnitOfTemperature = MagicMock()
ha_const.PERCENTAGE = "%"
ha_const.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER = "µg/m³"
ha_const.CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER = "mg/m³"
ha_const.CONCENTRATION_PARTS_PER_MILLION = "ppm"
ha_const.MAJOR_VERSION = 2024
ha_const.UnitOfEnergy = MagicMock(KILO_WATT_HOUR="kWh")


def callback(func):
    return func


ha_core.callback = callback
ha_core.HomeAssistant = MagicMock
ha_core.CALLBACK_TYPE = MagicMock
ha_core.ServiceCall = MagicMock
ha_core.ServiceResponse = MagicMock
ha_core.SupportsResponse = MagicMock(OPTIONAL="optional")
ha_data_entry_flow.FlowResult = dict

ha_helpers_event.async_track_time_change = MagicMock()


class MockDataUpdateCoordinator:
    def __init__(self, hass, logger, name=None, update_interval=None):
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


ha_helpers_update_coordinator.DataUpdateCoordinator = MockDataUpdateCoordinator
ha_helpers_update_coordinator.UpdateFailed = Exception


class MockSensorEntity:
    @property
    def name(self):
        return getattr(self, "_attr_name", None)

    @property
    def unique_id(self):
        return getattr(self, "_attr_unique_id", None)


class MockCoordinatorEntity:
    def __init__(self, coordinator, *args, **kwargs):
        self.coordinator = coordinator

    def __class_getitem__(cls, item):
        return cls

    async def async_added_to_hass(self):
        pass


ha_helpers_update_coordinator.CoordinatorEntity = MockCoordinatorEntity


from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class MockSensorEntityDescription:
    key: str
    name: Any = None
    device_class: Any = None
    native_unit_of_measurement: Any = None
    value_fn: Any = None
    translation_key: Any = None
    suggested_display_precision: Any = None
    options: Any = None


ha_components_sensor.SensorEntity = MockSensorEntity
ha_components_sensor.SensorEntityDescription = MockSensorEntityDescription
ha_components_sensor.SensorDeviceClass = MagicMock(ENERGY="energy")
ha_components_sensor.SensorStateClass = MagicMock(TOTAL="total", TOTAL_INCREASING="total_increasing")
ha_helpers.__path__ = []
ha_helpers_entity = types.ModuleType("homeassistant.helpers.entity")
ha_helpers_entity.DeviceInfo = MagicMock
sys.modules["homeassistant.helpers.entity"] = ha_helpers_entity

ha_helpers_config_validation = types.ModuleType("homeassistant.helpers.config_validation")
ha_helpers_config_validation.positive_int = int
ha_helpers_config_validation.boolean = bool
ha_helpers_config_validation.string = str
ha_helpers_config_validation.config_entry_only_config_schema = lambda domain: None
sys.modules["homeassistant.helpers.config_validation"] = ha_helpers_config_validation

ha_helpers.entity_platform = MagicMock()
ha_helpers.device_registry = MagicMock()
ha_helpers.entity_registry = MagicMock()
ha_helpers.config_validation = ha_helpers_config_validation
sys.modules["homeassistant.helpers.entity_platform"] = ha_helpers.entity_platform
sys.modules["homeassistant.helpers.device_registry"] = ha_helpers.device_registry
sys.modules["homeassistant.helpers.entity_registry"] = ha_helpers.entity_registry

ha_components_climate.FAN_AUTO = "auto"
ha_components_climate.FAN_HIGH = "high"
ha_components_climate.FAN_LOW = "low"
ha_components_climate.FAN_MEDIUM = "medium"
ha_components_climate.HVACAction = MagicMock()
ha_components_climate.HVACMode = MagicMock()

sys.modules["homeassistant"] = ha
sys.modules["homeassistant.config_entries"] = ha_config_entries
sys.modules["homeassistant.const"] = ha_const
sys.modules["homeassistant.core"] = ha_core
sys.modules["homeassistant.data_entry_flow"] = ha_data_entry_flow
sys.modules["homeassistant.helpers"] = ha_helpers
sys.modules["homeassistant.helpers.event"] = ha_helpers_event
sys.modules["homeassistant.helpers.update_coordinator"] = ha_helpers_update_coordinator
sys.modules["homeassistant.components"] = ha_components
sys.modules["homeassistant.components.sensor"] = ha_components_sensor
sys.modules["homeassistant.components.climate"] = ha_components_climate

from custom_components.ds_air import config_flow  # noqa: E402
from custom_components.ds_air import coordinator  # noqa: E402
from custom_components.ds_air import sensor  # noqa: E402
from custom_components.ds_air.const import (  # noqa: E402
    CONF_ENTRY_TYPE,
    CONF_HOME_ID,
    ENTRY_TYPE_GATEWAY,
    ENTRY_TYPE_POWER,
)


class FlowAndCoordinatorTests(unittest.IsolatedAsyncioTestCase):
    async def test_config_flow_first_step_menu(self):
        flow = config_flow.DsAirFlowHandler()
        result = await flow.async_step_user()
        self.assertEqual(result["type"], "menu")
        self.assertEqual(result["step_id"], "user")
        self.assertIn("gateway", result["menu_options"])
        self.assertIn("power", result["menu_options"])

    async def test_config_flow_gateway_flow(self):
        flow = config_flow.DsAirFlowHandler()
        # 选择网关
        result = await flow.async_step_gateway()
        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "gateway")

    async def test_config_flow_power_login_failure(self):
        flow = config_flow.DsAirFlowHandler()
        flow.hass = MagicMock()
        flow.hass.config.path.return_value = "/tmp/ds_air_cert"

        # 模拟登录抛出异常
        flow.hass.async_add_executor_job = AsyncMock(side_effect=Exception("Login failed"))

        result = await flow.async_step_power({"username": "13800000000", "password": "wrong_password"})
        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "power")
        self.assertEqual(result["errors"], {"base": "invalid_auth"})

    async def test_config_flow_power_success_and_home_selection(self):
        flow = config_flow.DsAirFlowHandler()
        flow.hass = MagicMock()
        flow.hass.config.path.return_value = "/tmp/ds_air_cert"

        # 模拟登录成功并返回家庭列表
        flow.hass.async_add_executor_job = AsyncMock(
            side_effect=["test_token_123", [{"homeId": 68293, "homeName": "测试家庭"}]]
        )

        # 提交账号密码
        result = await flow.async_step_power({"username": "13800000000", "password": "correct_password"})
        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "power_home")

        # 提交选中的家庭
        finish_result = await flow.async_step_power_home({"home_id": "68293"})
        self.assertEqual(finish_result["type"], "create_entry")
        self.assertEqual(finish_result["title"], "测试家庭 电量统计")
        self.assertEqual(finish_result["data"][CONF_ENTRY_TYPE], ENTRY_TYPE_POWER)
        self.assertEqual(finish_result["data"][CONF_HOME_ID], 68293)

    def test_coordinator_scheduler_registration(self):
        hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            "username": "13800000000",
            "password": "pwd",
            "home_id": 68293,
            "home_name": "测试家庭",
        }
        hass.config.path.return_value = "/tmp/ds_air_cert"

        coord = coordinator.DsAirPowerCoordinator(hass, entry)
        ha_helpers_event.async_track_time_change.reset_mock()

        coord.start_scheduler()
        # 验证注册了 hour=5, minute=0, second=0
        ha_helpers_event.async_track_time_change.assert_called_once()
        _, kwargs = ha_helpers_event.async_track_time_change.call_args
        self.assertEqual(kwargs["hour"], 5)
        self.assertEqual(kwargs["minute"], 0)
        self.assertEqual(kwargs["second"], 0)

        # 验证停止定时器
        coord.stop_scheduler()

    def test_power_sensor_native_value_and_attributes(self):
        coord = MagicMock()
        coord.home_id = 68293
        coord.home_name = "我的家"
        coord.data = {
            "yesterday_used": 1.25,
            "yesterday_date": "2026-10-11",
            "total": 30.5,
            "price": 0.8,
            "estimated_cost": 24.4,
            "consumptions": [1.0, 1.25],
            "year": 2026,
            "month": 10,
            "home_id": 68293,
            "home_name": "我的家",
            "last_updated": "2026-10-12T05:00:00",
        }
        entry = MagicMock()

        # 1. 昨日用电传感器测试
        y_sensor = sensor.DsAirYesterdayPowerSensor(coord, entry)
        self.assertEqual(y_sensor.name, "昨日用电")
        self.assertEqual(y_sensor.native_value, 1.25)
        self.assertEqual(y_sensor.unique_id, "dsair_power_68293_yesterday")
        y_attrs = y_sensor.extra_state_attributes
        self.assertEqual(y_attrs["yesterday_used"], 1.25)
        self.assertEqual(y_attrs["yesterday_date"], "2026-10-11")

        # 2. 当月累计用电传感器测试
        m_sensor = sensor.DsAirMonthPowerSensor(coord, entry)
        self.assertEqual(m_sensor.name, "当月累计用电")
        self.assertEqual(m_sensor.native_value, 30.5)
        self.assertEqual(m_sensor.unique_id, "dsair_power_68293_month")
        m_attrs = m_sensor.extra_state_attributes
        self.assertEqual(m_attrs["total"], 30.5)
        self.assertEqual(m_attrs["price"], 0.8)
        self.assertEqual(m_attrs["estimated_cost"], 24.4)
        self.assertEqual(m_attrs["daily_consumptions"], [1.0, 1.25])

    async def test_fetch_historical_power(self):
        hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            "username": "13800000000",
            "password": "pwd",
            "home_id": 68293,
            "home_name": "测试家庭",
        }
        mock_client = MagicMock()
        mock_client.get_power_consumption_url.return_value = "https://example.com/h5?nlcId=TEST_NLC_ID"
        mock_client.extract_nlc_id_from_url.return_value = "TEST_NLC_ID"
        mock_client.get_home_power_data.return_value = {
            "code": 0,
            "data": {
                "year": 2026,
                "month": 10,
                "consumptions": [0.84, 0.84, 1.0],
                "total": 2.68,
                "price": 0.8,
                "yesterdayUsed": 1.0,
            },
        }

        coord = coordinator.DsAirPowerCoordinator(hass, entry, client=mock_client)
        result = coord.fetch_historical_power(2026, 10)

        self.assertEqual(result["year"], 2026)
        self.assertEqual(result["month"], 10)
        self.assertEqual(result["total"], 2.68)
        self.assertEqual(result["price"], 0.8)
        self.assertEqual(result["estimated_cost"], 2.14)
        self.assertEqual(len(result["daily_details"]), 3)
        self.assertEqual(result["daily_details"][0]["consumption"], 0.84)
        self.assertEqual(result["daily_details"][0]["date"], "2026-10-01")

    async def test_month_sensor_added_to_hass_binds_statistic_id(self):
        coord = MagicMock()
        coord.home_id = 68293
        coord.data = {"year": 2026, "month": 10, "consumptions": [0.84]}
        entry = MagicMock()
        m_sensor = sensor.DsAirMonthPowerSensor(coord, entry)
        m_sensor.entity_id = "sensor.jin_zhi_kong_qi_dang_yue_lei_ji_yong_dian"
        m_sensor.hass = MagicMock()
        await m_sensor.async_added_to_hass()
        coord.set_month_statistic_id.assert_called_with(
            "sensor.jin_zhi_kong_qi_dang_yue_lei_ji_yong_dian"
        )
        m_sensor.hass.async_create_task.assert_called_once()

    async def test_get_power_data_service(self):
        from custom_components import ds_air

        hass = MagicMock()
        hass.services.has_service.return_value = False
        registered_handlers = {}

        def mock_register(domain, service, handler, schema=None, supports_response=None):
            registered_handlers[f"{domain}.{service}"] = handler

        hass.services.async_register = mock_register

        ds_air._async_register_services(hass)
        self.assertIn("ds_air.get_power_data", registered_handlers)

        handler = registered_handlers["ds_air.get_power_data"]

        mock_coord = MagicMock(spec=coordinator.DsAirPowerCoordinator)
        mock_coord.home_id = 68293
        mock_coord.month_statistic_id = "sensor.jin_zhi_kong_qi_dang_yue_lei_ji_yong_dian"
        mock_coord.fetch_historical_power.return_value = {
            "home_id": 68293,
            "home_name": "测试家庭",
            "year": 2026,
            "month": 10,
            "total": 9.24,
            "price": 0.8,
            "estimated_cost": 7.39,
            "yesterday_used": 0.84,
            "consumptions": [0.84] * 11,
            "daily_details": [{"day": 1, "date": "2026-10-01", "consumption": 0.84}],
        }
        mock_coord.async_import_month_statistics = AsyncMock()

        hass.data = {"ds_air": {"entry_id_1": mock_coord}}
        hass.async_add_executor_job = AsyncMock(
            side_effect=lambda func, *args: func(*args)
        )

        call = MagicMock()
        call.data = {"year": 2026, "month": 10, "home_id": 68293, "import_to_statistics": True}

        response = await handler(call)
        self.assertEqual(response["year"], 2026)
        self.assertEqual(response["month"], 10)
        self.assertEqual(response["total"], 9.24)
        self.assertTrue(response["imported_to_statistics"])
        mock_coord.async_import_month_statistics.assert_called_once()


if __name__ == "__main__":
    unittest.main()

