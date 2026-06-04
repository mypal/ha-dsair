import time
from collections.abc import Iterable

from .config import Config
from .ctrl_enum import (
    EnumControl,
    EnumDevice,
    EnumFanDirection,
    EnumFanVolume,
    EnumOutDoorRunCond,
    EnumSwitch,
)


def build_device_unique_id(gateway_id: str, room_id: int, unit_id: int) -> str:
    return f"daikin_{gateway_id}_{room_id}_{unit_id}"


def migrate_legacy_unique_id(
    unique_id: str, gateway_id: str, sensor_keys: Iterable[str] = ()
) -> str | None:
    parts = unique_id.split("_")
    if len(parts) == 3 and parts[0] == "daikin":
        room_id, unit_id = parts[1:]
        if room_id.isdigit() and unit_id.isdigit():
            return build_device_unique_id(gateway_id, int(room_id), int(unit_id))

    for sensor_key in sensor_keys:
        prefix = f"{sensor_key}_"
        if not unique_id.startswith(prefix):
            continue
        migrated_device_id = migrate_legacy_unique_id(
            unique_id.removeprefix(prefix), gateway_id
        )
        if migrated_device_id is not None:
            return f"{sensor_key}_{migrated_device_id}"

    return None


def migrate_legacy_sensor_links(
    links: list, aircons: Iterable["Device"]
) -> tuple[list, bool]:
    alias_to_unique_id = {
        aircon.alias: aircon.unique_id for aircon in aircons if aircon.alias
    }
    unique_ids = {aircon.unique_id for aircon in aircons}
    migrated_links = []
    changed = False

    for link in links:
        if not isinstance(link, dict):
            migrated_links.append(link)
            continue

        migrated_link = dict(link)
        climate_id = migrated_link.get("climate")
        if (
            isinstance(climate_id, str)
            and climate_id not in unique_ids
            and climate_id in alias_to_unique_id
        ):
            migrated_link["climate"] = alias_to_unique_id[climate_id]
            changed = True
        migrated_links.append(migrated_link)

    return migrated_links, changed


def build_aircon_device_name(alias: str) -> str:
    return alias if "空调" in alias else f"{alias} 空调"


def build_sensor_device_name(alias: str) -> str:
    return f"{alias} 传感器"


class Device:
    def __init__(self):
        self.alias: str = ""
        self.gateway_id: str = ""
        self.id: int = 0
        self.name: str = ""
        self.room_id: int = 0
        self.unit_id: int = 0
        self.mac: str = ""

    @property
    def unique_id(self):
        return build_device_unique_id(self.gateway_id, self.room_id, self.unit_id)


class AirConStatus:
    def __init__(
        self,
        current_temp: int | None = None,
        setted_temp: int | None = None,
        switch: EnumControl.Switch | None = None,
        air_flow: EnumControl.AirFlow | None = None,
        breathe: EnumControl.Breathe | None = None,
        fan_direction1: EnumControl.FanDirection | None = None,
        fan_direction2: EnumControl.FanDirection | None = None,
        humidity: EnumControl.Humidity | None = None,
        mode: EnumControl.Mode | None = None,
    ):
        self.current_temp: int | None = current_temp
        self.setted_temp: int | None = setted_temp
        self.switch: EnumControl.Switch | None = switch
        self.air_flow: EnumControl.AirFlow | None = air_flow
        self.breathe: EnumControl.Breathe | None = breathe
        self.fan_direction1: EnumControl.FanDirection | None = fan_direction1
        self.fan_direction2: EnumControl.FanDirection | None = fan_direction2
        self.humidity: EnumControl.Humidity | None = humidity
        self.mode: EnumControl.Mode | None = mode


class AirCon(Device):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.gateway_id = config.gateway_id
        self.auto_dry_mode: int = 0
        self.auto_mode: int = 0
        self.bath_room: bool = False
        self.new_air_con: bool = False
        self.cool_mode: int = 0
        self.dry_mode: int = 0
        self.fan_dire_auto: bool = False
        self.fan_direction1: EnumFanDirection = EnumFanDirection.FIX
        self.fan_direction2: EnumFanDirection = EnumFanDirection.FIX
        self.fan_volume: EnumFanVolume = EnumFanVolume.FIX
        self.fan_volume_auto: bool = False
        self.temp_set: bool = False
        self.hum_fresh_air_allow: bool = False
        self.three_d_fresh_allow: bool = False
        self.heat_mode: int = 0
        self.more_dry_mode: int = 0
        self.out_door_run_cond: EnumOutDoorRunCond = EnumOutDoorRunCond.VENT
        self.pre_heat_mode: int = 0
        self.relax_mode: int = 0
        self.sleep_mode: int = 0
        self.ventilation_mode: int = 0
        self.status: AirConStatus = AirConStatus()


def get_device_by_aircon(aircon: AirCon):
    if aircon.new_air_con:
        return EnumDevice.NEWAIRCON
    if aircon.bath_room:
        return EnumDevice.BATHROOM
    return EnumDevice.AIRCON


class Geothermic(Device):
    """do nothing"""


class Ventilation(Device):
    def __init__(self, config: Config | None = None):
        super().__init__()
        if config:
            self.config = config
            self.gateway_id = config.gateway_id
        self.is_small_vam: bool = False
        self.capability: int = 0
        self.status: VentilationStatus = VentilationStatus()


