import types

from .ctrl_enum import EnumOutDoorRunCond, EnumFanDirection, EnumFanVolume, EnumSwitch, EnumControl


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
    def __init__(self):
        self.current_temp = None
        self.setted_temp = None
        self.switch = None
        self.air_flow = None
        self.breathe = None
        self.fan_direction1 = None
        self.fan_direction2 = None
        self.humidity = None
        self.mode = None

    def __init__(self, current_temp: int = 0, setted_temp: int = 0,
                 switch: EnumControl.Switch = EnumControl.Switch.OFF,
                 air_flow: EnumControl.AirFlow = EnumControl.AirFlow.AUTO,
                 breathe: EnumControl.Breathe = EnumControl.Breathe.CLOSE,
                 fan_direction1: EnumControl.FanDirection = EnumControl.FanDirection.INVALID,
                 fan_direction2: EnumControl.FanDirection = EnumControl.FanDirection.INVALID,
                 humidity: EnumControl.Humidity = EnumControl.Humidity.CLOSE,
                 mode: EnumControl.Mode = EnumControl.Mode.AUTO):
        self.current_temp = current_temp      # type: int
        self.setted_temp = setted_temp        # type: int
        self.switch = switch                  # type: EnumControl.Switch
        self.air_flow = air_flow              # type: EnumControl.AirFlow
        self.breathe = breathe                # type: EnumControl.Breathe
        self.fan_direction1 = fan_direction1  # type: EnumControl.FanDirection
        self.fan_direction2 = fan_direction2  # type: EnumControl.FanDirection
        self.humidity = humidity              # type: EnumControl.Humidity
        self.mode = mode                      # type: EnumControl.Mode


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
        self.status: AirConStatus = None


class Geothermic(Device):
    """do nothing"""


class Ventilation(Device):
    """do nothing"""


class HD(Device):
    def __init__(self):
        Device.__init__(self)
        self.switch: EnumSwitch


class Room:
    def __init__(self):
        self.air_con = AirCon()
        self.alias: str
        self.geothermic: Geothermic
        self.hd_room: bool
        self.icon: str
        self.id: int
        self.name: str
        self.type: int
        self.ventilation: Ventilation
