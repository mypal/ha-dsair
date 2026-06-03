"""Daikin platform that offers HD (Heat Exchanger) devices as water heaters.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/water_heater/
"""

import logging

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
    STATE_HEAT_PUMP,
    STATE_OFF,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER
from .ds_air_service import HD, HDStatus, EnumControl, Service, display

_LOGGER = logging.getLogger(__name__)

# HD支持的功能标志
_SUPPORT_FLAGS = (
    WaterHeaterEntityFeature.TARGET_TEMPERATURE
    | WaterHeaterEntityFeature.OPERATION_MODE
)

# HD支持的操作模式
HD_OPERATION_LIST = [
    STATE_HEAT_PUMP,
    STATE_OFF,
]


def _log(s: str):
    s = str(s)
    for i in s.split("\n"):
        _LOGGER.debug(i)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the HD devices."""
    _LOGGER.debug("开始在HA中初始化大金HD设备")
    service: Service = hass.data[DOMAIN][entry.entry_id]
    hds = service.get_hds()
    water_heaters = [DsWaterHeater(service, hd) for hd in hds]
    async_add_entities(water_heaters)

    _LOGGER.debug(f"初始化HD设备完成，共有{len(water_heaters)}台设备。")


class DsWaterHeater(WaterHeaterEntity):
    """Representation of a Daikin HD water heater device."""

    # Entity Properties
    _attr_has_entity_name: bool = True
    _attr_name: str | None = None
    _attr_should_poll: bool = False

    # Water Heater Properties
    _attr_max_temp: float = 55.0
    _attr_min_temp: float = 25.0
    _attr_precision: float = PRECISION_TENTHS
    _attr_target_temperature_step: float = 1.0
    _attr_temperature_unit: str = UnitOfTemperature.CELSIUS
    _attr_operation_list: list[str] = HD_OPERATION_LIST
    _attr_supported_features: int = _SUPPORT_FLAGS

    def __init__(self, service: Service, hd: HD):
        _log("create hd:")
        _log(str(hd.__dict__))
        """Initialize the water heater device."""
        self.service = service
        self._device_info = hd
        self._attr_unique_id = hd.unique_id

        service.register_hd_hook(hd, self._status_change_hook)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=hd.alias if "水热交换器" in hd.alias else f"{hd.alias} 水热交换器",
            manufacturer=MANUFACTURER,
        )

    def _status_change_hook(self, **kwargs) -> None:
        """处理来自服务层的状态更新"""
        _log(f"[HD Entity] 收到状态更新: {kwargs}")

        # 更新状态
        if kwargs.get("status") is not None:
            curstatus: HDStatus = self._device_info.status
            newstatus: HDStatus = kwargs['status']

            if newstatus.switch is not None:
                old_mode = self.current_operation
                curstatus.switch = newstatus.switch
                _log(f"[HD Entity] 模式更新: {old_mode} -> {self.current_operation}")

            if newstatus.warm_temperature is not None:
                old_temp = self.target_temperature
                curstatus.warm_temperature = newstatus.warm_temperature
                _log(f"[HD Entity] 温度更新: {old_temp}°C -> {self.target_temperature}°C")

            if newstatus.mute is not None:
                curstatus.mute = newstatus.mute
            if newstatus.warm_cold is not None:
                curstatus.warm_cold = newstatus.warm_cold
            if newstatus.preheat is not None:
                curstatus.preheat = newstatus.preheat
            if newstatus.cold_lower is not None:
                curstatus.cold_lower = newstatus.cold_lower
            if newstatus.cold_temperature is not None:
                curstatus.cold_temperature = newstatus.cold_temperature
            if newstatus.cold_upper is not None:
                curstatus.cold_upper = newstatus.cold_upper
            if newstatus.mute_enable is not None:
                curstatus.mute_enable = newstatus.mute_enable
            if newstatus.night_energy_end_hour is not None:
                curstatus.night_energy_end_hour = newstatus.night_energy_end_hour
            if newstatus.night_energy_end_minute is not None:
                curstatus.night_energy_end_minute = newstatus.night_energy_end_minute
            if newstatus.night_energy_reduce_temp is not None:
                curstatus.night_energy_reduce_temp = newstatus.night_energy_reduce_temp
            if newstatus.night_energy_start_hour is not None:
                curstatus.night_energy_start_hour = newstatus.night_energy_start_hour
            if newstatus.night_energy_start_minute is not None:
                curstatus.night_energy_start_minute = newstatus.night_energy_start_minute
            if newstatus.night_energy_switch is not None:
                curstatus.night_energy_switch = newstatus.night_energy_switch
            if newstatus.outdoor_temp is not None:
                curstatus.outdoor_temp = newstatus.outdoor_temp
            if newstatus.switch_enable is not None:
                curstatus.switch_enable = newstatus.switch_enable
            if newstatus.temperature_set is not None:
                curstatus.temperature_set = newstatus.temperature_set
            if newstatus.warm_lower is not None:
                curstatus.warm_lower = newstatus.warm_lower

        self.async_write_ha_state()

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device_info.status.warm_temperature

    @property
    def current_operation(self) -> str | None:
        """Return current operation."""
        if self._device_info.status.switch is None:
            return None
        if self._device_info.status.switch == EnumControl.Switch.ON:
            return STATE_HEAT_PUMP
        return STATE_OFF

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            _log(f"[HD Entity] 设置目标温度: {temperature}°C")
            status = self._device_info.status
            # 判断当前模式，需要开机且为制热模式
            if status.switch == EnumControl.Switch.ON and (status.warm_cold == 1 or status.warm_cold is None):
                new_status = HDStatus()
                new_status.warm_temperature = temperature
                status.warm_temperature = temperature
                self.service.hd_control(self._device_info, new_status)
                self.async_write_ha_state()

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        _log(f"[HD Entity] 设置操作模式: {operation_mode}")
        new_status = HDStatus()

        if operation_mode == STATE_HEAT_PUMP:
            new_status.switch = EnumControl.Switch.ON
            # 同时更新本地状态以提供即时UI反馈
            self._device_info.status.switch = EnumControl.Switch.ON
        elif operation_mode == STATE_OFF:
            new_status.switch = EnumControl.Switch.OFF
            # 同时更新本地状态以提供即时UI反馈
            self._device_info.status.switch = EnumControl.Switch.OFF
        else:
            _log(f"[HD Entity] 不支持的操作模式: {operation_mode}")
            return

        self.service.hd_control(self._device_info, new_status)
        self.async_write_ha_state()
