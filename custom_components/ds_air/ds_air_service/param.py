import struct

from .base_bean import BaseBean
from .config import Config
from .ctrl_enum import (
    EnumCmdType,
    EnumControl,
    EnumDevice,
    EnumFanDirection,
    EnumFanVolume,
    EnumSwitch,
)
from typing import Literal

from .dao import (
    AirCon,
    AirConStatus,
    HD,
    HDStatus,
    Ventilation,
    VentilationStatus,
    get_device_by_aircon,
    get_device_by_vent,
)


class Encode:
    def __init__(self):
        self._fmt = "<"
        self._len = 0
        self._list = []

    def write1(self, d):
        self._fmt += "B"
        self._len += 1
        self._list.append(int(d))

    def write2(self, d):
        self._fmt += "H"
        self._len += 2
        self._list.append(int(d))

    def write4(self, d):
        self._fmt += "I"
        self._len += 4
        self._list.append(int(d))

    def writes(self, d):
        if isinstance(d, str):
            d = d.encode("utf-8")
        self._fmt += str(len(d)) + "s"
        self._len += len(d)
        self._list.append(d)

    def write_bytes(self, d: bytes | bytearray | list):
        if isinstance(d, (bytearray, list)):
            d = bytes(d)
        elif isinstance(d, str):
            d = d.encode("utf-8")
        self._fmt += str(len(d)) + "s"
        self._len += len(d)
        self._list.append(d)

    def pack(self, rewrite_length: bool = True) -> bytes:
        if rewrite_length:
            self._list[1] = self._len - 4
        return struct.pack(self._fmt, *self._list)

    @property
    def len(self):
        return self._len


class Param(BaseBean):
    cnt = 0

    def __init__(
        self, device_type: EnumDevice, cmd_type: EnumCmdType, has_result: bool
    ):
        Param.cnt += 1
        BaseBean.__init__(self, Param.cnt, device_type, cmd_type)
        self._has_result = has_result

    def generate_subbody(self, s: Encode, config: Config) -> None:
        return

    def to_string(self, config: Config) -> bytes:
        s = Encode()
        s.write1(2)  # 0 保留字
        s.write2(16)  # 1~2 长度，不含首尾保留字及长度本身
        s.write1(13)  # 3 保留字
        s.write1(0)  # 4 保留字
        s.write1(self.subbody_ver)  # 5 子体版本
        s.write1(0)  # 6 保留字
        s.write4(self.cmd_id)  # 7~10 自增命令ID
        s.write1(self.target.value[0])  # 11 设备类型
        s.write4(self.target.value[1])  # 12~15 设备类型id
        s.write1(self.need_ack)  # 16 是否需要ack
        s.write2(self.cmd_type.value)  # 17~18 命令类型id
        self.generate_subbody(s, config)
        s.write1(3)  # 最后一位 保留字
        return s.pack()

    @property
    def has_result(self):
        return self._has_result


class HeartbeatParam(Param):
    def __init__(self):
        super().__init__(EnumDevice.SYSTEM, EnumCmdType.SYS_ACK, False)

    def to_string(self, config: Config) -> bytes:
        s = Encode()
        s.write1(2)
        s.write2(0)
        s.write1(3)
        return s.pack()


class SystemParam(Param):
    def __init__(self, cmd_type, has_result):
        Param.__init__(self, EnumDevice.SYSTEM, cmd_type, has_result)


class HandShakeParam(SystemParam):
    def __init__(self):
        SystemParam.__init__(self, EnumCmdType.SYS_HAND_SHAKE, True)


class GetGWInfoParam(SystemParam):
    def __init__(self):
        SystemParam.__init__(self, EnumCmdType.SYS_GET_GW_INFO, True)


class GetRoomInfoParam(SystemParam):
    def __init__(
        self,
        cmd_type: Literal[
            EnumCmdType.SYS_GET_ROOM_INFO, EnumCmdType.SYS_GET_ROOM_INFO_V1
        ] = EnumCmdType.SYS_GET_ROOM_INFO,
    ):
        SystemParam.__init__(self, cmd_type, True)
        self._room_ids: list[int] = []
        self.type: int = 1
        self.subbody_ver: int = 1

    def generate_subbody(self, s: Encode, config: Config) -> None:
        s.write1(len(self.room_ids))
        for r in self.room_ids:
            s.write2(r)
            if self.subbody_ver == 1 and r != 65535:
                s.write1(self.type)

    @property
    def room_ids(self):
        return self._room_ids


