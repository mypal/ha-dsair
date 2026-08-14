"""Platform for DS-AIR Ventilation and Bathroom Fan of Daikin"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MAJOR_VERSION, MINOR_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .ds_air_service import (
    AirCon,
    AirConStatus,
    EnumControl,
    get_vent_mode_name_small_vam,
    get_vent_mode_name_standard_vam,
    get_vent_mode_enum_small_vam,
    get_vent_mode_enum_standard_vam,
)
from .ds_air_service.dao import Ventilation, VentilationStatus
from .ds_air_service.display import display

_LOGGER = logging.getLogger(__name__)


def _log(s: str):
    s = str(s)
    for i in s.split("\n"):
        _LOGGER.debug(i)


# Fan features
SMALL_VAM_SUPPORT = FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE
STANDARD_VAM_SUPPORT = FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE
BATHROOM_FAN_SUPPORT = FanEntityFeature.SET_SPEED

# For HA Core >= 2024.8, add TURN_ON and TURN_OFF flags
if (MAJOR_VERSION, MINOR_VERSION) >= (2024, 8):
    POWER_SUPPORT = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
    SMALL_VAM_SUPPORT |= POWER_SUPPORT
    STANDARD_VAM_SUPPORT |= POWER_SUPPORT
    BATHROOM_FAN_SUPPORT |= POWER_SUPPORT

# 新风模式名称列表
_MODE_VENT_NAME_LIST_SMALL_VAM = ["内循环", "热交换", "自动", "防污染", "排异味"]
_MODE_VENT_NAME_LIST_STANDARD_VAM = ["旁通", "热交换", "自动"]

# 浴室排风扇风速名称列表（APP 金制空气只有两个挡位：低/高）
BATHROOM_FAN_SPEED_LIST = ["低", "高"]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DS-AIR ventilation and bathroom fan platform."""
    from .ds_air_service import Service

    service: Service = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    for vent in service.get_ventilations():
        entities.append(DsVent(vent, service))
    for aircon in service.get_bathrooms():
        entities.append(BathroomFan(aircon, service))
    async_add_entities(entities)


