"""Select entities for DS-AIR ventilation devices."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER
from .ds_air_service import (
    EnumControl,
    Service,
    get_vent_mode_enum_small_vam,
    get_vent_mode_enum_standard_vam,
    get_vent_mode_name_small_vam,
    get_vent_mode_name_standard_vam,
)
from .ds_air_service.dao import Ventilation, VentilationStatus

_LOGGER = logging.getLogger(__name__)

_MODE_VENT_NAME_LIST_SMALL_VAM = ["内循环", "热交换", "自动", "防污染", "排异味"]
_MODE_VENT_NAME_LIST_STANDARD_VAM = ["旁通", "热交换", "自动"]
_VENT_AIR_FLOW_OPTIONS_SMALL_VAM = ["静音", "中速", "高速", "暴风"]
_VENT_AIR_FLOW_OPTIONS_STANDARD_VAM = ["静音", "中速", "高速"]
_VENT_AIR_FLOW_BY_OPTION = {
    "静音": EnumControl.AirFlow.WEAK,
    "中速": EnumControl.AirFlow.MIDDLE,
    "高速": EnumControl.AirFlow.STRONG,
    "暴风": EnumControl.AirFlow.SUPER_STRONG,
}
_VENT_AIR_FLOW_BY_ENUM = {
    value: option for option, value in _VENT_AIR_FLOW_BY_OPTION.items()
}


def _log(value) -> None:
    value = str(value)
    for line in value.split("\n"):
        _LOGGER.debug(line)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DS-AIR select entities."""
    service: Service = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    for vent in service.get_ventilations():
        entities.append(DsVentModeSelect(vent, service))
        entities.append(DsVentAirFlowSelect(vent, service))
    async_add_entities(entities)


class DsVentModeSelect(SelectEntity):
    """Ventilation mode selector."""

    _attr_has_entity_name = True
    _attr_translation_key = "ventilation_mode"
    _attr_should_poll = False

    def __init__(self, vent: Ventilation, service: Service) -> None:
        self._device_info = vent
        self._service = service
        self._attr_unique_id = f"mode_{vent.unique_id}"

        if vent.is_small_vam:
            self._attr_options = _MODE_VENT_NAME_LIST_SMALL_VAM
        else:
            self._attr_options = _MODE_VENT_NAME_LIST_STANDARD_VAM

        service.register_vent_hook(vent, self._status_change_hook)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_info.unique_id)},
            name=f"新风 {self._device_info.alias}",
            manufacturer=MANUFACTURER,
            via_device=(DOMAIN, self._device_info.gateway_id),
        )

    @property
    def current_option(self) -> str | None:
        """Return current selected option."""
        mode = self._device_info.status.mode
        if mode is None:
            return None
        if self._device_info.is_small_vam:
            return get_vent_mode_name_small_vam(mode)
        return get_vent_mode_name_standard_vam(mode)

    def select_option(self, option: str) -> None:
        """Select ventilation mode."""
        if self._device_info.is_small_vam:
            mode = get_vent_mode_enum_small_vam(option)
        else:
            mode = get_vent_mode_enum_standard_vam(option)

        self._device_info.status.mode = mode
        self._service.control_vent(
            self._device_info,
            VentilationStatus(mode=mode),
        )
        self.schedule_update_ha_state()

    def _status_change_hook(self, **kwargs) -> None:
        """Handle ventilation status changes."""
        if kwargs.get("vent") is not None:
            self._device_info = kwargs["vent"]

        if kwargs.get("status") is not None:
            new_status: VentilationStatus = kwargs["status"]
            if new_status.mode is not None:
                self._device_info.status.mode = new_status.mode

        _log(f"vent mode select updated: {self.current_option}")
        self.schedule_update_ha_state()


class DsVentAirFlowSelect(SelectEntity):
    """Ventilation air flow selector."""

    _attr_has_entity_name = True
    _attr_translation_key = "ventilation_air_flow"
    _attr_should_poll = False

    def __init__(self, vent: Ventilation, service: Service) -> None:
        self._device_info = vent
        self._service = service
        self._attr_unique_id = f"air_flow_{vent.unique_id}"
        if vent.is_small_vam:
            self._attr_options = _VENT_AIR_FLOW_OPTIONS_SMALL_VAM
        else:
            self._attr_options = _VENT_AIR_FLOW_OPTIONS_STANDARD_VAM

        service.register_vent_hook(vent, self._status_change_hook)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_info.unique_id)},
            name=f"新风 {self._device_info.alias}",
            manufacturer=MANUFACTURER,
            via_device=(DOMAIN, self._device_info.gateway_id),
        )

    @property
    def current_option(self) -> str | None:
        """Return current selected option."""
        air_flow = self._device_info.status.air_flow
        if air_flow is None:
            return None
        return _VENT_AIR_FLOW_BY_ENUM.get(air_flow)

    def select_option(self, option: str) -> None:
        """Select ventilation air flow."""
        air_flow = _VENT_AIR_FLOW_BY_OPTION[option]
        self._device_info.status.air_flow = air_flow
        self._service.control_vent(
            self._device_info,
            VentilationStatus(air_flow=air_flow),
        )
        self.schedule_update_ha_state()

    def _status_change_hook(self, **kwargs) -> None:
        """Handle ventilation status changes."""
        if kwargs.get("vent") is not None:
            self._device_info = kwargs["vent"]

        if kwargs.get("status") is not None:
            new_status: VentilationStatus = kwargs["status"]
            if new_status.air_flow is not None:
                self._device_info.status.air_flow = new_status.air_flow

        _log(f"vent air flow select updated: {self.current_option}")
        self.schedule_update_ha_state()
