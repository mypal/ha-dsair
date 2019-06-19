from .ctrl_enum import FanDirection, FanVolume, OutDoorRunCond


class AirCon:
    def __init__(self):
        self.auto_dry_mode = 0
        self.auto_mode = 0
        self.bath_room = False
        self.cool_mode = 0
        self.dry_mode = 0
        self.fan_dire_auto = False
        self.fan_direction1 = FanDirection.FIX
        self.fan_direction2 = FanDirection.FIX
        self.fan_volume = FanVolume.NO
        self.fan_volume_auto = False
        self.heat_mode = 0
        self.more_dry_mode = 0
        self.new_air_con = False
        self.out_door_run_cond = OutDoorRunCond.VENT
        self.pre_heat_mode = 0
        self.relax_mode = 0
        self.sleep_mode = 0
        self.ventilation_mode = 0


class Geothermic:
    """todo"""


class Device:
    def __init__(self):
        self.alias = ''
        self.id = 0
        self.name = ''
        self.room_id = 0
        self.unit_id = 0


class Ventilation(Device):
    """do nothing"""


class Room:
    def __init__(self):
        self.air_con = AirCon()
        self.alias = ''
        self.geothermic = Geothermic()
        self.hd_room = False
        self.icon = ''
        self.id = 0
        self.name = ''
        self.type = 0
        self.ventilation = Ventilation()