class Sensor2InfoParam(Param):
    def __init__(self):
        # todo: 未兼容固件低于02.04.00的网关
        Param.__init__(self, EnumDevice.SENSOR, EnumCmdType.SENSOR2_INFO, True)
        # self._sensor_type: int = 1

    def generate_subbody(self, s: Encode, config: Config) -> None:
        s.write1(255)


class AirconParam(Param):
    def __init__(self, cmd_cype, has_result):
        Param.__init__(self, EnumDevice.AIRCON, cmd_cype, has_result)


class AirConCapabilityQueryParam(AirconParam):
    def __init__(self):
        AirconParam.__init__(self, EnumCmdType.AIR_CAPABILITY_QUERY, True)
        self._aircons: list[AirCon] = []

    def generate_subbody(self, s: Encode, config: Config) -> None:
        s.write1(len(self._aircons))
        for i in self._aircons:
            s.write1(i.room_id)
            s.write1(1)
            s.write1(0)

    @property
    def aircons(self):
        return self._aircons

    @aircons.setter
    def aircons(self, value):
        self._aircons = value


class AirConRecommendedIndoorTempParam(AirconParam):
    def __init__(self):
        super().__init__(EnumCmdType.AIR_RECOMMENDED_INDOOR_TEMP, True)


class AirConQueryStatusParam(AirconParam):
    def __init__(self):
        super().__init__(EnumCmdType.QUERY_STATUS, True)
        self._device: AirCon | None = None

    def generate_subbody(self, s: Encode, config: Config) -> None:
        s.write1(self._device.room_id)
        s.write1(self._device.unit_id)
        t = EnumControl.Type
        flag = t.SWITCH | t.MODE | t.SETTED_TEMP
        dev = self.device
        if dev is not None:
            if dev.fan_volume != EnumFanVolume.NO:
                flag = flag | t.AIR_FLOW
            if config.is_new_version:
                if EnumFanDirection.FIX not in (dev.fan_direction1, dev.fan_direction2):
                    flag = flag | t.FAN_DIRECTION
                if dev.bath_room or dev.three_d_fresh_allow:
                    flag = flag | t.BREATHE
                flag = flag | t.HUMIDITY
            if dev.hum_fresh_air_allow:
                flag = flag | t.FRESH_AIR_HUMIDIFICATION
        s.write1(flag)

    @property
    def device(self):
        return self._device

    @device.setter
    def device(self, v: AirCon):
        self._device = v


class MeshGetBasicInfoParam(Param):
    def __init__(self, room_id: int = 1, unit_id: int = 1):
        super().__init__(EnumDevice.MESHID_MESH_COMMON, EnumCmdType.MESH_GET_BASIC_INFO, True)
        self.room_id = room_id
        self.unit_id = unit_id

    def generate_subbody(self, s: Encode, config: Config) -> None:
        s.write1(self.room_id)
        s.write1(self.unit_id)


class MeshNodeQueryParam(SystemParam):
    def __init__(self):
        super().__init__(EnumCmdType.SYS_TIME_SYNC, True)

    def generate_subbody(self, s: Encode, config: Config) -> None:
        s.write1(0x01)
        s.write1(0xFF)
        s.write1(0xFF)


class MeshGetNodeListParam(Param):
    def __init__(self):
        super().__init__(EnumDevice.MESHID_MESH_COMMON, EnumCmdType.MESH_GET_NODE_LIST, True)


