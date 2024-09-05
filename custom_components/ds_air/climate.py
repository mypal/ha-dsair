"""Daikin platform that offers climate devices.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""

import logging

import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA,
    PRESET_COMFORT,
    PRESET_NONE,
    PRESET_SLEEP,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_PORT,
    MAJOR_VERSION,
    MINOR_VERSION,
    PRECISION_TENTHS,
    UnitOfTemperature,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    AIR_FLOW_NAME_LIST,
    DOMAIN,
    FAN_DIRECTION_LIST,
    MANUFACTURER,
    get_action_name,
    get_air_flow_enum,
    get_air_flow_name,
    get_fan_direction_enum,
    get_fan_direction_name,
    get_mode_name,
)
from .ds_air_service import AirCon, AirConStatus, EnumControl, Service, display

_SUPPORT_FLAGS = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.FAN_MODE
    | ClimateEntityFeature.PRESET_MODE
)
if (MAJOR_VERSION, MINOR_VERSION) >= (2024, 2):
    _SUPPORT_FLAGS |= ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_HOST): cv.string, vol.Optional(CONF_PORT): cv.port}
)

_LOGGER = logging.getLogger(__name__)


def _log(s: str):
    s = str(s)
    for i in s.split("\n"):
        _LOGGER.debug(i)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the climate devices."""
    service: Service = hass.data[DOMAIN][entry.entry_id]
    climates = [DsAir(service, aircon) for aircon in service.get_aircons()]
    async_add_entities(climates)
    link = entry.options.get("link")
    sensor_temp_map: dict[str, list[DsAir]] = {}
    sensor_humi_map: dict[str, list[DsAir]] = {}
    if link is not None:
        for i in link:
            climate_name = i.get("climate")
            if climate := next(
                c for c in climates if c._device_info.alias == climate_name
            ):
                if temp_entity_id := i.get("sensor_temp"):
                    sensor_temp_map.setdefault(temp_entity_id, []).append(climate)
                    climate.linked_temp_entity_id = temp_entity_id
                if humi_entity_id := i.get("sensor_humi"):
                    sensor_humi_map.setdefault(humi_entity_id, []).append(climate)
                    climate.linked_humi_entity_id = humi_entity_id

    async def listener(event: Event):
        sensor_id = event.data.get("entity_id")
        if sensor_id in sensor_temp_map:
            for climate in sensor_temp_map[sensor_id]:
                climate.update_cur_temp(event.data.get("new_state").state)
        elif sensor_id in sensor_humi_map:
            for climate in sensor_humi_map[sensor_id]:
                climate.update_cur_humi(event.data.get("new_state").state)

    remove_listener = async_track_state_change_event(
        hass, list(sensor_temp_map.keys()) + list(sensor_humi_map.keys()), listener
    )
    service.state_change_listener = remove_listener


