from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    HVACAction,
    HVACMode,
)

from .ds_air_service import EnumControl


DOMAIN = "ds_air"
CONF_GW = "gw"
DEFAULT_HOST = "192.168.1."
DEFAULT_PORT = 8008
DEFAULT_GW = "DTA117C611"
GW_LIST = ["DTA117C611", "DTA117B611"]

MANUFACTURER = "Daikin Industries, Ltd."


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


def get_mode_name(idx: int) -> HVACMode:
    return _MODE_NAME_LIST[idx]


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


def get_action_name(idx: int) -> HVACAction | None:
    return _MODE_ACTION_LIST[idx]


AIR_FLOW_NAME_LIST = [FAN_LOW, "稍弱", FAN_MEDIUM, "稍强", FAN_HIGH, FAN_AUTO]


def get_air_flow_name(idx: int) -> str:
    return AIR_FLOW_NAME_LIST[idx]


def get_air_flow_enum(name: str) -> EnumControl.AirFlow:
    return EnumControl.AirFlow(AIR_FLOW_NAME_LIST.index(name))


FAN_DIRECTION_LIST = [None, "➡️", "↘️", "⬇️", "↙️", "⬅️", "↔️", "🔄"]


def get_fan_direction_name(idx: int) -> str:
    return FAN_DIRECTION_LIST[idx]


def get_fan_direction_enum(name: str) -> EnumControl.FanDirection:
    return EnumControl.FanDirection(FAN_DIRECTION_LIST.index(name))