class MeshRAInfoParam(Param):
    """Query Mesh RA device status (cmd 1 = RA.INFO, target MESHID_RA).

    Matches the official app's RAInfoDTO: subbody [34][1][mac][softId].
    """
    def __init__(self, mac: str = "", soft_id: str = ""):
        super().__init__(EnumDevice.MESHID_RA, EnumCmdType.RA0x01, True)
        self.mac = mac
        self.soft_id = soft_id
        self.subbody_ver = 0

    def generate_subbody(self, s: Encode, config: Config) -> None:
        s.write1(0x22)                    # 34
        s.write1(0x01)                    # 1
        mac_str = self.mac or "00:00:00:00:00:00"
        mac_clean = mac_str.replace(":", "").replace("-", "")
        try:
            mac_bytes = bytes.fromhex(mac_clean) if len(mac_clean) == 12 else bytes(6)
        except Exception:
            mac_bytes = bytes(6)
        s.write_bytes(mac_bytes)
        soft_clean = (self.soft_id or "").replace(":", "").replace("-", "")
        try:
            soft_bytes = bytes.fromhex(soft_clean) if soft_clean else b""
        except Exception:
            soft_bytes = b""
        s.write_bytes(soft_bytes)


class AirConControlParam(AirconParam):
    def __init__(self, aircon: AirCon, new_status: AirConStatus):
        if getattr(aircon, "is_mesh", False):
            Param.__init__(self, EnumDevice.MESHID_RA, EnumCmdType.RA0x03, False)
            self.subbody_ver = 0
        else:
            super().__init__(EnumCmdType.CONTROL, False)
            self.target = get_device_by_aircon(aircon)
        self._aircon = aircon
        self._new_status = new_status

    def generate_subbody(self, s: Encode, config: Config) -> None:
        aircon = self._aircon
        status = self._new_status

        # Smart Mesh RA AC Format (RAStatusControlDTO) - matches official app
        if getattr(aircon, "is_mesh", False) or getattr(config, "is_mesh", False):
            sub = bytearray()
            sub.append(0x22)                    # fixed 34
            sub.append(0x01)                    # fixed 1
            mac_str = getattr(aircon, "mac", "") or "00:00:00:00:00:00"
            mac_clean = mac_str.replace(":", "").replace("-", "")
            try:
                mac_bytes = bytes.fromhex(mac_clean) if len(mac_clean) == 12 else bytes(6)
            except Exception:
                mac_bytes = bytes(6)
            sub += mac_bytes
            # softId (hex string -> bytes); empty -> 0 bytes
            soft_str = getattr(aircon, "soft_id", "") or ""
            soft_clean = soft_str.replace(":", "").replace("-", "")
            try:
                soft_bytes = bytes.fromhex(soft_clean) if soft_clean else b""
            except Exception:
                soft_bytes = b""
            sub += soft_bytes
            sub.append(0x01)                    # controlEnable
            sub.append(0x01)                    # fixed 1
            mask_pos = len(sub)
            sub.append(0x00)                    # mask placeholder
            sub.append(0x00)                    # fixed 0
            length_pos = len(sub)
            sub.append(0x00)                    # length placeholder

            cur_status = getattr(aircon, "status", None)

            # 1. Switch Status (1 = ON, 0 = OFF)
            sw = status.switch if status.switch is not None else (cur_status.switch if cur_status else None)
            sw_val = 1
            if sw is not None:
                val = sw.value if hasattr(sw, "value") else int(sw)
                sw_val = 1 if val == 1 else 0

            # 2. Mode (RA: 1=auto, 2=dry, 3=cold, 4=heat, 6=ventilation)
            m = status.mode if status.mode is not None else (cur_status.mode if cur_status else None)
            m_val = m.value if (m is not None and hasattr(m, "value")) else (int(m) if m is not None else 0)
            mode_map = {1: 2, 2: 6, 3: 1, 4: 4, 0: 3}  # HA: DRY,VENT,AUTO,HEAT,COLD -> RA
            ra_mode = mode_map.get(m_val, 3)

            # 3. Target Temperature (raw = temp*2 + 28, e.g. 25C -> 78)
            t_raw = status.setted_temp if status.setted_temp is not None else (cur_status.setted_temp if cur_status else None)
            if t_raw is not None:
                t = int(t_raw) if t_raw < 100 else int(t_raw / 10)
            else:
                t = 25
            t = max(16, min(32, t))
            raw_temp = int(t * 2) + 28

            # 4. Air Volume (RA enum: 1-9 speed, 10=auto, 11=silent), 2-byte LE
            fan = status.air_flow if status.air_flow is not None else (cur_status.air_flow if cur_status else None)
            fan_val = fan.value if (fan is not None and hasattr(fan, "value")) else (int(fan) if fan is not None else 5)
            volume_map = {0: 1, 1: 3, 2: 5, 3: 7, 4: 9, 5: 10, 6: 11}
            ra_volume = volume_map.get(fan_val, 10)

            # 5. Air Direction (RA: 2 independent swing switches direction1/direction2, 0/1 each)
            d1 = status.fan_direction1 if status.fan_direction1 is not None else (cur_status.fan_direction1 if cur_status else None)
            d2 = status.fan_direction2 if status.fan_direction2 is not None else (cur_status.fan_direction2 if cur_status else None)
            direction_vals = None
            if d1 is not None or d2 is not None:
                def _d_to_sw(val):
                    if val is None:
                        return 0
                    v = val.value if hasattr(val, "value") else int(val)
                    return 1 if v in (7,) or v > 0 else 0  # SWING(7) or any step -> swing on
                direction_vals = (_d_to_sw(d1), _d_to_sw(d2))

            # Full control payload
            data = bytearray()
            data.append(sw_val)                 # switch (1 byte)
            data.append(ra_mode)                # mode (1 byte)
            data.append(raw_temp)               # raw temperature (1 byte)
            data += struct.pack("<H", ra_volume)  # air volume (2 bytes LE)
            if direction_vals is not None:
                data.append(direction_vals[0])  # direction1 (1 byte)
                data.append(direction_vals[1])  # direction2 (1 byte)

            mask = 0x01 | 0x02 | 0x04 | 0x08
            if direction_vals is not None:
                mask |= 0x10                    # direction bit (bit4)
            sub[mask_pos] = mask
            sub[length_pos] = len(data)
            sub += data
            s.write_bytes(sub)
            return

        # VRV format
        s.write1(aircon.room_id)
        s.write1(aircon.unit_id)
        li = []
        flag = 0
        if status.switch is not None:
            flag = flag | EnumControl.Type.SWITCH
            li.append((1, status.switch.value))
        if status.mode is not None:
            flag = flag | EnumControl.Type.MODE
            li.append((1, status.mode.value))
        if status.air_flow is not None:
            flag = flag | EnumControl.Type.AIR_FLOW
            li.append((1, status.air_flow.value))
        if status.current_temp is not None:
            flag = flag | EnumControl.Type.CURRENT_TEMP
            li.append((2, status.current_temp))
        if status.setted_temp is not None:
            flag = flag | EnumControl.Type.SETTED_TEMP
            li.append((2, status.setted_temp))
        if config.is_new_version:
            if self.target != EnumDevice.BATHROOM:
                if status.fan_direction1 is not None:
                    flag = flag | EnumControl.Type.FAN_DIRECTION
                    li.append((1, status.fan_direction1 | status.fan_direction2 << 4))

                if self.target == EnumDevice.NEWAIRCON:
                    if status.humidity is not None:
                        flag = flag | EnumControl.Type.HUMIDITY
                        li.append((1, status.humidity))
        s.write1(flag)
        for bit, val in li:
            if bit == 1:
                s.write1(val)
            elif bit == 2:
                s.write2(val)


