from __future__ import annotations

import struct
from typing import TYPE_CHECKING

from .base_bean import BaseBean
from .config import Config
from .ctrl_enum import (
    EnumCmdType,
    EnumControl,
    EnumDevice,
    EnumFanDirection,
    EnumFanVolume,
    EnumOutDoorRunCond,
    EnumSensor,
    FreshAirHumidification,
    ThreeDFresh,
)
from .dao import (
    HD,
    UNINITIALIZED_VALUE,
    AirCon,
    AirConStatus,
    Device,
    Geothermic,
    Room,
    Sensor,
    Ventilation,
    get_device_by_aircon,
)
from .param import (
    AirConCapabilityQueryParam,
    AirConQueryStatusParam,
    AirConRecommendedIndoorTempParam,
    GetRoomInfoParam,
    Sensor2InfoParam,
)

if TYPE_CHECKING:
    from .service import Service


def decoder(b: bytes, config: Config):
    if b[0] != 2:
        return None, None

    length = struct.unpack("<H", b[1:3])[0]
    if (
        length == 0
        or len(b) - 4 < length
        or struct.unpack("<B", b[length + 3 : length + 4])[0] != 3
    ):
        if length == 0:
            return HeartbeatResult(), None
        return None, None

    return result_factory(
        struct.unpack("<BHBBBBIBIBH" + str(length - 16) + "sB", b[: length + 4]),
        config,
    ), b[length + 4 :]


def result_factory(data: tuple, config: Config):
    (
        r1,
        length,
        r2,
        r3,
        subbody_ver,
        r4,
        cnt,
        dev_type,
        dev_id,
        need_ack,
        cmd_type,
        subbody,
        r5,
    ) = data
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
        elif cmd_type == EnumCmdType.SYS_SCHEDULE_QUERY_VERSION_V3:
            result = ScheduleQueryVersionV3Result(cnt, EnumDevice.SYSTEM)
        elif cmd_type == EnumCmdType.SENSOR2_INFO:
            result = Sensor2InfoResult(cnt, EnumDevice.SYSTEM)
        else:
            result = UnknownResult(cnt, EnumDevice.SYSTEM, cmd_type)
    elif dev_id in (
        EnumDevice.NEWAIRCON.value[1],
        EnumDevice.AIRCON.value[1],
        EnumDevice.BATHROOM.value[1],
        EnumDevice.SENSOR.value[1],
    ):
        device = EnumDevice((8, dev_id))
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
        elif cmd_type == EnumCmdType.SENSOR2_INFO.value:
            result = Sensor2InfoResult(cnt, device)
        else:
            result = UnknownResult(cnt, device, cmd_type)
    else:
        """ignore other device"""
        result = UnknownResult(cnt, EnumDevice.SYSTEM, cmd_type)

    result.subbody_ver = subbody_ver
    result.load_bytes(subbody, config)

    return result


class Decode:
    def __init__(self, b):
        self._b = b
        self._pos = 0

    def read1(self):
        pos = self._pos
        s = struct.unpack("<B", self._b[pos : pos + 1])[0]
        pos += 1
        self._pos = pos
        return s

    def read2(self):
        pos = self._pos
        s = struct.unpack("<H", self._b[pos : pos + 2])[0]
        pos += 2
        self._pos = pos
        return s

    def read4(self):
        pos = self._pos
        s = struct.unpack("<I", self._b[pos : pos + 4])[0]
        pos += 4
        self._pos = pos
        return s

    def read(self, length: int):
        pos = self._pos
        s = self._b[pos : pos + length]
        pos += length
        self._pos = pos
        return s

    def read_utf(self, length: int):
        pos = self._pos
        try:
            s = self._b[pos : pos + length].decode("utf-8")
        except UnicodeDecodeError:
            s = None
        pos += length
        self._pos = pos
        return s


class BaseResult(BaseBean):
    def __init__(self, cmd_id: int, targe: EnumDevice, cmd_type: EnumCmdType):
        BaseBean.__init__(self, cmd_id, targe, cmd_type)

    def load_bytes(self, b: bytes, config: Config) -> None:
        """Do nothing"""

    def do(self, service: Service) -> None:
        """Do nothing"""


class HeartbeatResult(BaseResult):
    def __init__(self):
        BaseResult.__init__(self, 0, EnumDevice.SYSTEM, EnumCmdType.SYS_ACK)


class AckResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.SYS_ACK)

    def load_bytes(self, b: bytes, config: Config) -> None:
        config.is_new_version = struct.unpack("<B", b)[0] == 2


class ScheduleQueryVersionV3Result(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.SYS_ACK)


