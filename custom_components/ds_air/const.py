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
CN_GATEWAY_NAME = "金制空气"
EN_GATEWAY_NAME = "DS-AIR"
LEGACY_GATEWAY_TITLES = {CN_GATEWAY_NAME, EN_GATEWAY_NAME}

MANUFACTURER = "Daikin Industries, Ltd."


def get_default_gateway_name(language: str | None, host: str) -> str:
    return CN_GATEWAY_NAME


def is_legacy_gateway_title(title: str | None, host: str | None = None) -> bool:
    if title in LEGACY_GATEWAY_TITLES:
        return True
    if host is None:
        return False
    return title in {f"{CN_GATEWAY_NAME} {host}", f"{EN_GATEWAY_NAME} {host}"}


def get_gateway_name(language: str | None, host: str, title: str | None) -> str:
    if title and not is_legacy_gateway_title(title, host):
        return title
    return get_default_gateway_name(language, host)


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


AIR_FLOW_NAME_LIST = [FAN_LOW, "稍弱", FAN_MEDIUM, "稍强", FAN_HIGH, FAN_AUTO]


def get_air_flow_name(idx: EnumControl.AirFlow | None) -> str | None:
    return AIR_FLOW_NAME_LIST[idx] if idx is not None else None


def get_air_flow_enum(name: str) -> EnumControl.AirFlow:
    return EnumControl.AirFlow(AIR_FLOW_NAME_LIST.index(name))


FAN_DIRECTION_LIST = [None, "➡️", "↘️", "⬇️", "↙️", "⬅️", "↔️", "🔄"]


def get_fan_direction_name(idx: EnumControl.FanDirection | None) -> str | None:
    return FAN_DIRECTION_LIST[idx] if idx is not None else None


def get_fan_direction_enum(name: str) -> EnumControl.FanDirection:
    return EnumControl.FanDirection(FAN_DIRECTION_LIST.index(name))
