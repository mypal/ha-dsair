from .ctrl_enum import EnumDevice, EnumCmdType


class BaseBean:
    def __init__(self, cmd_id: int, target: EnumDevice, cmd_type: EnumCmdType):
        self._cmd_id = cmd_id
        self._cmd_type = cmd_type
        self._target = target
        self._need_ack = 1
        self._subbody_ver = 0

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

    @need_ack.setter
    def need_ack(self, v: int):
        self._need_ack = v

    @subbody_ver.setter
    def subbody_ver(self, v: int):
        self._subbody_ver = v