def get_device_by_vent(vent: Ventilation):
    if vent.is_small_vam:
        return EnumDevice.SMALL_VAM
    return EnumDevice.VENTILATION


class VentilationStatus:
    def __init__(
        self,
        switch: EnumControl.Switch | None = None,
        mode: EnumControl.Mode | None = None,
        air_flow: EnumControl.AirFlow | None = None,
        in_door_temp: int | None = None,
        out_door_temp: int | None = None,
        out_door_humidity: int | None = None,
        pm25: int | None = None,
    ):
        self.switch: EnumControl.Switch | None = switch
        self.mode: EnumControl.Mode | None = mode
        self.air_flow: EnumControl.AirFlow | None = air_flow
        self.in_door_temp: int | None = in_door_temp
        self.out_door_temp: int | None = out_door_temp
        self.out_door_humidity: int | None = out_door_humidity
        self.pm25: int | None = pm25


class HD(Device):
    def __init__(self, config: Config | None = None):
        super().__init__()
        if config:
            self.config = config
            self.gateway_id = config.gateway_id
        self.switch_enable: EnumControl.Switch | None = None
        self.night_energy_switch: EnumControl.Switch | None = None
        self.temperature_set: int | None = None
        self.status: HDStatus = HDStatus()


class HDStatus:
    def __init__(
        self,
        switch: EnumControl.Switch | None = None,
        cold_lower: float | None = None,
        cold_temperature: float | None = None,
        cold_upper: float | None = None,
        mute: EnumControl.Switch | None = None,
        mute_enable: EnumControl.Switch | None = None,
        night_energy_end_hour: int | None = None,
        night_energy_end_minute: int | None = None,
        night_energy_reduce_temp: int | None = None,
        night_energy_start_hour: int | None = None,
        night_energy_start_minute: int | None = None,
        night_energy_switch: EnumControl.Switch | None = None,
        outdoor_temp: float | None = None,
        preheat: int | None = None,
        switch_enable: EnumControl.Switch | None = None,
        temperature_set: int | None = None,
        warm_cold: int | None = None,
        warm_lower: float | None = None,
        warm_temperature: float | None = None,
        warm_upper: float | None = None,
    ):
        self.switch: EnumControl.Switch | None = switch
        self.cold_lower: float | None = cold_lower
        self.cold_temperature: float | None = cold_temperature
        self.cold_upper: float | None = cold_upper
        self.mute: EnumControl.Switch | None = mute
        self.mute_enable: EnumControl.Switch | None = mute_enable
        self.night_energy_end_hour: int | None = night_energy_end_hour
        self.night_energy_end_minute: int | None = night_energy_end_minute
        self.night_energy_reduce_temp: int | None = night_energy_reduce_temp
        self.night_energy_start_hour: int | None = night_energy_start_hour
        self.night_energy_start_minute: int | None = night_energy_start_minute
        self.night_energy_switch: EnumControl.Switch | None = night_energy_switch
        self.outdoor_temp: float | None = outdoor_temp
        self.preheat: int | None = preheat
        self.switch_enable: EnumControl.Switch | None = switch_enable
        self.temperature_set: int | None = temperature_set
        self.warm_cold: int | None = warm_cold
        self.warm_lower: float | None = warm_lower
        self.warm_temperature: float | None = warm_temperature
        self.warm_upper: float | None = warm_upper


STATUS_ATTR = [
    "mac",
    "type1",
    "type2",
    "start_time",
    "stop_time",
    "sensor_type",
    "temp",
    "humidity",
    "pm25",
    "co2",
    "voc",
    "tvoc",
    "hcho",
    "switch_on_off",
    "temp_upper",
    "temp_lower",
    "humidity_upper",
    "humidity_lower",
    "pm25_upper",
    "pm25_lower",
    "co2_upper",
    "co2_lower",
    "voc_lower",
    "tvoc_upper",
    "hcho_upper",
    "connected",
    "sleep_mode_count",
    "time_millis",
]

UNINITIALIZED_VALUE = -1000


class Sensor(Device):
    def __init__(self):
        Device.__init__(self)
        self.mac: str = ""
        self.type1: int = 0
        self.type2: int = 0
        self.start_time: int = 0
        self.stop_time: int = 0
        self.sensor_type: int = 0
        self.temp: int = 0
        self.humidity: int = 0
        self.pm25: int = 0
        self.co2: int = 0
        self.voc: int = 0
        self.tvoc: float = 0.0
        self.hcho: float = 0.0
        self.switch_on_off: bool = False
        self.temp_upper: int = 0
        self.temp_lower: int = 0
        self.humidity_upper: int = 0
        self.humidity_lower: int = 0
        self.pm25_upper: int = 0
        self.pm25_lower: int = 0
        self.co2_upper: int = 0
        self.co2_lower: int = 0
        self.voc_lower: int = 0
        self.tvoc_upper: float = 0.0
        self.hcho_upper: float = 0.0
        self.connected: bool = False
        self.sleep_mode_count: int = 0
        self.time_millis: float = time.time()


class Room:
    def __init__(self):
        self.air_con = None
        self.alias: str = ""
        self.geothermic: Geothermic | None = None
        self.hd: HD | None = None
        self.hd_room: bool = False
        self.sensor_room: bool = False
        self.icon: str = ""
        self.id: int = 0
        self.name: str = ""
        self.type: int = 0
        self.ventilation: Ventilation | None = None
