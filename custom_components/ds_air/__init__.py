"""
Platform for DS-AIR of Daikin
https://www.daikin-china.com.cn/newha/products/4/19/DS-AIR/
"""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import CONF_GW, DEFAULT_HOST, DEFAULT_PORT, DEFAULT_GW
from .ds_air_service.config import Config

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["climate", "sensor"]


def _log(s: str):
    s = str(s)
    for i in s.split("\n"):
        _LOGGER.debug(i)


def setup(hass, config):
    return True


async def async_setup_entry(
        hass: HomeAssistant, entry: ConfigEntry
):
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    gw = entry.data[CONF_GW]

    if host is None:
        host = DEFAULT_HOST
    if port is None:
        port = DEFAULT_PORT
    if gw is None:
        gw = DEFAULT_GW

    Config.is_c611 = gw == DEFAULT_GW

    _log("host:" + host + "\nport:" + str(port))
    from .ds_air_service.service import Service
    await hass.async_add_executor_job(Service.init, host, port)
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    from .ds_air_service.service import Service
    Service.destroy()

    return unload_ok
