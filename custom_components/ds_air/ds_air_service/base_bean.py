from .ctrl_enum import EnumDevice, EnumCmdType


class BaseBean:
    def __init__(self, cmd_id: int, target: EnumDevice, cmd_type: EnumCmdType):
        self._cmd_id: int = cmd_id
        self._cmd_type: EnumCmdType = cmd_type
        self._target: EnumDevice = target
        self._need_ack: int = 1
        self._subbody_ver: int = 1

    @property
    def cmd_id(self):
        return self._cmd_id

    @property
    def cmd_type(self):
        return self._cmd_type

    @property
    def need_ack(self):
        return self._need_ack

    @property
    def subbody_ver(self):
        return self._subbody_ver

    @property
    def target(self):
        return self._target

    @target.setter
    def target(self, v: EnumDevice):
        self._target = v

    @need_ack.setter
    def need_ack(self, v: int):
        self._need_ack = v

    @subbody_ver.setter
    def subbody_ver(self, v: int):
        self._subbody_ver = v