# 新风相关参数类


class VentilationParam(Param):
    def __init__(self, cmd_type: EnumCmdType, has_result: bool):
        Param.__init__(self, EnumDevice.VENTILATION, cmd_type, has_result)


class VentilationCapabilityQueryParam(VentilationParam):
    def __init__(self):
        VentilationParam.__init__(self, EnumCmdType.VENT_QUERY_CAPABILITY, True)
        self._vents: list[Ventilation] = []

    def generate_subbody(self, s: Encode, config: Config) -> None:
        s.write1(len(self._vents))
        for i in self._vents:
            s.write1(i.room_id)
            s.write1(1)
            s.write1(0)

    @property
    def vents(self):
        return self._vents

    @vents.setter
    def vents(self, value):
        self._vents = value


class VentilationQueryStatusParam(VentilationParam):
    def __init__(self):
        super().__init__(EnumCmdType.QUERY_STATUS, True)
        self._device: Ventilation | None = None

    def generate_subbody(self, s: Encode, config: Config) -> None:
        s.write1(self._device.room_id)
        s.write1(self._device.unit_id)
        t = EnumControl.Type
        flag = t.SWITCH
        # 代码中对于SmallVAM是用这个参数，但是查询结果没有区别
        s.write1(7)

    @property
    def device(self):
        return self._device

    @device.setter
    def device(self, v: Ventilation):
        self._device = v


