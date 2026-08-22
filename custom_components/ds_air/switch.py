"""Daikin platform that offers HD (Heat Exchanger) devices as switches.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/switch/
"""

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER
from .ds_air_service import AirCon, HD, Service, EnumControl

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the HD switch entities."""
    service: Service = hass.data[DOMAIN][entry.entry_id]
    hds = service.get_hds()
    switches = []
    for hd in hds:
        switches.append(DsHdMuteSwitch(service, hd))

    # Mesh RA AC swing switches (vertical / horizontal)
    for aircon in service.get_aircons():
        if getattr(aircon, "is_mesh", False):
            switches.append(DsMeshSwingSwitch(service, aircon, "vertical"))
            switches.append(DsMeshSwingSwitch(service, aircon, "horizontal"))

    if switches:
        async_add_entities(switches)


class DsHdMuteSwitch(SwitchEntity):
    """Representation of a Daikin HD mute switch."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, service: Service, hd: HD):
        """Initialize the mute switch."""
        self.service = service
        self._device_info = hd
        self._attr_unique_id = f"{hd.unique_id}_mute"
        self._attr_name = "静音模式"

        service.register_hd_hook(hd, self._status_change_hook)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, hd.unique_id)},
            name=hd.alias if "水热交换器" in hd.alias else f"{hd.alias} 水热交换器",
            manufacturer=MANUFACTURER,
        )

    def _status_change_hook(self, **kwargs) -> None:
        """Handle status updates from service layer."""
        if kwargs.get("status") is not None:
            newstatus = kwargs['status']
            if newstatus.mute is not None:
                self._device_info.status.mute = newstatus.mute
                self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        if self._device_info.status.mute is None:
            return None
        return self._device_info.status.mute == EnumControl.Switch.ON

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        from .ds_air_service import HDStatus
        new_status = HDStatus()
        new_status.mute = EnumControl.Switch.ON
        self._device_info.status.mute = EnumControl.Switch.ON
        self.service.hd_control(self._device_info, new_status)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        from .ds_air_service import HDStatus
        new_status = HDStatus()
        new_status.mute = EnumControl.Switch.OFF
        self._device_info.status.mute = EnumControl.Switch.OFF
        self.service.hd_control(self._device_info, new_status)
        self.async_write_ha_state()


class DsMeshSwingSwitch(SwitchEntity):
    """Representation of a Daikin Mesh RA swing switch (vertical/horizontal).

    The official app exposes two independent swing switches:
      - direction1 (vertical swing)
      - direction2 (horizontal swing)
    Each is a boolean (0=off, 1=swing on).
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, service: Service, aircon: AirCon, axis: str):
        """Initialize the swing switch."""
        self.service = service
        self._device_info = aircon
        self._axis = axis
        if axis == "vertical":
            self._attr_unique_id = f"{aircon.unique_id}_swing_v"
            self._attr_name = "垂直摆动"
        else:
            self._attr_unique_id = f"{aircon.unique_id}_swing_h"
            self._attr_name = "水平摆动"

        service.register_status_hook(aircon, self._status_change_hook)

        from .ds_air_service.dao import build_aircon_device_name

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, aircon.unique_id)},
            name=build_aircon_device_name(aircon.alias),
            manufacturer=MANUFACTURER,
            via_device=(DOMAIN, aircon.gateway_id),
        )

    def _status_change_hook(self, **kwargs) -> None:
        """Handle status updates from service layer."""
        status = kwargs.get("status")
        if status is not None:
            self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)

    def _axis_value(self):
        status = self._device_info.status
        if self._axis == "vertical":
            return getattr(status, "fan_direction1", None)
        return getattr(status, "fan_direction2", None)

    @property
    def is_on(self) -> bool | None:
        """Return true if the swing is on."""
        val = self._axis_value()
        if val is None:
            return None
        v = val.value if hasattr(val, "value") else int(val)
        return v in (7,) or v > 0

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the swing on."""
        from .ds_air_service import AirConStatus
        new_status = AirConStatus()
        swing = EnumControl.FanDirection.SWING
        if self._axis == "vertical":
            self._device_info.status.fan_direction1 = swing
            new_status.fan_direction1 = swing
        else:
            self._device_info.status.fan_direction2 = swing
            new_status.fan_direction2 = swing
        self.service.control(self._device_info, new_status)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the swing off."""
        from .ds_air_service import AirConStatus
        new_status = AirConStatus()
        invalid = EnumControl.FanDirection.INVALID
        if self._axis == "vertical":
            self._device_info.status.fan_direction1 = invalid
            new_status.fan_direction1 = invalid
        else:
            self._device_info.status.fan_direction2 = invalid
            new_status.fan_direction2 = invalid
        self.service.control(self._device_info, new_status)
        self.async_write_ha_state()
