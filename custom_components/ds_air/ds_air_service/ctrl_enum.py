from enum import Enum, IntEnum

from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    HVACAction,
    HVACMode,
)


class EnumCmdType(IntEnum):
    # 返回指令
    SYS_ACK = 1
    SYS_CMD_RSP = 2
    SYS_TIME_SYNC = 5
    SYS_ERR_CODE = 6
    SYS_GET_WEATHER = 7
    SYS_LOGIN = 16
    SYS_CHANGE_PW = 17
    SYS_GET_ROOM_INFO = 48
    SYS_GET_ROOM_INFO_V1 = 304
    SYS_SET_BASIC_ROOM_INFO = 49
    SYS_SCHEDULE_SETTING = 64
    SYS_QUERY_SCHEDULE_SETTING = 65
    SYS_QUERY_SCHEDULE = 69
    SYS_QUERY_SCHEDULE_ID = 66
    SYS_SCENARIO_CONTROL = 67
    SYS_QUERY_SCHEDULE_FINISH = 68
    SYS_HAND_SHAKE = 40960
    SYS_CMD_TRANSFER = 40961
    SYS_CMD_TRANSFER_TARGET_QUIT = 40962

    # 发送指令
    CONTROL = 1
    STATUS_CHANGED = 2
    QUERY_STATUS = 3
    AIR_RECOMMENDED_INDOOR_TEMP = 4
    AIR_CAPABILITY_QUERY = 6
    VAM_CAPABILITY_QUERY = 6
    AIR_SCENARIO_CONTROL = 32
    SCENARIO_SETTING = 33
    QUERY_SCENARIO_SETTING = 34

    # 金制新增
    SENSOR_INFO = 81
    SENSOR_SET_WARNING_LIMIT = 82
    SENSOR_SET_SLEEP_MODE_TIME = 83
    SENSOR_REMOVE = 84
    SENSOR_R0_RESET = 85
    SENSOR_RESET_INFO = 86
    SENSOR2_R0_RESET = 87
    SENSOR2_RESET_INFO = 88
    SENSOR2_INFO = 89
    SENSOR2_SET_WARNING_LIMIT = 90
    SENSOR2_STATUS = 91
    SENSOR2_CHECK = 92
    SENSOR2_HCHOANDVOC = 93
    SYS_FILTER_CLEAN_SIGN = 9
    SYS_FILTER_CLEAN_SIGN_RESET = 21
    SYS_GET_GW_INFO = 80
    SYS_SET_GW_INFO = 81
    SYS_AUTO_ADDRESS = 82
    SYS_RESTORE_SETTINGS = 83
    SYS_SET_DISTRIBUTOR_INFO = 88
    SYS_SET_AREA_INFO = 89
    SYS_RESTART = 40963
    SYS_TRANSFER_FAIL = 40964
    SYS_CHECK_NEW_VERSION = 85
    SYS_VERSION_UP_MODE = 86
    SYS_VERSION_UP_STUATUS = 87
    SYS_BIND_OR_UNBIND_SENSOR = 96
    SYS_GET_SENSOR_IN_ROOMS = 98
    SYS_GET_ALL_SENSOR_STATE = 99
    SYS_BIND_OR_UNBIND_SENSOR_MESH = 176
    SYS_GET_SENSOR_IN_ROOMS_MESH = 178
    SYS_GET_ALL_SENSOR_STATE_MESH = 179
    SYS_SET_SENSOR_MODE = 101
    SYS_CLEAN_FILTER = 100
    SYS_DEVICE_4_LSM = 15
    MESH_COMMON_RESPONSE = 3
    MESH_GET_BASIC_INFO = 131
    MESH_GET_NODE_LIST = 129
    MESH_UNBIND_TO_MESHID = 5
    MESH_RENAME = 6
    MESH_RESET = 7
    MESH_CHECK_NEW = 8
    MESH_SET_UPDATE_MODE = 9
    MESH_ERROR_CODE = 10
    MESH_BIND_TO_MESH = 8
    MESH_GET_WEATHER_INFO = 12
    MESH_SET_AREA_INFO = 13
    MESH_UPDATE_STATUS = 14
    LSM_GET_DETAIL = 1
    LSM_QUERY_STATUS = 2
    LSM_SET_STATUS = 3
    LSM_STATUS_CHANGED = 4
    LSM_DETAIL_COMPLEMENT = 7
    LSM_WIND_SET = 9
    LSM_WIND_INFO = 10
    RA0x01 = 1
    RA0x03 = 3
    RA0x04 = 4
    LSM_QUERY_CAPABILITY = 6
    VENT_QUERY_CAPABILITY = 6
    MESH_GET_BASIC_INFO_IP = 4
    SLEEP_SENSOR_LIST = 1
    SLEEP_SENSOR_DETAIL = 2
    ROOM_BIND_SS = 3
    REMOVE_SLEEP_SENSOR = 4
    BIND_UNBIND_SS = 5
    SS_LIGHT_SET = 6
    SS_LINK_SET = 7
    SS_ALARM_SETTING = 8
    SS_NICK_NAME_CHANGE = 9
    RA_CMD_TYPE = 4
    RA_CHANGE_STATUS = 3
    D3_INIT_FINISH = 58
    SECURITY_MONITOR_LIST = 10
    SECURITY_MONITOR_UNBIND_ROOM_LIST = 6
    SECURITY_MONITOR_DELETE = 9
    SECURITY_MONITOR_FIND = 5
    SECURITY_MONITOR_BIND = 7
    SECURITY_MONITOR_UNTYING = 8
    SECURITY_MONITOR_WARNING = 4
    SECURITY_MONITOR_LIST_INFO = 3
    SECURITY_MONITOR_UPDATE_INFO = 2
    AIR_CON_CAPABILITY_V2 = 35
    AIR_CON_CLEANING_V = 36
    INSTALL_CHECK = 192
    SYS_SCHEDULE_LIST_V3 = 194
    SYS_SCHEDULE_LIST_V3_1 = 450
    SYS_SCHEDULE_VRV_SETTING_V3 = 195
    SYS_SCHEDULE_SET_RA_V3 = 196
    SYS_SCHEDULE_QUERY_V3 = 197
    SYS_SCHEDULE_GET_RA_INFO_V3 = 198
    SYS_SCHEDULE_SETTING_VALID_V3 = 199
    SYS_SCHEDULE_SETTING_VERSION = 200
    SYS_SCHEDULE_QUERY_VERSION_V3 = 201
    SYS_SCHEDULE_QUERY_IS_ENABLE_V3 = 202
    VENTILATION_LINK_STATUS = 51
    VENTILATION_SENSOR_SETTING = 49
    VENTILATION_SENSOR_BIND_OR_DEL = 106
    VENTILATION_BIND_SENSOR = 107
    ALL_SENSOR_INFO = 96
    VENTILATION_FILTER_CLEAN = 10
    NEW_HD_DEVICE_INFO = 12
    NEW_HD_STATE_UPDATE = 13
    NEW_HD_STATE_SETTING = 14
    NEW_HD_NIGHT_ENERGY_SETTING = 15
    NEW_HD_QUERY_SCENARIO_SETTING = 85
    HCHO_GET_INFO = 150
    HCHO_SET_INFO = 151
    HCHO_GET_SENSORS = 152
    SYS_ADDRESS_ALLOCATION = 218
    SMALL_VAM_QUERY_AIR_QUALITY = 52
    SMALL_VAM_LINKAGE_CONTROL = 53
    SMALL_VAM_LINKAGE_STATUS = 54
    HUMIDIFIER_GET_ALL_DEVICES = 4
    HUMIDIFIER_DEVICE_STATUS = 2
    HUMIDIFIER_CONTROL = 3
    HUMIDIFIER_NOTIFY_IP_BOX_TO_RESCAN = 5
    HUMIDIFIER_UPDATE_NAME = 6
    HUMIDIFIER_BINDING_STATUS = 7
    HUMIDIFIER_DELETE = 8
    HUMIDIFIER_LINKAGE_VENTILATION_RESIDUAL_WORK = 9
    HUMIDIFIER_BINDING = 212
    HUMIDIFIER_CONDENSATION_PERMIT_GET = 216
    HUMIDIFIER_CONDENSATION_PERMIT_SET = 217
    AIR_NOT_EASILY_INFECTED_STATUS = 208
    AIR_NOT_EASILY_INFECTED_CONTROL = 209
    AIR_NOT_EASILY_INFECTED_SETTING_STATUS = 210
    AIR_NOT_EASILY_INFECTED_SETTING = 211