class Sensor2InfoResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.SENSOR2_INFO)
        self._count = 0
        self._mode = 0
        self._room_id = 0
        self._sensor_type = 0
        self._sensors: list[Sensor] = []

    def load_bytes(self, b: bytes, config: Config) -> None:
        data = Decode(b)
        self._mode = data.read1()
        count = data.read1()
        self._count = count
        while count > 0:
            self._room_id = data.read1()
            d = Decode(data.read(data.read1()))
            self._sensor_type = d.read1()
            unit_id = d.read1()
            sensor = Sensor()
            sensor.mac = d.read(6).hex()
            sensor.room_id = self._room_id
            sensor.unit_id = unit_id
            length = d.read1()
            sensor.alias = d.read_utf(length)
            sensor.name = sensor.alias
            sensor.type1 = d.read1()
            sensor.type2 = d.read1()
            humidity = UNINITIALIZED_VALUE
            hcho = UNINITIALIZED_VALUE
            temp = UNINITIALIZED_VALUE
            if (sensor.type1 & 1) == 1:
                temp = d.read2()
            if ((sensor.type1 >> 1) & 1) == 1:
                humidity = d.read2()
            pm25 = UNINITIALIZED_VALUE
            if (sensor.type1 >> 2) & 1 == 1:
                pm25 = d.read2()
            co2 = UNINITIALIZED_VALUE
            if (sensor.type1 >> 3) & 1 == 1:
                co2 = d.read2()
            voc = EnumSensor.Voc.STEP_UNUSE
            if (sensor.type1 >> 4) & 1 == 1:
                f = d.read1()
                voc = EnumSensor.Voc(f)
            tvoc = UNINITIALIZED_VALUE
            if (sensor.type1 >> 5) & 1 == 1:
                tvoc = d.read2()
            if (sensor.type1 >> 6) & 1 == 1:
                hcho = d.read2()
            switch_on_off = d.read1() == 1
            temp_upper = d.read2()
            temp_lower = d.read2()
            humidity_upper = d.read2()
            humidity_lower = d.read2()
            pm25_upper = d.read2()
            pm25_lower = d.read2()
            co2_upper = d.read2()
            co2_lower = d.read2()
            voc_lower = d.read1()
            tvoc_upper = d.read2()
            hcho_upper = d.read2()
            connected = d.read1() == 1
            sleep_mode_count = d.read1()
            sleep_mode_enable = False
            if sleep_mode_count > 0:
                sleep_mode_enable = d.read1() == 1
            sensor.sensor_type = self._sensor_type
            sensor.temp = temp
            sensor.humidity = humidity
            sensor.pm25 = pm25
            sensor.co2 = co2
            sensor.voc = voc
            if self._sensor_type == 3:
                sensor.tvoc = tvoc
                sensor.hcho = hcho
                sensor.tvoc_upper = tvoc_upper
                sensor.hcho_upper = hcho_upper
            sensor.switch_on_off = switch_on_off
            sensor.temp_upper = temp_upper
            sensor.temp_lower = temp_lower
            sensor.humidity_upper = humidity_upper
            sensor.humidity_lower = humidity_lower
            sensor.pm25_upper = pm25_upper
            sensor.pm25_lower = pm25_lower
            sensor.co2_upper = co2_upper
            sensor.co2_lower = co2_lower
            sensor.voc_lower = voc_lower
            sensor.connected = connected
            sensor.sleep_mode_count = sleep_mode_count
            self._sensors.append(sensor)
            count = count - 1

    def do(self, service: Service) -> None:
        service.set_sensors_status(self._sensors)

    @property
    def count(self):
        return self._count

    @property
    def mode(self):
        return self._mode

    @property
    def room_id(self):
        return self._room_id

    @property
    def sensor_type(self):
        return self._sensor_type

    @property
    def sensors(self):
        return self._sensors


class CmdRspResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.SYS_CMD_RSP)
        self._cmdId = None
        self._code = None

    def load_bytes(self, b: bytes, config: Config) -> None:
        self._cmdId, self._code = struct.unpack("<IB", b)

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

    def load_bytes(self, b: bytes, config: Config) -> None:
        self._time = struct.unpack("<I", b)[0]

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

    def load_bytes(self, b: bytes, config: Config) -> None:
        dev_id, room, unit = struct.unpack("<iBB", b[:6])
        self._device = EnumDevice((8, dev_id))
        self._room = room
        self._unit = unit
        self._code = b[6:].decode("ASCII")

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

    def load_bytes(self, b: bytes, config: Config) -> None:
        (
            self._condition,
            self._humidity,
            self._temp,
            self._wind_dire,
            self._wind_speed,
        ) = struct.unpack("<BBHBB", b)

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

    def load_bytes(self, b: bytes, config: Config) -> None:
        self._status = struct.unpack("<BB", b)[1]

    @property
    def status(self):
        return self._status


class ChangePWResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.SYS_CHANGE_PW)
        self._status = None

    def load_bytes(self, b: bytes, config: Config) -> None:
        self._status = struct.unpack("<B", b)[0]

    @property
    def status(self):
        return self._status


class GetRoomInfoResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.SYS_GET_ROOM_INFO)
        self._count: int = 0
        self._hds: list[HD] = []
        self._sensors: list[Sensor] = []
        self._rooms: list[Room] = []

    def load_bytes(self, b: bytes, config: Config) -> None:
        ver_flag = 1
        d = Decode(b)
        self._count = d.read2()
        room_count = d.read1()
        for _i in range(room_count):
            room = Room()
            room.id = d.read2()
            if self.subbody_ver == 1:
                ver_flag = d.read1()
            if ver_flag != 2:
                length = d.read1()
                room.name = d.read_utf(length)
                length = d.read1()
                room.alias = d.read_utf(length)
                length = d.read1()
                room.icon = d.read_utf(length)
            unit_count = d.read2()
            for _j in range(unit_count):
                device = EnumDevice((8, d.read4()))
                device_count = d.read2()
                for unit_id in range(device_count):
                    if device in (
                        EnumDevice.AIRCON,
                        EnumDevice.NEWAIRCON,
                        EnumDevice.BATHROOM,
                    ):
                        dev = AirCon(config)
                        room.air_con = dev
                        dev.new_air_con = device == EnumDevice.NEWAIRCON
                        dev.bath_room = device == EnumDevice.BATHROOM
                    elif device == EnumDevice.GEOTHERMIC:
                        dev = Geothermic()
                        room.geothermic = dev
                    elif device == EnumDevice.HD:
                        dev = HD()
                        self.hds.append(dev)
                        room.hd_room = True
                        room.hd = dev
                    elif device == EnumDevice.SENSOR:
                        dev = Sensor()
                        self.sensors.append(dev)
                        room.sensor_room = True
                    elif device in (EnumDevice.VENTILATION, EnumDevice.SMALL_VAM):
                        dev = Ventilation()
                        room.ventilation = dev
                        dev.is_small_vam = device == EnumDevice.SMALL_VAM
                    else:
                        dev = Device()
                    dev.room_id = room.id
                    dev.unit_id = unit_id
                    if ver_flag > 2:
                        length = d.read1()
                        dev.name = d.read_utf(length)
                        length = d.read1()
                        dev.alias = d.read_utf(length)
                        if dev.alias is None:
                            dev.alias = room.alias
            self.rooms.append(room)

    def do(self, service: Service) -> None:
        service.set_rooms(self.rooms)
        service.send_msg(AirConRecommendedIndoorTempParam())
        service.set_sensors(self.sensors)

        aircons = []
        new_aircons = []
        bathrooms = []
        for room in service.get_rooms():
            if room.air_con is not None:
                room.air_con.alias = room.alias
                if room.air_con.new_air_con:
                    new_aircons.append(room.air_con)
                elif room.air_con.bath_room:
                    bathrooms.append(room.air_con)
                else:
                    aircons.append(room.air_con)

        p = AirConCapabilityQueryParam()
        p.aircons = aircons
        p.target = EnumDevice.AIRCON
        service.send_msg(p)
        p = AirConCapabilityQueryParam()
        p.aircons = new_aircons
        p.target = EnumDevice.NEWAIRCON
        service.send_msg(p)
        p = AirConCapabilityQueryParam()
        p.aircons = bathrooms
        p.target = EnumDevice.BATHROOM
        service.send_msg(p)

    @property
    def count(self):
        return self._count

    @property
    def hds(self):
        return self._hds

    @property
    def rooms(self):
        return self._rooms

    @property
    def sensors(self):
        return self._sensors


class QueryScheduleSettingResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(
            self, cmd_id, target, EnumCmdType.SYS_QUERY_SCHEDULE_SETTING
        )

    def load_bytes(self, b: bytes, config: Config) -> None:
        """Todo"""


class QueryScheduleIDResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.SYS_QUERY_SCHEDULE_ID)

    def load_bytes(self, b: bytes, config: Config) -> None:
        """Todo"""


class HandShakeResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.SYS_HAND_SHAKE)
        self._time: str = ""

    def load_bytes(self, b: bytes, config: Config) -> None:
        d = Decode(b)
        self._time = d.read_utf(14)

    def do(self, service: Service) -> None:
        p = GetRoomInfoParam()
        p.room_ids.append(0xFFFF)

        service.send_msg(p)
        service.send_msg(Sensor2InfoParam())


class GetGWInfoResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.SYS_HAND_SHAKE)
        self._time: str = ""

    def load_bytes(self, b: bytes, config: Config) -> None:
        """Todo"""

    def do(self, service: Service) -> None:
        """Todo"""


class CmdTransferResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.SYS_CMD_TRANSFER)

    def load_bytes(self, b: bytes, config: Config) -> None:
        """Todo"""


class QueryScheduleFinish(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.SYS_QUERY_SCHEDULE_FINISH)

    def load_bytes(self, b: bytes, config: Config) -> None:
        """Todo"""


class AirConStatusChangedResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.STATUS_CHANGED)
        self._room: int = 0
        self._unit: int = 0
        self._status: AirConStatus = AirConStatus()

    def load_bytes(self, b: bytes, config: Config) -> None:
        d = Decode(b)
        self._room = d.read1()
        self._unit = d.read1()
        status = self._status
        flag = d.read1()
        if flag & EnumControl.Type.SWITCH:
            status.switch = EnumControl.Switch(d.read1())
        if flag & EnumControl.Type.MODE:
            status.mode = EnumControl.Mode(d.read1())
        if flag & EnumControl.Type.AIR_FLOW:
            status.air_flow = EnumControl.AirFlow(d.read1())
        if flag & EnumControl.Type.CURRENT_TEMP:
            status.current_temp = d.read2()
        if flag & EnumControl.Type.SETTED_TEMP:
            status.setted_temp = d.read2()
        if config.is_new_version:
            if flag & EnumControl.Type.FAN_DIRECTION:
                direction = d.read1()
                status.fan_direction1 = EnumControl.FanDirection(direction & 0xF)
                status.fan_direction2 = EnumControl.FanDirection((direction >> 4) & 0xF)

    def do(self, service: Service) -> None:
        service.update_aircon(self.target, self._room, self._unit, status=self._status)


class AirConQueryStatusResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.QUERY_STATUS)
        self.unit = 0
        self.room = 0
        self.current_temp = 0
        self.setted_temp = 0
        self.switch = EnumControl.Switch.OFF
        self.air_flow = EnumControl.AirFlow.AUTO
        self.breathe = EnumControl.Breathe.CLOSE
        self.fan_direction1 = EnumControl.FanDirection.INVALID
        self.fan_direction2 = EnumControl.FanDirection.INVALID
        self.humidity = EnumControl.Humidity.CLOSE
        self.mode = EnumControl.Mode.AUTO
        self.hum_allow = False
        self.fresh_air_allow = False
        self.fresh_air_humidification = FreshAirHumidification.OFF
        self.three_d_fresh = ThreeDFresh.CLOSE

    def load_bytes(self, b: bytes, config: Config) -> None:
        d = Decode(b)
        self.room = d.read1()
        self.unit = d.read1()
        flag = d.read1()
        if flag & 1:
            self.switch = EnumControl.Switch(d.read1())
        if flag >> 1 & 1:
            self.mode = EnumControl.Mode(d.read1())
        if flag >> 2 & 1:
            self.air_flow = EnumControl.AirFlow(d.read1())
        if config.is_c611:
            if flag >> 3 & 1:
                bt = d.read1()
                self.hum_allow = bt & 8 == 8
                self.fresh_air_allow = bt & 4 == 4
                self.fresh_air_humidification = FreshAirHumidification(bt & 3)

            if flag >> 4 & 1:
                self.setted_temp = d.read2()
            if config.is_new_version:
                if flag >> 5 & 1:
                    b = d.read1()
                    self.fan_direction1 = EnumControl.FanDirection(b & 0xF)
                    self.fan_direction2 = EnumControl.FanDirection(b >> 4 & 0xF)
                if flag >> 6 & 1:
                    self.humidity = EnumControl.Humidity(d.read1())
                if self.target == EnumDevice.BATHROOM:
                    if flag >> 7 & 1:
                        self.breathe = EnumControl.Breathe(d.read1())
                elif self.target == EnumDevice.AIRCON:
                    if flag >> 7 & 1 == 1:
                        self.three_d_fresh = ThreeDFresh(d.read1())
        else:
            if flag >> 3 & 1:
                self.current_temp = d.read2()
            if flag >> 4 & 1:
                self.setted_temp = d.read2()
            if config.is_new_version:
                if flag >> 5 & 1:
                    b = d.read1()
                    self.fan_direction1 = EnumControl.FanDirection(b & 0xF)
                    self.fan_direction2 = EnumControl.FanDirection(b >> 4 & 0xF)
                if self.target == EnumDevice.NEWAIRCON:
                    if flag >> 6 & 1:
                        self.humidity = EnumControl.Humidity(d.read1())
                elif flag >> 7 & 1:
                    self.breathe = EnumControl.Breathe(d.read1())

    def do(self, service: Service) -> None:
        status = AirConStatus(
            self.current_temp,
            self.setted_temp,
            self.switch,
            self.air_flow,
            self.breathe,
            self.fan_direction1,
            self.fan_direction2,
            self.humidity,
            self.mode,
        )
        service.set_aircon_status(self.target, self.room, self.unit, status)


class AirConRecommendedIndoorTempResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(
            self, cmd_id, target, EnumCmdType.AIR_RECOMMENDED_INDOOR_TEMP
        )
        self._temp: int = 0
        self._outdoor_temp: int = 0

    def load_bytes(self, b: bytes, config: Config) -> None:
        d = Decode(b)
        self._temp = d.read2()
        self._outdoor_temp = d.read2()

    @property
    def temp(self):
        return self._temp

    @property
    def outdoor_temp(self):
        return self._outdoor_temp


class AirConCapabilityQueryResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.AIR_CAPABILITY_QUERY)
        self._air_cons: list[AirCon] = []

    def load_bytes(self, b: bytes, config: Config) -> None:
        d = Decode(b)
        room_size = d.read1()
        for _i in range(room_size):
            room_id = d.read1()
            unit_size = d.read1()
            for _j in range(unit_size):
                aircon = AirCon(config)
                aircon.unit_id = d.read1()
                aircon.room_id = room_id
                aircon.new_air_con = self.target == EnumDevice.NEWAIRCON
                aircon.bath_room = self.target == EnumDevice.BATHROOM
                flag = d.read1()
                aircon.fan_volume = EnumFanVolume(flag >> 5 & 0x7)
                aircon.dry_mode = flag >> 4 & 1
                aircon.auto_mode = flag >> 3 & 1
                aircon.heat_mode = flag >> 2 & 1
                aircon.cool_mode = flag >> 1 & 1
                aircon.ventilation_mode = flag & 1
                if config.is_new_version:
                    flag = d.read1()
                    if flag & 1:
                        aircon.fan_direction1 = EnumFanDirection.STEP_5
                    else:
                        aircon.fan_direction1 = EnumFanDirection.FIX

                    if flag >> 1 & 1:
                        aircon.fan_direction2 = EnumFanDirection.STEP_5
                    else:
                        aircon.fan_direction2 = EnumFanDirection.FIX

                    aircon.fan_dire_auto = flag >> 2 & 1
                    aircon.fan_volume_auto = flag >> 3 & 1
                    aircon.temp_set = flag >> 4 & 1
                    aircon.hum_fresh_air_allow = (flag >> 5 & 1) & (flag >> 6 & 1)
                    aircon.three_d_fresh_allow = flag >> 7 & 1

                    flag = d.read1()
                    aircon.out_door_run_cond = EnumOutDoorRunCond(flag >> 6 & 3)
                    aircon.more_dry_mode = flag >> 4 & 1
                    aircon.pre_heat_mode = flag >> 3 & 1
                    aircon.auto_dry_mode = flag >> 2 & 1
                    aircon.relax_mode = flag >> 1 & 1
                    aircon.sleep_mode = flag & 1
                else:
                    d.read1()
                self._air_cons.append(aircon)

    def do(self, service: Service) -> None:
        if service.is_ready():
            if len(self._air_cons):
                for i in self._air_cons:
                    service.update_aircon(
                        get_device_by_aircon(i), i.room_id, i.unit_id, aircon=i
                    )
        else:
            for i in self._air_cons:
                p = AirConQueryStatusParam()
                p.target = self.target
                p.device = i
                service.send_msg(p)
            service.set_device(self.target, self._air_cons)

    @property
    def aircons(self):
        return self._air_cons


class AirConQueryScenarioSettingResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice):
        BaseResult.__init__(self, cmd_id, target, EnumCmdType.QUERY_SCENARIO_SETTING)

    def load_bytes(self, b: bytes, config: Config) -> None:
        """Todo"""


class UnknownResult(BaseResult):
    def __init__(self, cmd_id: int, target: EnumDevice, cmd_type: EnumCmdType):
        BaseResult.__init__(self, cmd_id, target, cmd_type)
        self._subbody = ""

    def load_bytes(self, b: bytes, config: Config) -> None:
        self._subbody = struct.pack("<" + str(len(b)) + "s", b).hex()

    @property
    def subbody(self):
        return self._subbody
