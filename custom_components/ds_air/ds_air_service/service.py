import logging
import socket
import time
import types
import typing
from threading import Thread, Lock

from .ctrl_enum import EnumDevice
from .dao import Room, AirCon, AirConStatus, get_device_by_aircon
from .decoder import decoder, BaseResult
from .display import display
from .param import Param, HandShakeParam, HeartbeatParam, AirConControlParam

HOST = '192.168.1.110'
PORT = 8008

_LOGGER = logging.getLogger(__name__)


def _log(s: str):
    for i in s.split('\n'):
        _LOGGER.debug(i)


class SocketClient:
    def __init__(self, host: str, port: int):
        self._host = host
        self._port = port
        self._locker = Lock()
        self._s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._s.connect((self._host, self._port))
        self._recv_thread = RecvThread(self)
        self._recv_thread.start()
        self._heartbeat_thread = HeartBeatThread(self)
        self._heartbeat_thread.start()

    def send(self, p: Param):
        self._locker.acquire()
        _log('send:')
        _log(display(p))
        self._s.sendall(p.to_string())
        self._locker.release()

    def recv(self) -> typing.List[BaseResult]:
        res = []
        data = self._s.recv(1024)
        while data:
            r, b = decoder(data)
            res.append(r)
            data = b
        return res


class RecvThread(Thread):
    def __init__(self, sock: SocketClient):
        super().__init__()
        self._sock = sock
        self._locker = Lock()

    def run(self) -> None:
        while True:
            res = self._sock.recv()
            for i in res:
                _log('recv:')
                _log(display(i))
                self._locker.acquire()
                i.do()
                self._locker.release()


class HeartBeatThread(Thread):
    def __init__(self, sock: SocketClient):
        super().__init__()
        self._sock = sock

    def run(self) -> None:
        super().run()
        while True:
            self._sock.send(HeartbeatParam())
            time.sleep(60)


class Service:
    _socket_client = None      # type: SocketClient
    _rooms = None              # type: typing.List[Room]
    _aircons = None            # type: typing.List[AirCon]
    _new_aircons = None        # type: typing.List[AirCon]
    _bathrooms = None          # type: typing.List[AirCon]
    _ready = False             # type: bool
    _none_stat_dev_cnt = 0     # type: int
    _status_hook = []          # type: typing.List[(AirCon, types.FunctionType)]

    @staticmethod
    def init(host: str = HOST, port: int = PORT):
        Service._socket_client = SocketClient(host, port)
        Service._socket_client.send(HandShakeParam())
        while Service._rooms is None or Service._aircons is None \
                or Service._new_aircons is None or Service._bathrooms is None:
            time.sleep(1)
        for i in Service._aircons:
            for j in Service._rooms:
                if i.room_id == j.id:
                    i.alias = j.alias
                    if i.unit_id:
                        i.alias += str(i.unit_id)
        for i in Service._new_aircons:
            for j in Service._rooms:
                if i.room_id == j.id:
                    i.alias = j.alias
                    if i.unit_id:
                        i.alias += str(i.unit_id)
        for i in Service._bathrooms:
            for j in Service._rooms:
                if i.room_id == j.id:
                    i.alias = j.alias
                    if i.unit_id:
                        i.alias += str(i.unit_id)
        Service._ready = True

    @staticmethod
    def get_new_aircons():
        return Service._new_aircons

    @staticmethod
    def control(aircon: AirCon, status: AirConStatus):
        p = AirConControlParam(aircon, status)
        Service.send_msg(p)

    @staticmethod
    def register_status_hook(device: AirCon, hook):
        Service._status_hook.append((device, hook))

    # ----split line---- above for component, below for inner call

    @staticmethod
    def is_ready() -> bool:
        return Service._ready

    @staticmethod
    def send_msg(p: Param):
        """send msg to climate gateway"""
        Service._socket_client.send(p)

    @staticmethod
    def get_rooms():
        return Service._rooms

    @staticmethod
    def set_rooms(v: typing.List[Room]):
        Service._rooms = v

    @staticmethod
    def set_device(t: EnumDevice, v: typing.List[AirCon]):
        Service._none_stat_dev_cnt += len(v)
        if t == EnumDevice.AIRCON:
            Service._aircons = v
        elif t == EnumDevice.NEWAIRCON:
            Service._new_aircons = v
        else:
            Service._bathrooms = v

    @staticmethod
    def set_aircon_status(target: EnumDevice, room: int, unit: int, status: AirConStatus):
        li = []
        if target == EnumDevice.AIRCON:
            li = Service._aircons
        elif target == EnumDevice.NEWAIRCON:
            li = Service._new_aircons
        elif target == EnumDevice.BATHROOM:
            li = Service._bathrooms
        for i in li:
            if i.unit_id == unit and i.room_id == room:
                i.status = status
                Service._none_stat_dev_cnt -= 1
                break

    @staticmethod
    def update_aircon(target: EnumDevice, room: int, unit: int, **kwargs):
        li = Service._status_hook
        for item in li:
            i, func = item
            if i.unit_id == unit and i.room_id == room and get_device_by_aircon(i) == target:
                try:
                    func(**kwargs)
                except Exception as e:
                    _log(str(e))
