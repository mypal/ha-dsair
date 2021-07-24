import logging
import socket
import time
import typing
from threading import Thread, Lock

from .ctrl_enum import EnumDevice
from .dao import Room, AirCon, AirConStatus, get_device_by_aircon, Sensor
from .decoder import decoder, BaseResult
from .display import display
from .param import Param, HandShakeParam, HeartbeatParam, AirConControlParam, AirConQueryStatusParam, Sensor2InfoParam

_LOGGER = logging.getLogger(__name__)


def _log(s: str):
    s = str(s)
    for i in s.split('\n'):
        _LOGGER.debug(i)


class SocketClient:
    def __init__(self, host: str, port: int):
        self._host = host
        self._port = port
        self._locker = Lock()
        self._s = None
        while not self.do_connect():
            time.sleep(3)
        self._ready = True
        self._recv_thread = RecvThread(self)
        self._recv_thread.start()

    def destroy(self):
        self._ready = False
        self._recv_thread.terminate()
        self._s.close()

    def do_connect(self):
        self._s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._s.connect((self._host, self._port))
            _log('connected')
            return True
        except socket.error as exc:
            _log('connected error')
            _log(str(exc))
            return False

    def send(self, p: Param):
        self._locker.acquire()
        _log('\033[31msend:\033[0m')
        _log(display(p))
        done = False
        while not done:
            try:
                self._s.sendall(p.to_string())
                done = True
            except Exception:
                time.sleep(3)
                self.do_connect()
        self._locker.release()

    def recv(self) -> (typing.List[BaseResult], bytes):
        res = []
        done = False
        data = None

        while not done:
            try:
                data = self._s.recv(1024)
                done = True
            except Exception:
                if not self._ready:
                    return [], None
                time.sleep(3)
                self.do_connect()
        d = data
        while data:
            r, b = decoder(data)
            res.append(r)
            data = b
        return res, d


class RecvThread(Thread):
    def __init__(self, sock: SocketClient):
        super().__init__()
        self._sock = sock
        self._locker = Lock()
        self._running = True

    def terminate(self):
        self._running = False

    def run(self) -> None:
        while self._running:
            res, data = self._sock.recv()
            if data is not None:
                _log("hex: 0x"+data.hex())
            for i in res:
                _log('\033[31mrecv:\033[0m')
                _log(display(i))
                self._locker.acquire()
                i.do()
                self._locker.release()


class HeartBeatThread(Thread):
    def __init__(self):
        super().__init__()
        self._running = True

    def terminate(self):
        self._running = False

    def run(self) -> None:
        super().run()
        time.sleep(30)
        cnt = 0
        while self._running:
            Service.send_msg(HeartbeatParam())
            cnt += 1
            if cnt == 5:
                cnt = 0
                Service.poll_status()

            time.sleep(60)


class Service:
    _socket_client = None  # type: SocketClient
    _rooms = None  # type: typing.List[Room]
    _aircons = None  # type: typing.List[AirCon]
    _new_aircons = None  # type: typing.List[AirCon]
    _bathrooms = None  # type: typing.List[AirCon]
    _ready = False  # type: bool
    _none_stat_dev_cnt = 0  # type: int
    _status_hook = []  # type: typing.List[(AirCon, typing.Callable)]
    _sensor_hook = []  # type: typing.List[(str, typing.Callable)]
    _heartbeat_thread = None
    _sensors = []  # type: typing.List[Sensor]

    @staticmethod
    def init(host: str, port: int):
        if Service._ready:
            return
        Service._socket_client = SocketClient(host, port)
        Service._socket_client.send(HandShakeParam())
        Service._heartbeat_thread = HeartBeatThread()
        Service._heartbeat_thread.start()
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
    def destroy():
        if Service._ready:
            Service._heartbeat_thread.terminate()
            Service._socket_client.destroy()
            Service._socket_client = None
            Service._rooms = None
            Service._aircons = None
            Service._new_aircons = None
            Service._bathrooms = None
            Service._none_stat_dev_cnt = 0
            Service._status_hook = []
            Service._sensor_hook = []
            Service._heartbeat_thread = None
            Service._sensors = []
            Service._ready = False

    @staticmethod
    def get_aircons():
        return Service._new_aircons+Service._aircons+Service._bathrooms

    @staticmethod
    def control(aircon: AirCon, status: AirConStatus):
        p = AirConControlParam(aircon, status)
        Service.send_msg(p)

    @staticmethod
    def register_status_hook(device: AirCon, hook: typing.Callable):
        Service._status_hook.append((device, hook))

    @staticmethod
    def register_sensor_hook(unique_id: str, hook: typing.Callable):
        Service._sensor_hook.append((unique_id, hook))

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
    def get_sensors():
        return Service._sensors

    @staticmethod
    def set_sensors(sensors):
        Service._sensors = sensors

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
        if Service._ready:
            Service.update_aircon(target, room, unit, status=status)
        else:
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
    def set_sensors_status(sensors: typing.List[Sensor]):
        for newSensor in sensors:
            for sensor in Service._sensors:
                if sensor.name == newSensor.name or sensor.alias == newSensor.alias:
                    for attr in Sensor.STATUS_ATTR:
                        setattr(sensor, attr, getattr(newSensor, attr))
                    break
            for item in Service._sensor_hook:
                unique_id, func = item
                if newSensor.unique_id == unique_id:
                    try:
                        func(newSensor)
                    except Exception as e:
                        _log(str(e))

    @staticmethod
    def poll_status():
        for i in Service._new_aircons:
            p = AirConQueryStatusParam()
            p.target = EnumDevice.NEWAIRCON
            p.device = i
            Service.send_msg(p)
        p = Sensor2InfoParam()
        Service.send_msg(p)

    @staticmethod
    def update_aircon(target: EnumDevice, room: int, unit: int, **kwargs):
        li = Service._status_hook
        for item in li:
            i, func = item
            if i.unit_id == unit and i.room_id == room and get_device_by_aircon(i) == target:
                try:
                    func(**kwargs)
                except Exception as e:
                    _log('hook error!!')
                    _log(str(e))