class EnumDevice(Enum):
    SYSTEM = (0, 0)
    AIRCON = (8, 18)
    GEOTHERMIC = (8, 19)
    VENTILATION = (8, 20)
    HD = (8, 22)
    NEWAIRCON = (8, 23)
    BATHROOM = (8, 24)
    # 新增
    SENSOR = (8, 25)
    SMALL_VAM = (8, 28)
    HUMIDIFIER = (10, 50)
    IP_MESH_COMMON = (10, 47)
    MESHID_MESH_COMMON = (12, 47)
    IP_LSM = (10, 33)
    MESHID_LSM = (12, 33)
    IP_MESH_SENSOR = (10, 25)
    MESHID_MESH_SENSOR = (12, 25)
    SLEEP_SENSOR = (10, 48)
    IP_RA = (10, 34)
    MESHID_RA = (12, 34)
    SECURITY_MONITOR = (8, 49)
    SMART_HCHO = (8, 50)


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


#_AIR_FLOW_NAME_LIST = ['最弱', '稍弱', '中等', '稍强', '最强', '自动']
_AIR_FLOW_NAME_LIST = [FAN_LOW, '稍弱', FAN_MEDIUM, '稍强', FAN_HIGH, FAN_AUTO]

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


_FAN_DIRECTION_LIST = ['INVALID', '➡️', '↘️', '⬇️', '↙️', '⬅️', '↔️', '🔄']


