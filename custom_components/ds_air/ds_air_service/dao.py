import time
from typing import Optional

from .ctrl_enum import EnumOutDoorRunCond, EnumFanDirection, EnumFanVolume, EnumSwitch, EnumControl, EnumDevice


class Device:
    def __init__(self):
        self.alias: str = ""
        self.id: int = 0
        self.name: str = ""
        self.room_id: int = 0
        self.unit_id: int = 0
        self.mac: str = ""

    @property
    def unique_id(self):
        return "daikin_%d_%d" % (self.room_id, self.unit_id)


def _nothing():
    """do nothing"""


class AirConStatus:
    def __init__(self, current_temp: int = None, setted_temp: int = None,
                 switch: EnumControl.Switch = None,
                 air_flow: EnumControl.AirFlow = None,
                 breathe: EnumControl.Breathe = None,
                 fan_direction1: EnumControl.FanDirection = None,
                 fan_direction2: EnumControl.FanDirection = None,
                 humidity: EnumControl.Humidity = None,
                 mode: EnumControl.Mode = None):
        self.current_temp = current_temp  # type: int
        self.setted_temp = setted_temp  # type: int
        self.switch = switch  # type: EnumControl.Switch
        self.air_flow = air_flow  # type: EnumControl.AirFlow
        self.breathe = breathe  # type: EnumControl.Breathe
        self.fan_direction1 = fan_direction1  # type: EnumControl.FanDirection
        self.fan_direction2 = fan_direction2  # type: EnumControl.FanDirection
        self.humidity = humidity  # type: EnumControl.Humidity
        self.mode = mode  # type: EnumControl.Mode


class AirCon(Device):
    def __init__(self):
        super().__init__()
        self.auto_dry_mode = 0  # type: int
        self.auto_mode = 0  # type: int
        self.bath_room = False  # type: bool
        self.new_air_con = False  # type: bool
        self.cool_mode = 0  # type: int
        self.dry_mode = 0  # type: int
        self.fan_dire_auto = False  # type: bool
        self.fan_direction1 = EnumFanDirection.FIX  # type: EnumFanDirection
        self.fan_direction2 = EnumFanDirection.FIX  # type: EnumFanDirection
        self.fan_volume = EnumFanVolume.FIX  # type: EnumFanVolume
        self.fan_volume_auto = False  # type: bool
        self.temp_set = False  # type: bool
        self.hum_fresh_air_allow = False  # type: bool
        self.three_d_fresh_allow = False  # type: bool
        self.heat_mode = 0  # type: int
        self.more_dry_mode = 0  # type: int
        self.out_door_run_cond = EnumOutDoorRunCond.VENT  # type: EnumOutDoorRunCond
        self.pre_heat_mode = 0  # type: int
        self.relax_mode = 0  # type: int
        self.sleep_mode = 0  # type: int
        self.ventilation_mode = 0  # type: int
        self.status = AirConStatus()  # type: AirConStatus


def get_device_by_aircon(aircon: AirCon):
    if aircon.new_air_con:
        return EnumDevice.NEWAIRCON
    elif aircon.bath_room:
        return EnumDevice.BATHROOM
    else:
        return EnumDevice.AIRCON


class Geothermic(Device):
    """do nothing"""


class Ventilation(Device):
    def __init__(self):
        Device.__init__(self)
        self.is_small_vam = False  # type: bool


class HD(Device):
    def __init__(self):
        Device.__init__(self)
        self.switch: EnumSwitch


class Sensor(Device):
    STATUS_ATTR = ["mac", "type1", "type2", "start_time", "stop_time", "sensor_type", "temp", "humidity", "pm25", "co2",
                   "voc", "tvoc", "hcho", "switch_on_off", "temp_upper", "temp_lower", "humidity_upper",
                   "humidity_lower", "pm25_upper", "pm25_lower", "co2_upper", "co2_lower", "voc_lower", "tvoc_upper",
                   "hcho_upper", "connected", "sleep_mode_count", "time_millis"]

    UNINITIALIZED_VALUE = -1000

    def __init__(self):
        Device.__init__(self)
        self.mac: str = ''
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
        self.alias = ''  # type: str
        self.geothermic = None  # type: Optional[Geothermic]
        self.hd = None  # type: Optional[HD]
        self.hd_room = False  # type: bool
        self.sensor_room = False  # type: bool
        self.icon = ''  # type: str
        self.id = 0  # type: int
        self.name = ''  # type: str
        self.type = 0  # type: int
        self.ventilation = Ventilation()  # type: Optional[Ventilation]
