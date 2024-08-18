import logging
import socket
import time
import typing
from threading import Thread, Lock

from .ctrl_enum import EnumDevice
from .dao import Room, AirCon, AirConStatus, get_device_by_aircon, Sensor, STATUS_ATTR
from .decoder import decoder, BaseResult
from .display import display
from .param import Param, HandShakeParam, HeartbeatParam, AirConControlParam, AirConQueryStatusParam, Sensor2InfoParam

_LOGGER = logging.getLogger(__name__)


def _log(s: str):
    s = str(s)
    for i in s.split('\n'):
        _LOGGER.debug(i)


class SocketClient:
    def __init__(self, host: str, port: int, instance_id: str):
        self._host = host
        self._port = port
        self._instance_id = instance_id
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
        _log("send hex: 0x"+p.to_string().hex())
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
        if data is not None:
            _log("recv hex: 0x"+data.hex())
        while data:
            try:
                r, b = decoder(data, self._instance_id)
                res.append(r)
                data = b
            except Exception as e:
                _log(e)
                data = None
        return res


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
            res = self._sock.recv()
            for i in res:
                _log('\033[31mrecv:\033[0m')
                _log(display(i))
                self._locker.acquire()
                try:
                    if i is not None:
                        i.do()
                except Exception as e:
                    _log(e)
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
            for instance_id in Service._socket_clients:
                Service._socket_clients[instance_id].send(HeartbeatParam())
                if cnt % Service.get_scan_interval() == 0:
                    _log("poll_status")
                    cnt = 0
                    Service.poll_status(instance_id)
            cnt += 1

            time.sleep(60)