class DsAir(ClimateEntity):
    """Representation of a Daikin climate device."""

    # Entity Properties
    _attr_has_entity_name: bool = True
    _attr_name: str | None = None
    _attr_should_poll: bool = False

    # Climate Properties
    _attr_fan_modes: list[str] | None = AIR_FLOW_NAME_LIST
    # _attr_max_humidity: float = 3
    _attr_max_temp: float = 32
    # _attr_min_humidity: float = 1
    _attr_min_temp: float = 16
    _attr_precision: float = PRECISION_TENTHS
    _attr_swing_modes: list[str] | None = FAN_DIRECTION_LIST[1:]
    _attr_target_temperature_high: float | None = None
    _attr_target_temperature_low: float | None = None
    _attr_target_temperature_step: float | None = 0.5
    _attr_temperature_unit: str = UnitOfTemperature.CELSIUS

    _enable_turn_on_off_backwards_compatibility: bool = False  # used in 2024.2~2024.12

    def __init__(self, service: Service, aircon: AirCon):
        _log("create aircon:")
        _log(str(aircon.__dict__))
        _log(str(aircon.status.__dict__))
        """Initialize the climate device."""
        self.service = service
        self._device_info = aircon
        self._attr_unique_id = aircon.unique_id
        self.linked_temp_entity_id: str | None = None
        self.linked_humi_entity_id: str | None = None
        self._link_cur_temp = False

        service.register_status_hook(aircon, self._status_change_hook)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=aircon.alias if "空调" in aircon.alias else f"{aircon.alias} 空调",
            manufacturer=MANUFACTURER,
        )

    async def async_added_to_hass(self) -> None:
        if self.linked_temp_entity_id:
            if state := self.hass.states.get(self.linked_temp_entity_id):
                self.update_cur_temp(state.state)
        if self.linked_humi_entity_id:
            if state := self.hass.states.get(self.linked_humi_entity_id):
                self.update_cur_humi(state.state)

    def _status_change_hook(self, **kwargs):
        _log("hook:")
        if kwargs.get("aircon") is not None:
            aircon: AirCon = kwargs["aircon"]
            aircon.status = self._device_info.status
            self._device_info = aircon
            _log(display(self._device_info))

        if kwargs.get("status") is not None:
            status: AirConStatus = self._device_info.status
            new_status: AirConStatus = kwargs["status"]
            if new_status.mode is not None:
                status.mode = new_status.mode
            if new_status.switch is not None:
                status.switch = new_status.switch
            if new_status.humidity is not None:
                status.humidity = new_status.humidity
            if new_status.air_flow is not None:
                status.air_flow = new_status.air_flow
            if new_status.fan_direction1 is not None:
                status.fan_direction1 = new_status.fan_direction1
            if new_status.fan_direction2 is not None:
                status.fan_direction2 = new_status.fan_direction2
            if new_status.setted_temp is not None:
                status.setted_temp = new_status.setted_temp
            if new_status.current_temp is not None:
                status.current_temp = new_status.current_temp
            if new_status.breathe is not None:
                status.breathe = new_status.breathe
            _log(display(self._device_info.status))
        self.schedule_update_ha_state()

    def update_cur_temp(self, value: str | None) -> None:
        self._link_cur_temp = value is not None
        try:
            self._attr_current_temperature = float(value)
        except ValueError:
            self._attr_current_temperature = None
        self.schedule_update_ha_state()

    def update_cur_humi(self, value: str | None) -> None:
        try:
            self._attr_current_humidity = int(float(value))
        except ValueError:
            self._attr_current_humidity = None
        self.schedule_update_ha_state()

    @property
    def target_humidity(self) -> float | None:
        """Return the humidity we try to reach."""
        return self._device_info.status.humidity.value

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation if supported."""
        if self._device_info.status.switch == EnumControl.Switch.OFF:
            return HVACAction.OFF
        return get_action_name(self._device_info.status.mode.value)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation ie. heat, cool mode."""
        if self._device_info.status.switch == EnumControl.Switch.OFF:
            return HVACMode.OFF
        return get_mode_name(self._device_info.status.mode.value)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        li: list[HVACMode] = []
        aircon = self._device_info
        if aircon.cool_mode:
            li.append(HVACMode.COOL)
        if aircon.heat_mode or aircon.pre_heat_mode:
            li.append(HVACMode.HEAT)
        if aircon.auto_dry_mode or aircon.dry_mode or aircon.more_dry_mode:
            li.append(HVACMode.DRY)
        if aircon.ventilation_mode:
            li.append(HVACMode.FAN_ONLY)
        if aircon.relax_mode or aircon.sleep_mode or aircon.auto_mode:
            li.append(HVACMode.AUTO)
        li.append(HVACMode.OFF)
        return li

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self._link_cur_temp:
            return self._attr_current_temperature
        if self._device_info.config.is_c611:
            return None
        return self._device_info.status.current_temp / 10

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._device_info.status.setted_temp / 10

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp.

        Requires ClimateEntityFeature.PRESET_MODE.
        """
        if self._device_info.status.mode == EnumControl.Mode.SLEEP:
            return PRESET_SLEEP
        if self._device_info.status.mode == EnumControl.Mode.RELAX:
            return PRESET_COMFORT
        return PRESET_NONE

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes.

        Requires ClimateEntityFeature.PRESET_MODE.
        """
        result = []
        aircon = self._device_info
        if aircon.sleep_mode:
            result.append(PRESET_SLEEP)
        if aircon.relax_mode:
            result.append(PRESET_COMFORT)
        result.append(PRESET_NONE)
        return result

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting.

        Requires ClimateEntityFeature.FAN_MODE.
        """
        return get_air_flow_name(self._device_info.status.air_flow.value)

    @property
    def swing_mode(self) -> str | None:
        """Return the swing setting.

        Requires ClimateEntityFeature.SWING_MODE.
        """
        return get_fan_direction_name(self._device_info.status.fan_direction1.value)

    def set_temperature(self, **kwargs) -> None:
        """Set new target temperatures."""
        if (temperate := kwargs.get(ATTR_TEMPERATURE)) is not None:
            status = self._device_info.status
            if status.switch == EnumControl.Switch.ON and status.mode not in [
                EnumControl.Mode.VENTILATION,
                EnumControl.Mode.MOREDRY,
            ]:
                new_status = AirConStatus()
                status.setted_temp = round(temperate * 10.0)
                new_status.setted_temp = round(temperate * 10.0)
                self.service.control(self._device_info, new_status)
                self.schedule_update_ha_state()

    def set_humidity(self, humidity: int) -> None:
        """Set new humidity level."""
        status = self._device_info.status
        if status.switch == EnumControl.Switch.ON and status.mode in [
            EnumControl.Mode.RELAX,
            EnumControl.Mode.SLEEP,
        ]:
            new_status = AirConStatus()
            status.humidity = EnumControl.Humidity(humidity)
            new_status.humidity = EnumControl.Humidity(humidity)
            self.service.control(self._device_info, new_status)
            self.schedule_update_ha_state()

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        status = self._device_info.status
        if status.switch == EnumControl.Switch.ON and status.mode not in [
            EnumControl.Mode.MOREDRY,
            EnumControl.Mode.SLEEP,
        ]:
            new_status = AirConStatus()
            status.air_flow = get_air_flow_enum(fan_mode)
            new_status.air_flow = get_air_flow_enum(fan_mode)
            self.service.control(self._device_info, new_status)
            self.schedule_update_ha_state()

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        aircon = self._device_info
        status = aircon.status
        new_status = AirConStatus()
        if hvac_mode == HVACMode.OFF:
            status.switch = EnumControl.Switch.OFF
            new_status.switch = EnumControl.Switch.OFF
            self.service.control(self._device_info, new_status)
        else:
            status.switch = EnumControl.Switch.ON
            new_status.switch = EnumControl.Switch.ON
            m = EnumControl.Mode
            mode = None
            if hvac_mode == HVACMode.COOL:
                mode = m.COLD
            elif hvac_mode == HVACMode.HEAT:
                if aircon.heat_mode:
                    mode = m.HEAT
                else:
                    mode = m.PREHEAT
            elif hvac_mode == HVACMode.DRY:
                if aircon.auto_dry_mode:
                    mode = m.AUTODRY
                elif aircon.more_dry_mode:
                    mode = m.MOREDRY
                else:
                    mode = m.DRY
            elif hvac_mode == HVACMode.FAN_ONLY:
                mode = m.VENTILATION
            elif hvac_mode == HVACMode.AUTO:
                if aircon.auto_mode:
                    mode = m.AUTO
                elif aircon.relax_mode:
                    mode = m.RELAX
                else:
                    mode = m.SLEEP
            status.mode = mode
            new_status.mode = mode
            self.service.control(self._device_info, new_status)
        self.schedule_update_ha_state()

    def set_swing_mode(self, swing_mode: str) -> None:
        """Set new swing mode."""
        status = self._device_info.status
        if status.switch == EnumControl.Switch.ON:
            new_status = AirConStatus()
            status.fan_direction1 = self._device_info.status.fan_direction1
            new_status.fan_direction1 = self._device_info.status.fan_direction1
            status.fan_direction2 = get_fan_direction_enum(swing_mode)
            new_status.fan_direction2 = get_fan_direction_enum(swing_mode)
            self.service.control(self._device_info, new_status)
            self.schedule_update_ha_state()

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        aircon = self._device_info
        status = aircon.status
        new_status = AirConStatus()
        m = EnumControl.Mode
        mode = None
        if preset_mode == PRESET_NONE:
            if aircon.auto_mode:
                mode = m.AUTO
            elif aircon.relax_mode:
                mode = m.RELAX
            else:
                mode = m.COLD
        elif preset_mode == PRESET_SLEEP:
            mode = m.SLEEP
        elif preset_mode == PRESET_COMFORT:
            mode = m.RELAX
        status.mode = mode
        new_status.mode = mode
        self.service.control(self._device_info, new_status)
        self.schedule_update_ha_state()

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        flags = _SUPPORT_FLAGS
        aircon = self._device_info
        if aircon.status.fan_direction1.value > 0:
            flags |= ClimateEntityFeature.SWING_MODE
        if aircon.relax_mode:
            flags |= ClimateEntityFeature.TARGET_HUMIDITY
        return flags
