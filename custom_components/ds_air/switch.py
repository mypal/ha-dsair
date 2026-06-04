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
from .ds_air_service import HD, Service, EnumControl

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