class Service:
    _socket_clients: typing.Dict[str, SocketClient] = {}
    _rooms: typing.List[Room] = None
    _aircons: typing.Dict[str, typing.Dict[int, typing.List[AirCon]]] = {}
    _new_aircons: typing.Dict[str, typing.Dict[int, typing.List[AirCon]]] = {}
    _bathrooms: typing.Dict[str, typing.Dict[int, typing.List[AirCon]]] = {}
    _ready = False  # type: bool
    _none_stat_dev_cnt = 0  # type: int
    _status_hook: typing.Dict[str, typing.List[typing.Tuple[AirCon, typing.Callable]]] = {}
    _sensor_hook: typing.Dict[str, typing.List[typing.Tuple[str, typing.Callable]]] = {}
    _heartbeat_thread = HeartBeatThread()
    _sensors: typing.Dict[str, typing.List[Sensor]] = None
    _scan_interval = 5  # type: int

    @staticmethod
    def init(instance_id: str, host: str, port: int, scan_interval: int):
        if instance_id in Service._socket_clients:
            raise ValueError(f"Instance {instance_id} already initialized")
        Service._scan_interval = scan_interval
        Service._socket_clients[instance_id] = SocketClient(host, port, instance_id)
        Service._socket_clients[instance_id].send(HandShakeParam())
        Service._heartbeat_thread.start()
        while Service._rooms is None or Service._aircons is {} \
                or Service._new_aircons is {} or Service._bathrooms is {}:
            time.sleep(1)
        for i in Service._aircons.get(instance_id, {}).get(EnumDevice.AIRCON.value, []):
            for j in Service._rooms:
                if i.room_id == j.id:
                    i.alias = j.alias
                    if i.unit_id:
                        i.alias += str(i.unit_id)
        for i in Service._new_aircons.get(instance_id, {}).get(EnumDevice.NEWAIRCON.value, []):
            for j in Service._rooms:
                if i.room_id == j.id:
                    i.alias = j.alias
                    if i.unit_id:
                        i.alias += str(i.unit_id)
        for i in Service._bathrooms.get(instance_id, {}).get(EnumDevice.BATHROOM.value, []):
            for j in Service._rooms:
                if i.room_id == j.id:
                    i.alias = j.alias
                    if i.unit_id:
                        i.alias += str(i.unit_id)
        Service._ready = True

    @staticmethod
    def destroy(instance_id: str):
        if instance_id in Service._socket_clients:
            Service._socket_clients[instance_id].destroy()
            del Service._socket_clients[instance_id]
            if len(Service._socket_clients) <= 0:
                Service._heartbeat_thread.terminate()
            #Service._rooms = None
            Service._aircons.pop(instance_id)
            Service._new_aircons.pop(instance_id)
            Service._bathrooms.pop(instance_id)
            Service._none_stat_dev_cnt = 0
            Service._status_hook = {}
            Service._sensor_hook = {}
            Service._sensors.pop(instance_id)
            Service._ready = False

    @staticmethod
    def get_aircons(instance_id: str) -> typing.List[AirCon]:
        aircons = []
        for device in Service._new_aircons.get(instance_id, {}).values():
            aircons.extend(device)
        for device in Service._aircons.get(instance_id, {}).values():
            aircons.extend(device)
        for device in Service._bathrooms.get(instance_id, {}).values():
            aircons.extend(device)
        return aircons

    @staticmethod
    def control(instance_id: str, aircon: AirCon, status: AirConStatus):
        p = AirConControlParam(aircon, status)
        Service.send_msg(instance_id, p)

    @staticmethod
    def register_status_hook(instance_id: str, device: AirCon, hook: typing.Callable):
        if instance_id not in Service._status_hook:
            Service._status_hook[instance_id] = []
        Service._status_hook[instance_id].append((device, hook))

    @staticmethod
    def register_sensor_hook(instance_id: str, unique_id: str, hook: typing.Callable):
        if instance_id not in Service._sensor_hook:
            Service._sensor_hook[instance_id] = []
        Service._sensor_hook[instance_id].append((unique_id, hook))

    # ----split line---- above for component, below for inner call

    @staticmethod
    def is_ready() -> bool:
        return Service._ready

    @staticmethod
    def send_msg(instance_id: str, p: Param):
        """send msg to climate gateway"""
        if instance_id in Service._socket_clients:
            Service._socket_clients[instance_id].send(p)
        else:
            raise ValueError(f"Instance {instance_id} not initialized")

    @staticmethod
    def get_rooms():
        return Service._rooms

    @staticmethod
    def set_rooms(v: typing.List[Room]):
        Service._rooms = v

    @staticmethod
    def get_sensors(instance_id: str) -> typing.List[Sensor]:
        return Service._sensors[instance_id]

    @staticmethod
    def set_sensors(instance_id: str, sensors):
        if Service._sensors is None:
            Service._sensors = {}
        Service._sensors[instance_id] = sensors

    @staticmethod
    def set_device(instance_id: str, t: EnumDevice, v: typing.List[AirCon]):
        Service._none_stat_dev_cnt += len(v)
        if t == EnumDevice.AIRCON:
            if instance_id not in Service._aircons:
                Service._aircons[instance_id] = {}
            Service._aircons[instance_id][t.value] = v
        elif t == EnumDevice.NEWAIRCON:
            if instance_id not in Service._new_aircons:
                Service._new_aircons[instance_id] = {}
            Service._new_aircons[instance_id][t.value] = v
        else:
            if instance_id not in Service._bathrooms:
                Service._bathrooms[instance_id] = {}
            Service._bathrooms[instance_id][t.value] = v

    @staticmethod
    def set_aircon_status(instance_id: str, target: EnumDevice, room: int, unit: int, status: AirConStatus):
        if Service._ready:
            Service.update_aircon(instance_id, target, room, unit, status=status)
        else:
            li = []
            if target == EnumDevice.AIRCON:
                li = Service._aircons.get(instance_id, {}).get(target.value, [])
            elif target == EnumDevice.NEWAIRCON:
                li = Service._new_aircons.get(instance_id, {}).get(target.value, [])
            elif target == EnumDevice.BATHROOM:
                li = Service._bathrooms.get(instance_id, {}).get(target.value, [])
            for i in li:
                if i.unit_id == unit and i.room_id == room:
                    i.status = status
                    Service._none_stat_dev_cnt -= 1
                    break

    @staticmethod
    def set_sensors_status(instance_id: str, sensors: typing.List[Sensor]):
        for new_sensor in sensors:
            for sensor in Service._sensors.get(instance_id, {}):
                if sensor.unique_id == new_sensor.unique_id:
                    for attr in STATUS_ATTR:
                        setattr(sensor, attr, getattr(new_sensor, attr))
                    break
            for item in Service._sensor_hook.get(instance_id, []):
                unique_id, func = item
                if new_sensor.unique_id == unique_id:
                    try:
                        func(new_sensor)
                    except Exception as e:
                        _log(str(e))

    @staticmethod
    def poll_status(instance_id: str):
        if instance_id in Service._new_aircons:
            for i in Service._new_aircons[instance_id]:
                p = AirConQueryStatusParam()
                p.target = EnumDevice.NEWAIRCON
                p.device = i
                Service.send_msg(instance_id, p)
        if instance_id in Service._aircons:
            for i in Service._aircons[instance_id]:
                p = AirConQueryStatusParam()
                p.target = EnumDevice.AIRCON
                p.device = i
                Service.send_msg(instance_id, p)
        if instance_id in Service._bathrooms:
            for i in Service._bathrooms[instance_id]:
                p = AirConQueryStatusParam()
                p.target = EnumDevice.BATHROOM
                p.device = i
                Service.send_msg(instance_id, p)
        p = Sensor2InfoParam()
        Service.send_msg(instance_id, p)

    @staticmethod
    def update_aircon(instance_id: str, target: EnumDevice, room: int, unit: int, **kwargs):
        li = Service._status_hook.get(instance_id, [])
        for item in li:
            i, func = item
            if i.unit_id == unit and i.room_id == room and get_device_by_aircon(i) == target:
                try:
                    func(**kwargs)
                except Exception as e:
                    _log('hook error!!')
                    _log(str(e))

    @staticmethod
    def get_scan_interval():
        return Service._scan_interval
