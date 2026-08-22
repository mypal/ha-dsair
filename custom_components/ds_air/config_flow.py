import logging
import socket
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
    CONF_CLOUD_HOME_ID,
    CONF_CLOUD_PASSWORD,
    CONF_CLOUD_USERNAME,
    CONF_CONNECTION_TYPE,
    CONNECTION_CLOUD,
    CONNECTION_LOCAL,
    CONF_GW,
    DEFAULT_GW,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
    GW_LIST,
    SMART_MESH,
    get_default_gateway_name,
)

_LOGGER = logging.getLogger(__name__)


def _log(s: str) -> None:
    s = str(s)
    for i in s.split("\n"):
        _LOGGER.debug(i)


def _test_gateway_connection(host: str, port: int) -> tuple[int, str]:
    """Test connection to gateway, probing ports 8008 and 8009."""
    candidate_ports = [port]
    alt_port = 8009 if port == 8008 else 8008
    if alt_port not in candidate_ports:
        candidate_ports.append(alt_port)

    for p in candidate_ports:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3.0)
        try:
            s.connect((host, p))
            # Send standard handshake
            s.sendall(bytes.fromhex("0210000d0001000100000000000000000100a003"))
            resp = s.recv(1024)
            s.close()
            if resp and len(resp) >= 4 and resp[0] == 2:
                gw_type = SMART_MESH if p == 8009 else DEFAULT_GW
                return p, gw_type
        except Exception as exc:
            _LOGGER.debug("Probe port %d failed on %s: %s", p, host, exc)
            s.close()

    return 0, ""


