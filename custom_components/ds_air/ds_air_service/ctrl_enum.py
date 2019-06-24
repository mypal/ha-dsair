from enum import Enum, IntEnum

from components.climate.const import STATE_COOL, STATE_DRY, STATE_FAN_ONLY, STATE_AUTO, STATE_HEAT, STATE_ECO


class EnumCmdType(IntEnum):
    AIR_CAPABILITY_QUERY = 6
    AIR_RECOMMENDED_INDOOR_TEMP = 4
    AIR_SCENARIO_CONTROL = 32
    CONTROL = 1
    QUERY_SCENARIO_SETTING = 34
    QUERY_STATUS = 3
    SCENARIO_SETTING = 33
    STATUS_CHANGED = 2
    SYS_ACK = 1
    SYS_CHANGE_PW = 17
    SYS_CMD_RSP = 2
    SYS_CMD_TRANSFER = 40961
    SYS_CMD_TRANSFER_TARGET_QUIT = 40962
    SYS_ERR_CODE = 6
    SYS_GET_ROOM_INFO = 48
    SYS_GET_WEATHER = 7
    SYS_HAND_SHAKE = 40960
    SYS_LOGIN = 16
    SYS_QUERY_SCHEDULE_FINISH = 68
    SYS_QUERY_SCHEDULE_ID = 66
    SYS_QUERY_SCHEDULE_SETTING = 65
    SYS_SCENARIO_CONTROL = 67
    SYS_SCHEDULE_SETTING = 64
    SYS_SET_BASIC_ROOM_INFO = 49
    SYS_TIME_SYNC = 5


class EnumDevice(Enum):
    AIRCON = (8, 18)
    BATHROOM = (8, 24)
    GEOTHERMIC = (8, 19)
    HD = (8, 22)
    NEWAIRCON = (8, 23)
    SYSTEM = (0, 0)
    VENTILATION = (8, 20)

    @staticmethod
    def find(f, s):
        if f == 0:
            return EnumDevice.SYSTEM
        else:
            if s == 18:
                return EnumDevice.AIRCON
            elif s == 24:
                return EnumDevice.BATHROOM
            elif s == 19:
                return EnumDevice.GEOTHERMIC
            elif s == 22:
                return EnumDevice.HD
            elif s == 23:
                return EnumDevice.NEWAIRCON
            elif s == 20:
                return EnumDevice.VENTILATION
        return None


class EnumFanDirection(IntEnum):
    FIX = 0
    STEP_1 = 1
    STEP_2 = 2
    STEP_3 = 3
    STEP_4 = 4
    STEP_5 = 5


class EnumFanVolume(IntEnum):
    NO = 0
    FIX = 1
    STEP_2 = 2
    STEP_3 = 3
    STEP_4 = 4
    STEP_5 = 5
    STEPLESS = 7


class EnumOutDoorRunCond(IntEnum):
    COLD = 2
    HEAT = 1
    VENT = 0


class EnumSwitch(IntEnum):
    ON = 1
    OFF = 2


"""EnumControl"""


class AirFlow(IntEnum):
    SUPER_WEAK = 0
    WEAK = 1
    MIDDLE = 2
    STRONG = 3
    SUPER_STRONG = 4
    AUTO = 5


_AIR_FLOW_NAME_LIST = ['最弱', '稍弱', '中等', '稍强', '最强', '自动']


class Breathe(IntEnum):
    CLOSE = 0
    WEAK = 1
    STRONG = 2


class FanDirection(IntEnum):
    INVALID = 0
    P0 = 1  # 最右 最上
    P1 = 2
    P2 = 3
    P3 = 4
    P4 = 5  # 最左 最下
    AUTO = 6
    SWING = 7


class Humidity(IntEnum):
    CLOSE = 0
    STEP1 = 1
    STEP2 = 2
    STEP3 = 3


class Mode(IntEnum):
    COLD = 0
    DRY = 1
    VENTILATION = 2
    AUTO = 3
    HEAT = 4
    AUTODRY = 5
    RELAX = 6
    SLEEP = 7
    PREHEAT = 8
    MOREDRY = 9


_MODE_NAME_LIST = [STATE_COOL, STATE_DRY, STATE_FAN_ONLY, STATE_AUTO, STATE_HEAT, STATE_DRY, STATE_AUTO, STATE_ECO, STATE_HEAT, STATE_DRY]


class Switch(IntEnum):
    OFF = 0
    ON = 1


class Type(IntEnum):
    SWITCH = 1
    MODE = 2
    AIR_FLOW = 4
    CURRENT_TEMP = 8
    SETTED_TEMP = 16
    FAN_DIRECTION = 32
    HUMIDITY = 64
    BREATHE = 128


class EnumControl:
    Switch = Switch
    AirFlow = AirFlow
    Breathe = Breathe
    FanDirection = FanDirection
    Humidity = Humidity
    Mode = Mode
    Type = Type

    @staticmethod
    def get_mode_name(idx):
        return _MODE_NAME_LIST[idx]

    @staticmethod
    def get_air_flow_name(idx):
        return _AIR_FLOW_NAME_LIST[idx]
