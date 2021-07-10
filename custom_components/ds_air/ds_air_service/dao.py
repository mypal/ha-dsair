import time

from .ctrl_enum import EnumOutDoorRunCond, EnumFanDirection, EnumFanVolume, EnumSwitch, EnumControl, EnumDevice, \
    EnumSensor


class Device:
    def __init__(self):
        self.alias: str = ''
        self.id: int = 0
        self.name: str = ''
        self.room_id: int = 0
        self.unit_id: int = 0


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
    elif aircon.bath_room:
        return EnumDevice.BATHROOM
    else:
        return EnumDevice.AIRCON


class Geothermic(Device):
    """do nothing"""


class Ventilation(Device):
    """do nothing"""


class HD(Device):
    def __init__(self):
        Device.__init__(self)
        self.switch: EnumSwitch


class Sensor(Device):
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
        self.alias: str = ''
        self.geothermic: Geothermic = Geothermic()
        self.hd_room: bool = False
        self.sensor_room: bool = False
        self.icon: str = ''
        self.id: int = 0
        self.name: str = ''
        self.type: int = 0
        self.ventilation: Ventilation = Ventilation()
