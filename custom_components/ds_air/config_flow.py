from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import callback, HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .ds_air_service.display import display
from .ds_air_service.service import Service
from .const import DOMAIN, CONF_GW, DEFAULT_GW, DEFAULT_PORT, GW_LIST
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

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}
        if user_input is not None:
            _log(user_input[CONF_HOST])
            _log(user_input[CONF_PORT])
            _log(user_input[CONF_GW])
            return self.async_create_entry(
                title="金制空气", data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Optional(CONF_GW, default=DEFAULT_GW): vol.In(GW_LIST),
                vol.Optional(CONF_SCAN_INTERVAL, default=5): vol.In([5])
            }), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
            config_entry: ConfigEntry,
    ) -> DsAirOptionsFlowHandler:
        """Options callback for AccuWeather."""
        return DsAirOptionsFlowHandler(config_entry)


class DsAirOptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options for AccuWeather."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize AccuWeather options flow."""
        self.config_entry = entry
        self._len = 3
        self._cur = 0
        hass: HomeAssistant = GetHass.get_hash()
        self._climates = list(map(lambda state: state.alias, Service.get_aircons()))
        sensors = hass.states.async_all("sensor")
        self._sensors = list(map(lambda state: state.entity_id,
                                 filter(lambda state: state.attributes.get("device_class") == "temperature", sensors)))
        # self._sensors = []
        # for s in sensors:
        #     if s.attributes.get("device_class") == "temperature":
        #         self._sensors.append(s.entity_id)
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
                "sensor": user_input.get("sensor")
            })
            _log(user_input.get("climate"))
            _log(user_input.get("sensor"))
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
                    vol.Optional("sensor"): vol.In(self._sensors)
                }
            )
        )

        self._cur = self._cur + 1

        return form
