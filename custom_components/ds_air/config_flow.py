from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SENSORS,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_GW, DEFAULT_GW, DEFAULT_HOST, DEFAULT_PORT, DOMAIN, GW_LIST
from .ds_air_service import Service

_LOGGER = logging.getLogger(__name__)


def _log(s: str) -> None:
    s = str(s)
    for i in s.split("\n"):
        _LOGGER.debug(i)


class DsAirFlowHandler(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self.user_input = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}
        if user_input is not None:
            self.user_input.update(user_input)
            if not user_input.get(CONF_SENSORS) or user_input.get("temp") is not None:
                return self.async_create_entry(title="金制空气", data=self.user_input)
            else:
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema(
                        {
                            vol.Required("temp", default=True): bool,
                            vol.Required("humidity", default=True): bool,
                            vol.Required("pm25", default=True): bool,
                            vol.Required("co2", default=True): bool,
                            vol.Required("tvoc", default=True): bool,
                            vol.Required("voc", default=False): bool,
                            vol.Required("hcho", default=False): bool,
                        }
                    ),
                    errors=errors,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Required(CONF_GW, default=DEFAULT_GW): vol.In(GW_LIST),
                    vol.Required(CONF_SCAN_INTERVAL, default=5): int,
                    vol.Required(CONF_SENSORS, default=True): bool,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> DsAirOptionsFlowHandler:
        """Options callback for DS-AIR."""
        return DsAirOptionsFlowHandler(config_entry)


class DsAirOptionsFlowHandler(OptionsFlow):
    """Config flow options for integration"""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._config_data = []
        self._climates = list(map(lambda state: state.alias, Service.get_aircons()))
        self._sensors_temp = {}
        self._sensors_humi = {}
        self._len = len(self._climates)
        self._cur = -1
        self.user_input = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        sensors = self.hass.states.async_all("sensor")
        self._sensors_temp = {
            None: "None",
            **{
                state.entity_id: f"{state.attributes.get(ATTR_FRIENDLY_NAME, state.entity_id)} ({state.entity_id})"
                for state in sensors
                if state.attributes.get(ATTR_DEVICE_CLASS)
                == SensorDeviceClass.TEMPERATURE
            },
        }
        self._sensors_humi = {
            None: "None",
            **{
                state.entity_id: f"{state.attributes.get(ATTR_FRIENDLY_NAME, state.entity_id)} ({state.entity_id})"
                for state in sensors
                if state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.HUMIDITY
            },
        }

        return self.async_show_menu(
            step_id="init",
            menu_options=["adjust_config", "bind_sensors"],
        )

    async def async_step_adjust_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors = {}
        if user_input is not None:
            self.user_input.update(user_input)
            if self.user_input.get("_invaild"):
                self.user_input["_invaild"] = False
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=self.user_input
                )
                return self.async_create_entry(title="", data={})
        else:
            self.user_input["_invaild"] = True
            data = self.config_entry.data
            # if CONF_SENSORS:
            return self.async_show_form(
                step_id="adjust_config",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST, default=data[CONF_HOST]): str,
                        vol.Required(CONF_PORT, default=data[CONF_PORT]): int,
                        vol.Required(CONF_GW, default=data[CONF_GW]): vol.In(
                            GW_LIST
                        ),
                        vol.Required(
                            CONF_SCAN_INTERVAL, default=data[CONF_SCAN_INTERVAL]
                        ): int,
                        vol.Required(CONF_SENSORS, default=True): bool,
                        vol.Required("temp", default=data["temp"]): bool,
                        vol.Required("humidity", default=data["humidity"]): bool,
                        vol.Required("pm25", default=data["pm25"]): bool,
                        vol.Required("co2", default=data["co2"]): bool,
                        vol.Required("tvoc", default=data["tvoc"]): bool,
                        vol.Required("voc", default=data["voc"]): bool,
                        vol.Required("hcho", default=data["hcho"]): bool,
                    }
                ),
                errors=errors,
            )
            # else:
            #     return self.async_show_form(
            #         step_id="adjust_config",
            #         data_schema=vol.Schema(
            #             {
            #                 vol.Required(CONF_HOST, default=data[CONF_HOST]): str,
            #                 vol.Required(CONF_PORT, default=data[CONF_PORT]): int,
            #                 vol.Required(CONF_GW, default=data[CONF_GW]): vol.In(
            #                     GW_LIST
            #                 ),
            #                 vol.Required(
            #                     CONF_SCAN_INTERVAL, default=data[CONF_SCAN_INTERVAL]
            #                 ): int,
            #                 vol.Required(CONF_SENSORS, default=False): bool,
            #             }
            #         ),
            #         errors=errors,
            #     )

    async def async_step_bind_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle bind flow."""
        if self._len == 0:
            return self.async_show_form(step_id="empty", last_step=False)
        if user_input is not None:
            self._config_data.append(
                {
                    "climate": user_input.get("climate"),
                    "sensor_temp": user_input.get("sensor_temp"),
                    "sensor_humi": user_input.get("sensor_humi"),
                }
            )
        self._cur = self._cur + 1
        if self._cur > (self._len - 1):
            return self.async_create_entry(title="", data={"link": self._config_data})
        cur_climate: str = self._climates[self._cur]
        cur_links = self.config_entry.options.get("link", [])
        cur_link = next(
            (link for link in cur_links if link["climate"] == cur_climate), None
        )
        cur_sensor_temp = cur_link.get("sensor_temp") if cur_link else None
        cur_sensor_humi = cur_link.get("sensor_humi") if cur_link else None
        return self.async_show_form(
            step_id="bind_sensors",
            data_schema=vol.Schema(
                {
                    vol.Required("climate", default=cur_climate): vol.In([cur_climate]),
                    vol.Optional("sensor_temp", default=cur_sensor_temp): vol.In(
                        self._sensors_temp
                    ),
                    vol.Optional("sensor_humi", default=cur_sensor_humi): vol.In(
                        self._sensors_humi
                    ),
                }
            ),
        )

    async def async_step_empty(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """No AC found."""
        return await self.async_step_init(user_input)
