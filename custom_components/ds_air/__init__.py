"""
Platform for DS-AIR of Daikin
https://www.daikin-china.com.cn/newha/products/4/19/DS-AIR/
"""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from .hass_inst import GetHass
from .const import CONF_GW, DEFAULT_HOST, DEFAULT_PORT, DEFAULT_GW, DOMAIN
from .ds_air_service.config import Config

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["climate", "sensor"]


def _log(s: str):
    s = str(s)
    for i in s.split("\n"):
        _LOGGER.debug(i)

def setup(hass, config):
    hass.data[DOMAIN] = {}
    GetHass.set_hass(hass)
    return True


async def async_setup_entry(
        hass: HomeAssistant, entry: ConfigEntry
):
    hass.data.setdefault(DOMAIN, {})
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    gw = entry.data[CONF_GW]
    scan_interval = entry.data[CONF_SCAN_INTERVAL]

    _log(f"{host}:{port} {gw} {scan_interval}")

    hass.data[DOMAIN][CONF_HOST] = host
    hass.data[DOMAIN][CONF_PORT] = port
    hass.data[DOMAIN][CONF_GW] = gw
    hass.data[DOMAIN][CONF_SCAN_INTERVAL] = scan_interval

    Config.is_c611 = gw == DEFAULT_GW

    from .ds_air_service.service import Service
    await hass.async_add_executor_job(Service.init, host, port, scan_interval)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if hass.data[DOMAIN].get("listener") is not None:
        hass.data[DOMAIN].get("listener")()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    from .ds_air_service.service import Service
    Service.destroy()

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_reload(entry.entry_id)
    return True
