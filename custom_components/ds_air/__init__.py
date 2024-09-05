"""Platform for DS-AIR of Daikin
https://www.daikin-china.com.cn/newha/products/4/19/DS-AIR/
"""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import CONF_GW, DEFAULT_GW, DEFAULT_HOST, DEFAULT_PORT, DOMAIN
from .ds_air_service import Config, Service

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.CLIMATE,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    gw = entry.data[CONF_GW]
    scan_interval = entry.data[CONF_SCAN_INTERVAL]

    _LOGGER.debug(f"{host}:{port} {gw} {scan_interval}")

    config = Config()
    config.is_c611 = gw == DEFAULT_GW

    service = Service()
    hass.data[DOMAIN][entry.entry_id] = service
    await hass.async_add_executor_job(service.init, host, port, scan_interval, config)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    service: Service = hass.data[DOMAIN].pop(entry.entry_id)

    if service.state_change_listener is not None:
        service.state_change_listener()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    service.destroy()

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    # reference: https://developers.home-assistant.io/docs/device_registry_index/#removing-devices
    return True