class Humidity(IntEnum):
    CLOSE = 0
    STEP1 = 1
    STEP2 = 2
    STEP3 = 3


class FreshAirHumidification(IntEnum):
    OFF = 0
    FRESH_AIR = 1
    HUM_FRESH_AIR = 2


class ThreeDFresh(IntEnum):
    CLOSE = 0
    WEAK = 1
    STRONG = 2
    AUTO = 3


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

# Legacy Mode Mapping
#_MODE_NAME_LIST = [HVACMode.COOL, HVACMode.DRY, HVACMode.FAN_ONLY, HVACMode.AUTO, HVACMode.HEAT,
#                   HVACMode.DRY, HVACMode.AUTO, HVACMode.HEAT_COOL, HVACMode.HEAT, HVACMode.DRY]

_MODE_NAME_LIST = [HVACMode.COOL, HVACMode.DRY, HVACMode.FAN_ONLY, HVACMode.AUTO, HVACMode.HEAT,
                   HVACMode.DRY, HVACMode.AUTO, HVACMode.AUTO, HVACMode.HEAT, HVACMode.DRY]
_MODE_ACTION_LIST = [HVACAction.COOLING, HVACAction.DRYING, HVACAction.FAN, None, HVACAction.HEATING,
                   HVACAction.DRYING, None, None, HVACAction.PREHEATING, HVACAction.DRYING]

class Switch(IntEnum):
    OFF = 0
    ON = 1


class Type(IntEnum):
    SWITCH = 1  # 0
    MODE = 2  # 1
    AIR_FLOW = 4  # 2
    CURRENT_TEMP = 8
    FRESH_AIR_HUMIDIFICATION = 8  # 3
    SETTED_TEMP = 16  # 4
    FAN_DIRECTION = 32  # 5
    HUMIDITY = 64  # 6
    BREATHE = 128  # 7
    FAN_DIRECTION_FB = 254  # 8
    FAN_DIRECTION_LR = 255  # 9
    SCENE_STATE = 253  # 10


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
    def get_action_name(idx):
        return _MODE_ACTION_LIST[idx]

    @staticmethod
    def get_mode_enum(name):
        return Mode(_MODE_NAME_LIST.index(name))

    @staticmethod
    def get_air_flow_name(idx):
        return _AIR_FLOW_NAME_LIST[idx]

    @staticmethod
    def get_air_flow_enum(name):
        return AirFlow(_AIR_FLOW_NAME_LIST.index(name))

    @staticmethod
    def get_fan_direction_name(idx):
        return _FAN_DIRECTION_LIST[idx]

    @staticmethod
    def get_fan_direction_enum(name):
        return FanDirection(_FAN_DIRECTION_LIST.index(name))


class EnumSensor:
    class LinkState(IntEnum):
        NO_LINKED = 0
        YES_LINKED = 1

    class Voc(IntEnum):
        STEP_1 = 1
        STEP_2 = 2
        STEP_3 = 4
        STEP_4 = 8
        STEP_UNUSE = 127

        def __str__(self):
            if self.value == EnumSensor.Voc.STEP_UNUSE:
                return "不可用"
            elif self.value == EnumSensor.Voc.STEP_1:
                return "优"
            elif self.value == EnumSensor.Voc.STEP_2:
                return "低"
            elif self.value == EnumSensor.Voc.STEP_3:
                return "中"
            elif self.value == EnumSensor.Voc.STEP_4:
                return "高"
