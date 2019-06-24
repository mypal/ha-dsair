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
        self.status_change_hook = _nothing    # type: types.FunctionType


class AirCon(Device):
    def __init__(self):
        Device.__init__(self)
        self.auto_dry_mode: int
        self.auto_mode: int
        self.bath_room: bool
        self.cool_mode: int
        self.dry_mode: int
        self.fan_dire_auto: bool
        self.fan_direction1: EnumFanDirection
        self.fan_direction2: EnumFanDirection
        self.fan_volume: EnumFanVolume
        self.fan_volume_auto: bool
        self.heat_mode: int
        self.more_dry_mode: int
        self.new_air_con: bool
        self.out_door_run_cond: EnumOutDoorRunCond
        self.pre_heat_mode: int
        self.relax_mode: int
        self.sleep_mode: int
        self.ventilation_mode: int
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