class DsAirFlowHandler(ConfigFlow, domain=DOMAIN):
    VERSION = 2

    def __init__(self):
        self.user_input = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Choose an independent local or cloud setup path."""
        return self.async_show_menu(
            step_id="user", menu_options=[CONNECTION_LOCAL, CONNECTION_CLOUD]
        )

    async def async_step_local(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors = {}
        if user_input is not None:
            # Step 1: Initial host / gateway form submitted
            if CONF_HOST in user_input and "temp" not in user_input:
                host = user_input[CONF_HOST].strip()
                port = user_input.get(CONF_PORT, DEFAULT_PORT)
                gw = user_input.get(CONF_GW, DEFAULT_GW)

                working_port, detected_gw = await self.hass.async_add_executor_job(
                    _test_gateway_connection, host, port
                )
                if working_port == 0:
                    errors["base"] = "cannot_connect"
                else:
                    self.user_input.update(user_input)
                    self.user_input[CONF_HOST] = host
                    self.user_input[CONF_PORT] = working_port
                    if detected_gw == SMART_MESH and gw == DEFAULT_GW:
                        self.user_input[CONF_GW] = SMART_MESH

                    await self.async_set_unique_id(f"ds_air_{host}")
                    self._abort_if_unique_id_configured()

                    if not self.user_input.get(CONF_SENSORS):
                        title = f"金制智联 ({host})" if self.user_input.get(CONF_GW) == SMART_MESH else get_default_gateway_name()
                        return self.async_create_entry(
                            title=title,
                            data=self.user_input,
                        )

                    return self.async_show_form(
                        step_id="local",
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

            elif "temp" in user_input:
                self.user_input.update(user_input)
                host = self.user_input.get(CONF_HOST, "")
                title = f"金制智联 ({host})" if self.user_input.get(CONF_GW) == SMART_MESH else get_default_gateway_name()
                return self.async_create_entry(
                    title=title,
                    data=self.user_input,
                )

        return self.async_show_form(
            step_id="local",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Required(CONF_GW, default=DEFAULT_GW): vol.In(GW_LIST),
                    vol.Required(CONF_SCAN_INTERVAL, default=5): int,
                    vol.Required(CONF_SENSORS, default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Create a cloud-only entry without probing a local gateway."""
        errors = {}
        if user_input is not None:
            username = user_input[CONF_CLOUD_USERNAME].strip()
            password = user_input[CONF_CLOUD_PASSWORD]
            from .ds_air_cloud import DaikinCloudClient

            client = DaikinCloudClient(username, password)
            try:
                if not await self.hass.async_add_executor_job(client.login):
                    errors["base"] = "invalid_auth"
                else:
                    homes, devices = await self.hass.async_add_executor_job(client.discover)
                    if not homes:
                        errors["base"] = "no_homes"
                    elif not devices:
                        errors["base"] = "no_devices"
                    else:
                        await self.async_set_unique_id(f"ds_air_cloud_{username}")
                        self._abort_if_unique_id_configured()
                        home_ids = sorted({int(device["homeId"]) for device in devices})
                        return self.async_create_entry(
                            title=f"金制空气云端 ({username})",
                            data={
                                CONF_CONNECTION_TYPE: CONNECTION_CLOUD,
                                CONF_CLOUD_USERNAME: username,
                                CONF_CLOUD_PASSWORD: password,
                                CONF_CLOUD_HOME_ID: home_ids[0],
                                CONF_GW: SMART_MESH,
                                CONF_SCAN_INTERVAL: 5,
                                CONF_SENSORS: False,
                            },
                        )
            except Exception:
                _LOGGER.exception("Unable to initialize Daikin cloud account")
                errors["base"] = "cannot_connect"
            finally:
                client.close()

        return self.async_show_form(
            step_id="cloud",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLOUD_USERNAME): str,
                    vol.Required(CONF_CLOUD_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Options callback for DS-AIR."""
        return DsAirOptionsFlowHandler(config_entry)


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
        host = self._config_entry.data.get(CONF_HOST, "cloud")
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

        if self._config_entry.data.get(CONF_CONNECTION_TYPE) == CONNECTION_CLOUD:
            return self.async_show_menu(
                step_id="init", menu_options=["bind_cloud"]
            )
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
                return self.async_create_entry(
                    title="", data=dict(self._config_entry.options)
                )
        else:
            self.user_input["_invaild"] = True
            data = self._config_entry.data
            # if CONF_SENSORS:
            return self.async_show_form(
                step_id="adjust_config",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST, default=data.get(CONF_HOST, DEFAULT_HOST)): str,
                        vol.Required(CONF_PORT, default=data.get(CONF_PORT, DEFAULT_PORT)): int,
                        vol.Required(CONF_GW, default=data.get(CONF_GW, DEFAULT_GW)): vol.In(GW_LIST),
                        vol.Required(
                            CONF_SCAN_INTERVAL, default=data.get(CONF_SCAN_INTERVAL, 5)
                        ): int,
                        vol.Required(CONF_SENSORS, default=data.get(CONF_SENSORS, True)): bool,
                        vol.Required("temp", default=data.get("temp", True)): bool,
                        vol.Required("humidity", default=data.get("humidity", True)): bool,
                        vol.Required("pm25", default=data.get("pm25", True)): bool,
                        vol.Required("co2", default=data.get("co2", True)): bool,
                        vol.Required("tvoc", default=data.get("tvoc", True)): bool,
                        vol.Required("voc", default=data.get("voc", True)): bool,
                        vol.Required("hcho", default=data.get("hcho", True)): bool,
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
            return self.async_create_entry(
                title="",
                data={**self._config_entry.options, "link": self._config_data},
            )
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

    async def async_step_bind_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle Daikin China cloud account binding."""
        errors = {}
        cloud_only = self._config_entry.data.get(CONF_CONNECTION_TYPE) == CONNECTION_CLOUD
        if not cloud_only:
            return self.async_abort(reason="not_supported")
        opts = self._config_entry.data

        if user_input is not None:
            username = (user_input.get(CONF_CLOUD_USERNAME) or "").strip()
            password = (user_input.get(CONF_CLOUD_PASSWORD) or "").strip()

            if username and password:
                from .ds_air_cloud import DaikinCloudClient
                client = DaikinCloudClient(username, password)
                login_ok = await self.hass.async_add_executor_job(client.login)
                if login_ok:
                    client.close()
                    new_data = dict(self._config_entry.data)
                    new_data[CONF_CLOUD_USERNAME] = username
                    new_data[CONF_CLOUD_PASSWORD] = password
                    self.hass.config_entries.async_update_entry(
                        self._config_entry, data=new_data
                    )
                    return self.async_create_entry(
                        title="", data=dict(self._config_entry.options)
                    )
                else:
                    client.close()
                    errors["base"] = "invalid_auth"
            else:
                errors["base"] = "invalid_auth"

        schema = {
            vol.Optional(
                CONF_CLOUD_USERNAME,
                default=opts.get(CONF_CLOUD_USERNAME, ""),
            ): str,
            vol.Optional(
                CONF_CLOUD_PASSWORD,
                default=opts.get(CONF_CLOUD_PASSWORD, ""),
            ): str,
        }
        return self.async_show_form(
            step_id="bind_cloud",
            data_schema=vol.Schema(schema),
            errors=errors,
        )

    async def async_step_empty(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """No AC found."""
        return await self.async_step_init(user_input)
