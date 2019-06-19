import struct

from .config import Config
from .dao import Room
from .base_bean import BaseBean
from .ctrl_enum import EnumDevice, EnumCmdType


def decoder(b):
    if b[0] != 2:
        return None

    length = struct.unpack('<H', b[1:3])[0]
    if length == 0 or len(b) - 4 < length or struct.unpack('<B', b[length + 3:length + 4])[0] != 3:
        if length == 0:
            print('heartbeat:' + b)
        else:
            print('exception:' + b)
        return None

    return result_factory(struct.unpack('<BHBBBBIBIBH' + str(length - 16) + 'sB', b[:length + 4])), b[length + 4:]


def result_factory(data):
    r1, length, r2, r3, subbody_ver, r4, cnt, dev_type, dev_id, need_ack, cmd_type, subbody, r5 = data
    result = None
    if dev_id == EnumDevice.SYSTEM.value[1]:
        if cmd_type == EnumCmdType.SYS_ACK.value:
            result = AckResult(cnt, EnumDevice.SYSTEM)
        elif cmd_type == EnumCmdType.SYS_CMD_RSP.value:
            result = CmdRspResult(cnt, EnumDevice.SYSTEM)
        elif cmd_type == EnumCmdType.SYS_TIME_SYNC.value:
            result = TimeSyncResult(cnt, EnumDevice.SYSTEM)
        elif cmd_type == EnumCmdType.SYS_ERR_CODE.value:
            result = ErrCodeResult(cnt, EnumDevice.SYSTEM)
        elif cmd_type == EnumCmdType.SYS_GET_WEATHER.value:
            result = GetWeatherResult(cnt, EnumDevice.SYSTEM)
        elif cmd_type == EnumCmdType.SYS_LOGIN.value:
            result = LoginResult(cnt, EnumDevice.SYSTEM)
        elif cmd_type == EnumCmdType.SYS_CHANGE_PW.value:
            result = ChangePWResult(cnt, EnumDevice.SYSTEM)
        elif cmd_type == EnumCmdType.SYS_GET_ROOM_INFO.value:
            result = GetRoomInfoResult(cnt, EnumDevice.SYSTEM)
        elif cmd_type == EnumCmdType.SYS_QUERY_SCHEDULE_SETTING.value:
            result = QueryScheduleSettingResult(cnt, EnumDevice.SYSTEM)
        elif cmd_type == EnumCmdType.SYS_QUERY_SCHEDULE_ID.value:
            result = QueryScheduleIDResult(cnt, EnumDevice.SYSTEM)
        elif cmd_type == EnumCmdType.SYS_HAND_SHAKE.value:
            result = HandShakeResult(cnt, EnumDevice.SYSTEM)
        elif cmd_type == EnumCmdType.SYS_CMD_TRANSFER.value:
            result = CmdTransferResult(cnt, EnumDevice.SYSTEM)
        elif cmd_type == EnumCmdType.SYS_QUERY_SCHEDULE_FINISH.value:
            result = QueryScheduleFinish(cnt, EnumDevice.SYSTEM)
        else:
            result = None

        result.subbody_ver = subbody_ver
        result.load_bytes(subbody)

    elif dev_id == EnumDevice.NEWAIRCON.value[1] or dev_id == EnumDevice.AIRCON.value[1] \
            or dev_id == EnumDevice.BATHROOM.value[1]:
        device = EnumDevice[(8, dev_id)]
        if cmd_type == EnumCmdType.STATUS_CHANGED.value:
            result = AirConStatusChangedResult(cnt, device)
        elif cmd_type == EnumCmdType.QUERY_STATUS.value:
            result = AirConQueryStatusResult(cnt, device)
        elif cmd_type == EnumCmdType.AIR_RECOMMENDED_INDOOR_TEMP.value:
            result = AirConRecommendedIndoorTempResult(cnt, device)
        elif cmd_type == EnumCmdType.AIR_CAPABILITY_QUERY.value:
            result = AirConCapabilityQueryResult(cnt, device)
        elif cmd_type == EnumCmdType.QUERY_SCENARIO_SETTING.value:
            result = AirConQueryScenarioSettingResult(cnt, device)

        result.subbody_ver = subbody_ver
        result.load_bytes(subbody)

    else:
        """ignore other device"""

    return result


