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

from .const import (
    CONF_CONFIG_TYPE,
    CONF_ENTRY_TYPE,
    CONF_GW,
    CONF_HOME_ID,
    CONF_HOME_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
    DEFAULT_GW,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
    ENTRY_TYPE_GATEWAY,
    ENTRY_TYPE_POWER,
    GW_LIST,
    get_default_gateway_name,
)
from .daikin_power import DaikinPowerClient

_LOGGER = logging.getLogger(__name__)


def _log(s: str) -> None:
    s = str(s)
    for i in s.split("\n"):
        _LOGGER.debug(i)


class DsAirFlowHandler(ConfigFlow, domain=DOMAIN):
    VERSION = 2

    def __init__(self):
        self.user_input = {}
        self._power_data: dict[str, Any] = {}
        self._homes: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """First step: choose between gateway configuration and power consumption."""
        if user_input is not None:
            config_type = user_input.get(CONF_CONFIG_TYPE)
            if config_type == ENTRY_TYPE_POWER:
                return await self.async_step_power()
            if config_type == ENTRY_TYPE_GATEWAY or CONF_HOST in user_input:
                return await self.async_step_gateway(user_input)

        return self.async_show_menu(
            step_id="user",
            menu_options=["gateway", "power"],
        )

    async def async_step_gateway(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure gateway (original flow)."""
        errors = {}
        if user_input is not None:
            self.user_input.update(user_input)
            if not user_input.get(CONF_SENSORS) or user_input.get("temp") is not None:
                self.user_input[CONF_ENTRY_TYPE] = ENTRY_TYPE_GATEWAY
                return self.async_create_entry(
                    title=get_default_gateway_name(),
                    data=self.user_input,
                )

            return self.async_show_form(
                step_id="gateway",
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
            step_id="gateway",
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

    async def async_step_power(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Input username and password."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD].strip()

            cert_cache_dir = self.hass.config.path(".storage", "ds_air_cert")
            client = DaikinPowerClient(cert_cache_dir=cert_cache_dir)

            try:
                token = await self.hass.async_add_executor_job(
                    client.login_by_password, username, password
                )
                homes = await self.hass.async_add_executor_job(client.get_homes)
                if not homes:
                    errors["base"] = "no_homes"
                else:
                    self._power_data = {
                        CONF_ENTRY_TYPE: ENTRY_TYPE_POWER,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_TOKEN: token,
                    }
                    self._homes = homes
                    return await self.async_step_power_home()
            except Exception as err:
                _LOGGER.exception("Daikin power login failed: %s", err)
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="power",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_power_home(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Choose home and create power consumption entry."""
        errors: dict[str, str] = {}

        home_options: dict[str, str] = {}
        for h in self._homes:
            h_id = str(h["homeId"])
            h_name = h.get("homeName") or "家庭"
            home_options[h_id] = f"{h_name} (ID: {h_id})"

        default_home_id = str(self._homes[0]["homeId"]) if self._homes else ""

        if user_input is not None:
            selected_id = str(user_input[CONF_HOME_ID])
            selected_home = next(
                (h for h in self._homes if str(h["homeId"]) == selected_id),
                None,
            )
            home_name = (
                selected_home.get("homeName") if selected_home else f"家庭 {selected_id}"
            )
            home_id = int(selected_id)

            await self.async_set_unique_id(f"dsair_power_{home_id}")
            self._abort_if_unique_id_configured()

            entry_data = {
                **self._power_data,
                CONF_HOME_ID: home_id,
                CONF_HOME_NAME: home_name,
            }

            title = f"{home_name} 电量统计"
            return self.async_create_entry(title=title, data=entry_data)

        return self.async_show_form(
            step_id="power_home",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOME_ID, default=default_home_id): vol.In(
                        home_options
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Options callback for DS-AIR."""
        if config_entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_POWER:
            return DsAirPowerOptionsFlowHandler(config_entry)
        return DsAirOptionsFlowHandler(config_entry)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Change the model without recreating the gateway or its entities."""
        entry = self._get_reconfigure_entry()
        if (
            entry.data.get(CONF_ENTRY_TYPE, ENTRY_TYPE_GATEWAY) != ENTRY_TYPE_GATEWAY
            or CONF_HOST not in entry.data
        ):
            return self.async_abort(reason="reconfigure_not_supported")
        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry, data_updates={CONF_GW: user_input[CONF_GW]}
            )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_GW, default=entry.data.get(CONF_GW, DEFAULT_GW)
                    ): vol.In(GW_LIST),
                }
            ),
        )


class DsAirPowerOptionsFlowHandler(OptionsFlow):
    """Options flow for power consumption entries."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage power options."""
        return self.async_abort(reason="not_supported")


class DsAirOptionsFlowHandler(OptionsFlow):
    """Config flow options for integration"""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._config_data = []
        self._climates: dict[str, str] = {}  # set in async_step_init
        self._climate_ids: list[str] = []  # set in async_step_init
        self._len: int = 0  # set in async_step_init
        self._sensors_temp: dict[str, str] = {}
        self._sensors_humi: dict[str, str] = {}
        self._cur = -1
        self.user_input = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        service = self.hass.data[DOMAIN][self._config_entry.entry_id]
        host = self._config_entry.data[CONF_HOST]
        self._climates = {
            state.unique_id: f"{state.alias} ({host} {state.room_id}-{state.unit_id:02d})"
            for state in service.get_aircons()
        }
        self._climate_ids = list(self._climates)
        self._len = len(self._climate_ids)

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
                    self._config_entry, data=self.user_input
                )
                return self.async_create_entry(title="", data={})
        else:
            self.user_input["_invaild"] = True
            data = self._config_entry.data
            # if CONF_SENSORS:
            return self.async_show_form(
                step_id="adjust_config",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST, default=data[CONF_HOST]): str,
                        vol.Required(CONF_PORT, default=data[CONF_PORT]): int,
                        vol.Required(CONF_GW, default=data[CONF_GW]): vol.In(GW_LIST),
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
        cur_climate: str = self._climate_ids[self._cur]
        cur_links = self._config_entry.options.get("link", [])
        cur_link = next(
            (link for link in cur_links if link.get("climate") == cur_climate), None
        )
        cur_sensor_temp = cur_link.get("sensor_temp") if cur_link else None
        cur_sensor_humi = cur_link.get("sensor_humi") if cur_link else None
        return self.async_show_form(
            step_id="bind_sensors",
            data_schema=vol.Schema(
                {
                    vol.Required("climate", default=cur_climate): vol.In(
                        {cur_climate: self._climates[cur_climate]}
                    ),
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
