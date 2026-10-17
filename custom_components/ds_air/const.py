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

# 条目类型
CONF_ENTRY_TYPE = "entry_type"
ENTRY_TYPE_GATEWAY = "gateway"
ENTRY_TYPE_POWER = "power"

# 电量统计相关常量
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_TOKEN = "token"
CONF_HOME_ID = "home_id"
CONF_HOME_NAME = "home_name"
CONF_CONFIG_TYPE = "config_type"
SERVICE_GET_POWER_DATA = "get_power_data"

# 网关型号常量
B611 = "DTA117B611"
C611 = "DTA117C611"
D611 = "DTA117D611"
F611 = "DTA117F611"
DEFAULT_GW = C611
GW_LIST = [C611, B611, D611, F611]

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


# 垂直风向：从最高仰角到垂直向下，再到自动与摆动
FAN_DIRECTION_LIST = [None, "⬆️", "↗️", "➡️", "↘️", "⬇️", "🅰️", "↕️"]

# 水平风向：从最左到最右，再到自动与左右摆动
FAN_DIRECTION_HOR_LIST = [None, "⬅️", "↖️", "⬆️", "↗️", "➡️", "🅰️", "↔️"]

_FAN_DIRECTION_MAP: dict[str, EnumControl.FanDirection] = {
    "⬆️": EnumControl.FanDirection.P0,
    "↗️": EnumControl.FanDirection.P1,
    "➡️": EnumControl.FanDirection.P2,
    "↘️": EnumControl.FanDirection.P3,
    "⬇️": EnumControl.FanDirection.P4,
    "🅰️": EnumControl.FanDirection.AUTO,
    "↕️": EnumControl.FanDirection.SWING,
    # 兼容历史配置与文本输入
    "自动": EnumControl.FanDirection.AUTO,
    "AUTO": EnumControl.FanDirection.AUTO,
    "auto": EnumControl.FanDirection.AUTO,
    "摆动": EnumControl.FanDirection.SWING,
    "上下摆动": EnumControl.FanDirection.SWING,
    "SWING": EnumControl.FanDirection.SWING,
    "swing": EnumControl.FanDirection.SWING,
    "🔄": EnumControl.FanDirection.SWING,
    "↔️": EnumControl.FanDirection.AUTO,
}

_FAN_DIRECTION_HOR_MAP: dict[str, EnumControl.FanDirection] = {
    "⬅️": EnumControl.FanDirection.P0,
    "↖️": EnumControl.FanDirection.P1,
    "⬆️": EnumControl.FanDirection.P2,
    "↗️": EnumControl.FanDirection.P3,
    "➡️": EnumControl.FanDirection.P4,
    "🅰️": EnumControl.FanDirection.AUTO,
    "↔️": EnumControl.FanDirection.SWING,
    # 兼容历史配置与文本输入
    "自动": EnumControl.FanDirection.AUTO,
    "AUTO": EnumControl.FanDirection.AUTO,
    "auto": EnumControl.FanDirection.AUTO,
    "摆动": EnumControl.FanDirection.SWING,
    "左右摆动": EnumControl.FanDirection.SWING,
    "SWING": EnumControl.FanDirection.SWING,
    "swing": EnumControl.FanDirection.SWING,
    "🔄": EnumControl.FanDirection.SWING,
}


def get_fan_direction_name(idx: EnumControl.FanDirection | None) -> str | None:
    if idx is None or idx == EnumControl.FanDirection.INVALID:
        return None
    try:
        return FAN_DIRECTION_LIST[idx]
    except (IndexError, TypeError):
        return None


def get_fan_direction_enum(name: str) -> EnumControl.FanDirection:
    if name in _FAN_DIRECTION_MAP:
        return _FAN_DIRECTION_MAP[name]
    if name in FAN_DIRECTION_LIST:
        return EnumControl.FanDirection(FAN_DIRECTION_LIST.index(name))
    return EnumControl.FanDirection.INVALID


def get_fan_direction_hor_name(idx: EnumControl.FanDirection | None) -> str | None:
    if idx is None or idx == EnumControl.FanDirection.INVALID:
        return None
    try:
        return FAN_DIRECTION_HOR_LIST[idx]
    except (IndexError, TypeError):
        return None


def get_fan_direction_hor_enum(name: str) -> EnumControl.FanDirection:
    if name in _FAN_DIRECTION_HOR_MAP:
        return _FAN_DIRECTION_HOR_MAP[name]
    if name in FAN_DIRECTION_HOR_LIST:
        return EnumControl.FanDirection(FAN_DIRECTION_HOR_LIST.index(name))
    return EnumControl.FanDirection.INVALID


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
