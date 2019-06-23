import socket
import typing
from threading import Thread, Lock
from time import sleep

from .param import Param, HandShakeParam, HeartbeatParam
from .display import display
from .decoder import decoder, BaseResult

HOST = '192.168.1.110'
PORT = 8008


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
        print('\n\033[1;35msend:\033[0m')
        print(display(p))
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
                print('\n\033[1;36mrecv:\033[0m')
                print(display(i))
                i.do()


class HeartBeatThread(Thread):
    def __init__(self, sock):
        super().__init__()
        self._sock = sock

    def run(self) -> None:
        super().run()
        while True:
            self._sock.send(HeartbeatParam())
            sleep(60)


class Service:
    socket_client = SocketClient(HOST, PORT)
    rooms = []

    @staticmethod
    def hand_shake():
        Service.socket_client.send(HandShakeParam())

    @staticmethod
    def send(p: Param):
        Service.socket_client.send(p)
