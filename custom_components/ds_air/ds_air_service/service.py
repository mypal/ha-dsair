import asyncio
import logging
import socket
import time
import typing
from threading import Thread, Lock

from .ctrl_enum import EnumDevice
from .dao import Room, AirCon, AirConStatus
from .param import Param, HandShakeParam, HeartbeatParam
from .display import display
from .decoder import decoder, BaseResult

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

    def run(self) -> None:
        while True:
            res = self._sock.recv()
            for i in res:
                _log('recv:')
                _log(display(i))
                i.do()


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
    _none_stat_dev_cnt = 0  # type: int

    @staticmethod
    def init(host: str = HOST, port: int = PORT):
        Service._socket_client = SocketClient(host, port)
        Service._socket_client.send(HandShakeParam())
        while Service._rooms is None or Service._aircons is None \
                or Service._new_aircons is None or Service._bathrooms is None:
            time.sleep(1)  # asyncio.sleep(1)

    @staticmethod
    def get_aircons():
        return Service._aircons

    # ----split line---- above for component, below for inner call

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
    def set_aircons(v: typing.List[AirCon]):
        Service._none_stat_dev_cnt += len(v)
        Service._aircons = v

    @staticmethod
    def set_new_aircons(v: typing.List[AirCon]):
        Service._none_stat_dev_cnt += len(v)
        Service._new_aircons = v

    @staticmethod
    def set_bathrooms(v: typing.List[AirCon]):
        Service._none_stat_dev_cnt += len(v)
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