class DsVent(FanEntity):
    """Representation of a DS-AIR ventilation device."""

    def __init__(self, vent: Ventilation, service):
        """Initialize the ventilation device."""
        _log("create ventilation:")
        _log(vent.__dict__)
        _log(vent.status)
        self._device_name = f"新风 {vent.alias}"
        self._device_info = vent
        self._unique_id = vent.unique_id
        self._service = service
        self._attr_has_entity_name = True
        self._attr_translation_key = "ventilation_switch"

        # Set supported features
        if vent.is_small_vam:
            self._attr_supported_features = SMALL_VAM_SUPPORT
            # Don't include the AUTO mode for speed count
            self._attr_speed_count = len(_MODE_VENT_NAME_LIST_SMALL_VAM) - 1
            self._attr_preset_modes = _MODE_VENT_NAME_LIST_SMALL_VAM
        else:
            self._attr_supported_features = STANDARD_VAM_SUPPORT
            self._attr_speed_count = len(_MODE_VENT_NAME_LIST_STANDARD_VAM) - 1
            self._attr_preset_modes = _MODE_VENT_NAME_LIST_STANDARD_VAM

        service.register_vent_hook(vent, self._status_change_hook)

    def _status_change_hook(self, **kwargs):
        """Handle status change callback."""
        _log("vent hook:")
        if kwargs.get("vent") is not None:
            vent: Ventilation = kwargs["vent"]
            self._device_info = vent
            self._device_name = f"新风 {vent.alias}"
            _log(display(self._device_info))

        if kwargs.get("status") is not None:
            status = self._device_info.status
            new_status: VentilationStatus = kwargs["status"]
            if new_status.switch is not None:
                status.switch = new_status.switch
            if new_status.mode is not None:
                status.mode = new_status.mode
            if new_status.air_flow is not None:
                status.air_flow = new_status.air_flow
            _log("new status")
            _log(display(kwargs["status"]))
            _log("updated status")
            _log(display(self._device_info.status))

        self.schedule_update_ha_state()

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return self._unique_id

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._unique_id)},
            name=self._device_name,
            manufacturer="Daikin Industries, Ltd.",
        )

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        vent = self._device_info
        if vent.status.air_flow is None:
            return None

        if vent.is_small_vam:
            return vent.status.air_flow.value * self.percentage_step
        else:
            if vent.status.air_flow == EnumControl.AirFlow.WEAK:
                return 50
            elif vent.status.air_flow == EnumControl.AirFlow.MIDDLE:
                return 100
            elif vent.status.air_flow == EnumControl.AirFlow.STRONG:
                return 100

        return None

    def set_percentage(self, percentage: int) -> None:
        """Set the fan speed percentage."""
        vent = self._device_info
        new_status = VentilationStatus()

        if vent.is_small_vam:
            air_flow = EnumControl.AirFlow(round(percentage / self.percentage_step))
        else:
            if percentage > 66:
                air_flow = EnumControl.AirFlow.STRONG
            elif percentage > 33:
                air_flow = EnumControl.AirFlow.MIDDLE
            elif percentage > 0:
                air_flow = EnumControl.AirFlow.WEAK
            else:
                air_flow = vent.status.air_flow

            if (
                percentage > 0
                and vent.status.switch != EnumControl.Switch.ON
            ):
                new_status.switch = EnumControl.Switch.ON

        vent.status.air_flow = air_flow
        if air_flow != EnumControl.AirFlow.SUPER_WEAK:
            new_status.air_flow = air_flow
            self._service.control_vent(self._device_info, new_status)
            self.schedule_update_ha_state()

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""
        vent = self._device_info
        new_status = VentilationStatus()
        if vent.is_small_vam:
            mode = get_vent_mode_enum_small_vam(preset_mode)
        else:
            mode = get_vent_mode_enum_standard_vam(preset_mode)
        vent.status.mode = mode
        new_status.mode = mode
        self._service.control_vent(self._device_info, new_status)

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        if self._device_info.status.mode is None:
            return None
        elif self._device_info.is_small_vam:
            return get_vent_mode_name_small_vam(self._device_info.status.mode)
        else:
            return get_vent_mode_name_standard_vam(self._device_info.status.mode)

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        if self._device_info.status.switch is None:
            return None
        return self._device_info.status.switch == EnumControl.Switch.ON

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on the fan."""
        vent = self._device_info
        new_status = VentilationStatus()
        new_status.switch = EnumControl.Switch.ON
        self._service.control_vent(self._device_info, new_status)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        vent = self._device_info
        new_status = VentilationStatus()
        new_status.switch = EnumControl.Switch.OFF
        self._service.control_vent(self._device_info, new_status)


class BathroomFan(FanEntity):
    """Representation of a DS-AIR bathroom exhaust fan."""

    _attr_has_entity_name: bool = True
    _attr_should_poll: bool = False
    _attr_translation_key = "bathroom_fan"

    def __init__(self, aircon: AirCon, service):
        """Initialize the bathroom fan."""
        _log("create bathroom fan:")
        _log(str(aircon.__dict__))
        self._device_info = aircon
        self._unique_id = f"{aircon.unique_id}_exhaust_fan"
        self._service = service
        self._attr_name = f"换气 {aircon.alias}"
        self._attr_supported_features = BATHROOM_FAN_SUPPORT
        self._attr_speed_count = 2  # 两个挡位：低/高

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, aircon.unique_id)},
            name=f"{aircon.alias} 空调",
            manufacturer="Daikin Industries, Ltd.",
        )

        service.register_status_hook(aircon, self._status_change_hook)

    def _status_change_hook(self, **kwargs):
        """Handle status change callback."""
        _log("bathroom fan hook:")
        if kwargs.get("aircon") is not None:
            aircon: AirCon = kwargs["aircon"]
            aircon.status = self._device_info.status
            self._device_info = aircon

        if kwargs.get("status") is not None:
            status = self._device_info.status
            new_status: AirConStatus = kwargs["status"]
            if new_status.switch is not None:
                status.switch = new_status.switch
            if new_status.air_flow is not None:
                status.air_flow = new_status.air_flow
            if new_status.mode is not None:
                status.mode = new_status.mode
            if new_status.breathe is not None:
                status.breathe = new_status.breathe

        self.schedule_update_ha_state()

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return self._unique_id

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        if self._device_info.status.breathe is None:
            return None
        return self._device_info.status.breathe != EnumControl.Breathe.CLOSE

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self._device_info.status.breathe is None:
            return None
        breathe = self._device_info.status.breathe
        if breathe == EnumControl.Breathe.WEAK:
            return 50  # 低
        elif breathe == EnumControl.Breathe.STRONG:
            return 100  # 高
        return None

    def set_percentage(self, percentage: int) -> None:
        """Set the fan speed percentage."""
        aircon = self._device_info
        new_status = AirConStatus()

        # 两个挡位：低 (50%) = WEAK, 高 (100%) = STRONG
        if percentage > 50:
            breathe = EnumControl.Breathe.STRONG
        elif percentage > 0:
            breathe = EnumControl.Breathe.WEAK
        else:
            breathe = aircon.status.breathe

        aircon.status.breathe = breathe
        new_status.breathe = breathe
        self._service.control(aircon, new_status)
        self.schedule_update_ha_state()

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on the fan."""
        aircon = self._device_info
        new_status = AirConStatus()
        
        # 使用传入的 percentage 参数，默认低速
        percentage = kwargs.get("percentage")
        if percentage is None:
            percentage = 50
        if percentage > 50:
            breathe = EnumControl.Breathe.STRONG
        else:
            breathe = EnumControl.Breathe.WEAK
        
        new_status.breathe = breathe
        aircon.status.breathe = breathe
        self._service.control(aircon, new_status)
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        aircon = self._device_info
        new_status = AirConStatus()
        new_status.breathe = EnumControl.Breathe.CLOSE
        aircon.status.breathe = EnumControl.Breathe.CLOSE
        self._service.control(aircon, new_status)
        self.schedule_update_ha_state()
