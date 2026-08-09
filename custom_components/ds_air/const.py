from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.components.sensor import SensorDeviceClass

from .ds_air_service import EnumControl

DOMAIN = "ds_air"
CONF_GW = "gw"
DEFAULT_HOST = "192.168.1."
DEFAULT_PORT = 8008

# 网关型号常量
B611 = "DTA117B611"
C611 = "DTA117C611"
D611 = "DTA117D611"
DEFAULT_GW = C611
GW_LIST = [C611, B611, D611]

CN_GATEWAY_NAME = "金制空气"

MANUFACTURER = "Daikin Industries, Ltd."


def get_default_gateway_name() -> str:
    return CN_GATEWAY_NAME


_MODE_NAME_LIST = [
    HVACMode.COOL,
    HVACMode.DRY,
    HVACMode.FAN_ONLY,
    HVACMode.AUTO,
    HVACMode.HEAT,
    HVACMode.DRY,
    HVACMode.AUTO,
    HVACMode.AUTO,
    HVACMode.HEAT,
    HVACMode.DRY,
]


def get_mode_name(idx: EnumControl.Mode | None) -> HVACMode | None:
    return _MODE_NAME_LIST[idx] if idx is not None else None


_MODE_ACTION_LIST = [
    HVACAction.COOLING,
    HVACAction.DRYING,
    HVACAction.FAN,
    None,
    HVACAction.HEATING,
    HVACAction.DRYING,
    None,
    None,
    HVACAction.PREHEATING,
    HVACAction.DRYING,
]


def get_action_name(idx: EnumControl.Mode | None) -> HVACAction | None:
    return _MODE_ACTION_LIST[idx] if idx is not None else None


AIR_FLOW_NAME_LIST = [FAN_LOW, "稍弱", FAN_MEDIUM, "稍强", FAN_HIGH, FAN_AUTO, "静音"]


def get_air_flow_name(idx: EnumControl.AirFlow | None) -> str | None:
    return AIR_FLOW_NAME_LIST[idx] if idx is not None else None


def get_air_flow_enum(name: str) -> EnumControl.AirFlow:
    return EnumControl.AirFlow(AIR_FLOW_NAME_LIST.index(name))


FAN_DIRECTION_LIST = [None, "➡️", "↘️", "⬇️", "↙️", "⬅️", "↔️", "🔄"]


def get_fan_direction_name(idx: EnumControl.FanDirection | None) -> str | None:
    return FAN_DIRECTION_LIST[idx] if idx is not None else None


def get_fan_direction_enum(name: str) -> EnumControl.FanDirection:
    return EnumControl.FanDirection(FAN_DIRECTION_LIST.index(name))


# 新风传感器类型
SMALL_VAM_SENSOR_TYPES = {
    "in_door_temp": [
        UnitOfTemperature.CELSIUS,
        "indoor_temperature",
        SensorDeviceClass.TEMPERATURE,
        10,
    ],
    "out_door_temp": [
        UnitOfTemperature.CELSIUS,
        "outdoor_temperature",
        SensorDeviceClass.TEMPERATURE,
        10,
    ],
    "out_door_humidity": [
        PERCENTAGE,
        "outdoor_humidity",
        SensorDeviceClass.HUMIDITY,
        1,
    ],
    "pm25": [
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        "outdoor_pm25",
        SensorDeviceClass.PM25,
        1,
    ],
}