class VentilationControlParam(VentilationParam):
    def __init__(self, vent: Ventilation, new_status: VentilationStatus):
        super().__init__(EnumCmdType.CONTROL, False)
        self.target = get_device_by_vent(vent)
        self._vent = vent
        self._new_status = new_status

    def generate_subbody(self, s: Encode, config: Config) -> None:
        vent = self._vent
        status = self._new_status
        s.write1(vent.room_id)
        s.write1(vent.unit_id)
        li = []
        flag = 0
        if status.switch is not None:
            flag = flag | EnumControl.Type.SWITCH
            li.append((1, status.switch.value))
        if status.mode is not None:
            flag = flag | EnumControl.Type.MODE
            li.append((1, status.mode.value))
        if status.air_flow is not None:
            flag = flag | EnumControl.Type.AIR_FLOW
            li.append((1, status.air_flow.value))

        s.write1(flag)
        for bit, val in li:
            if bit == 1:
                s.write1(val)
            elif bit == 2:
                s.write2(val)


class VentilationQueryCompositeSituationParam(VentilationParam):
    def __init__(self):
        super().__init__(EnumCmdType.SMALL_VAM_QUERY_COMPOSITE_SITUATION, True)
        self._device: Ventilation | None = None

    def generate_subbody(self, s: Encode, config: Config) -> None:
        s.write1(self._device.room_id)
        s.write1(self._device.unit_id)

    @property
    def device(self):
        return self._device

    @device.setter
    def device(self, v: Ventilation):
        self._device = v


# HD 相关参数类


class HDParam(Param):
    def __init__(self, cmd_type: EnumCmdType, has_result: bool):
        Param.__init__(self, EnumDevice.HD, cmd_type, has_result)


class HDQueryStatusParam(HDParam):
    """HD设备状态查询参数，旧版主动查询，只能返回开关状态"""
    def __init__(self):
        super().__init__(EnumCmdType.QUERY_STATUS, True)
        self._device: HD | None = None

    def generate_subbody(self, s: Encode, config: Config) -> None:
        if self._device is not None:
            s.write1(self._device.room_id)
            s.write1(self._device.unit_id)
            s.write1(1)

    @property
    def device(self):
        return self._device

    @device.setter
    def device(self, value: HD):
        self._device = value


class HDQueryInfoParam(HDParam):
    """HD设备信息查询参数（当前没有响应，暂不使用）"""
    def __init__(self):
        super().__init__(EnumCmdType.NEW_HD_DEVICE_INFO, True)
        self._device: HD | None = None
        self.subbody_ver = 0

    def generate_subbody(self, s: Encode, config: Config) -> None:
        if self._device is not None:
            s.write1(self._device.room_id)
            s.write1(self._device.unit_id)

    @property
    def device(self):
        return self._device

    @device.setter
    def device(self, value: HD):
        self._device = value


class HDBaseControlParam(HDParam):
    """HD设备基础控制参数"""
    def __init__(self, hd: HD, new_status: HDStatus):
        super().__init__(EnumCmdType.NEW_HD_STATE_SETTING, False)
        self._hd = hd
        self._new_status = new_status

    def generate_subbody(self, s: Encode, config: Config) -> None:
        hd = self._hd
        status = self._new_status
        s.write1(hd.room_id)
        s.write1(hd.unit_id)

        li = []
        flag = 0
        if status.switch is not None:
            li.append((1, status.switch.value))
            flag |= 1
        if status.mute is not None:
            li.append((1, status.mute.value))
            flag |= 2
        if status.warm_temperature is not None:
            temp_value = int(status.warm_temperature * 10)
            li.append((2, temp_value))
            flag |= 16

        s.write1(flag)
        for bit, val in li:
            if bit == 1:
                s.write1(val)
            elif bit == 2:
                s.write2(val)