class BaseResult(BaseBean):
    def __init__(self, cmd_id: int, targe: EnumDevice, cmd_type: EnumCmdType):
        BaseBean.__init__(self, cmd_id, targe, cmd_type)

    def load_bytes(self, b):
        """do nothing"""


class AckResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.SYS_ACK)

    def load_bytes(self, b):
        Config.is_new_version = struct.unpack('<B', b)[0] == 2


class CmdRspResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.SYS_CMD_RSP)
        self._cmdId = None
        self._code = None

    def load_bytes(self, b):
        self._cmdId, self._code = struct.unpack('<IB', b)

    @property
    def cmd_id(self):
        return self._cmdId

    @property
    def code(self):
        return self._code


class TimeSyncResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.SYS_TIME_SYNC)
        self._time = None

    def load_bytes(self, b):
        self._time = struct.unpack('<I', b)[0]

    @property
    def time(self):
        return self._time


class ErrCodeResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.SYS_ERR_CODE)
        self._code = None
        self._device = None
        self._room = None
        self._unit = None

    def load_bytes(self, b):
        dev_id, room, unit = struct.unpack('<iBB', b[:6])
        self._device = EnumDevice((8, dev_id))
        self._room = room
        self._unit = unit
        self._code = b[6:].decode('ASCII')

    @property
    def code(self):
        return self._code

    @property
    def device(self):
        return self._device

    @property
    def room(self):
        return self._room

    @property
    def unit(self):
        return self._unit


class GetWeatherResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.SYS_GET_WEATHER)
        self._condition = None
        self._humidity = None
        self._temp = None
        self._wind_dire = None
        self._wind_speed = None

    def load_bytes(self, b):
        self._condition, self._humidity, self._temp, self._wind_dire, self._wind_speed \
            = struct.unpack('<BBHBB', b)

    @property
    def condition(self):
        return self._condition

    @property
    def humidity(self):
        return self._humidity

    @property
    def temp(self):
        return self._temp

    @property
    def wind_dire(self):
        return self._wind_dire

    @property
    def wind_speed(self):
        return self._wind_speed


class LoginResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.SYS_LOGIN)
        self._status = None

    def load_bytes(self, b):
        self._status = struct.unpack('<BB', b)[1]

    @property
    def status(self):
        return self._status


class ChangePWResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.SYS_CHANGE_PW)
        self._status = None

    def load_bytes(self, b):
        self._status = struct.unpack('<B', b)[0]

    @property
    def status(self):
        return self._status


class GetRoomInfoResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.SYS_GET_ROOM_INFO)
        self._count = 0
        self._hds = []
        self._rooms = []

    def load_bytes(self, b):
        self._count, s = struct.unpack('<HB', b[:3])
        for i in range(s):
            room = Room()

    @property
    def count(self):
        return self._count

    @property
    def hds(self):
        return self._hds

    @property
    def rooms(self):
        return self._rooms


class QueryScheduleSettingResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.SYS_QUERY_SCHEDULE_SETTING)

    def load_bytes(self, b):
        """todo"""


class QueryScheduleIDResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.SYS_QUERY_SCHEDULE_ID)

    def load_bytes(self, b):
        """todo"""


class HandShakeResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.SYS_HAND_SHAKE)

    def load_bytes(self, b):
        """todo"""


class CmdTransferResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.SYS_CMD_TRANSFER)

    def load_bytes(self, b):
        """todo"""


class QueryScheduleFinish(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.SYS_QUERY_SCHEDULE_FINISH)

    def load_bytes(self, b):
        """todo"""


class AirConStatusChangedResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.STATUS_CHANGED)

    def load_bytes(self, b):
        """todo"""


class AirConQueryStatusResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.QUERY_STATUS)

    def load_bytes(self, b):
        """todo"""


class AirConRecommendedIndoorTempResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.AIR_RECOMMENDED_INDOOR_TEMP)

    def load_bytes(self, b):
        """todo"""


class AirConCapabilityQueryResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.AIR_CAPABILITY_QUERY)

    def load_bytes(self, b):
        """todo"""


class AirConQueryScenarioSettingResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.QUERY_SCENARIO_SETTING)

    def load_bytes(self, b):
        """todo"""
