from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, CONF_SENSORS
from homeassistant.core import callback, HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CONF_GW, DEFAULT_GW, DEFAULT_PORT, GW_LIST, DEFAULT_HOST
from .ds_air_service.service import Service
from .hass_inst import GetHass

_LOGGER = logging.getLogger(__name__)


def _log(s: str) -> object:
    s = str(s)
    for i in s.split("\n"):
        _LOGGER.debug(i)


class DsAirFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self.host = None
        self.port = None
        self.gw = None
        self.sensor_check = {}
        self.user_input = {}

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:

        #if self._async_current_entries():
        #    return self.async_abort(reason="single_instance_allowed")

        errors = {}
        if user_input is not None:
            self.user_input.update(user_input)
            if user_input.get(CONF_SENSORS) == False or user_input.get("temp") is not None:
                return self.async_create_entry(
                    title="网关"+user_input.get(CONF_HOST), data=self.user_input
                )
            else:
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema({
                        vol.Required("temp", default=True): bool,
                        vol.Required("humidity", default=True): bool,
                        vol.Required("pm25", default=True): bool,
                        vol.Required("co2", default=True): bool,
                        vol.Required("tvoc", default=True): bool,
                        vol.Required("voc", default=False): bool,
                        vol.Required("hcho", default=False): bool,
                    }), errors=errors
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_GW, default=DEFAULT_GW): vol.In(GW_LIST),
                vol.Required(CONF_SCAN_INTERVAL, default=5): int,
                vol.Required(CONF_SENSORS, default=True): bool
            }), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
            config_entry: ConfigEntry,
    ) -> DsAirOptionsFlowHandler:
        """Options callback for DS-AIR."""
        return DsAirOptionsFlowHandler(config_entry)


class DsAirOptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options for sensors binding."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize DSAir options flow."""
        self.config_entry = entry
        self._len = 3
        self._cur = 0
        hass: HomeAssistant = GetHass.get_hash()
        self._climates = list(map(lambda state: state.alias, Service.get_aircons()))
        sensors = hass.states.async_all("sensor")
        self._sensors_temp = list(map(lambda state: state.entity_id,
                                 filter(lambda state: state.attributes.get("device_class") == "temperature", sensors)))
        self._sensors_humi = list(map(lambda state: state.entity_id,
                                 filter(lambda state: state.attributes.get("device_class") == "humidity", sensors)))
        self._config_data = []

    async def async_step_init(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        self._len = len(self._climates)
        self._cur = 0
        return await self.async_step_user()

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self._config_data.append({
                "climate": user_input.get("climate"),
                "sensor_temp": user_input.get("sensor_temp"),
                "sensor_humi": user_input.get("sensor_humi")
            })
        if self._cur == self._len:
            return self.async_create_entry(title="", data={"link": self._config_data})

        form = self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "climate",
                        default=self._climates[self._cur]
                    ): vol.In([self._climates[self._cur]]),
                    vol.Optional("sensor_temp"): vol.In(self._sensors_temp),
                    vol.Optional("sensor_humi"): vol.In(self._sensors_humi)
                }
            )
        )

        self._cur = self._cur + 1

        return form
