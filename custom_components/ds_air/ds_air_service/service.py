from __future__ import annotations

from collections.abc import Callable
import logging
import socket
from threading import Lock, Thread
import time

from .config import Config
from .ctrl_enum import EnumDevice
from .dao import STATUS_ATTR, AirCon, AirConStatus, Room, Sensor, get_device_by_aircon
from .decoder import BaseResult, decoder
from .display import display
from .param import (
    AirConControlParam,
    AirConQueryStatusParam,
    HandShakeParam,
    HeartbeatParam,
    Param,
    Sensor2InfoParam,
)

_LOGGER = logging.getLogger(__name__)


def _log(s: str):
    s = str(s)
    for i in s.split("\n"):
        _LOGGER.debug(i)


class SocketClient:
    def __init__(self, host: str, port: int, service: Service, config: Config):
        self._host = host
        self._port = port
        self._config = config
        self._locker = Lock()
        self._s = None
        while not self.do_connect():
            time.sleep(3)
        self._ready = True
        self._recv_thread = RecvThread(self, service)
        self._recv_thread.start()

    def destroy(self):
        self._ready = False
        self._recv_thread.terminate()
        self._s.close()

    def do_connect(self):
        self._s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._s.connect((self._host, self._port))
            _log("connected")
            return True
        except OSError as exc:
            _log("connected error")
            _log(str(exc))
            return False

    def send(self, p: Param):
        self._locker.acquire()
        _log("send hex: 0x" + p.to_string(self._config).hex())
        _log("\033[31msend:\033[0m")
        _log(display(p))
        done = False
        while not done:
            try:
                self._s.sendall(p.to_string(self._config))
                done = True
            except Exception:
                time.sleep(3)
                self.do_connect()
        self._locker.release()

    def recv(self) -> (list[BaseResult], bytes):
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
            _log("recv hex: 0x" + data.hex())
        while data:
            try:
                r, b = decoder(data, self._config)
                res.append(r)
                data = b
            except Exception as e:
                _log(e)
                data = None
        return res


class RecvThread(Thread):
    def __init__(self, sock: SocketClient, service: Service):
        super().__init__()
        self._sock = sock
        self._service = service
        self._locker = Lock()
        self._running = True

    def terminate(self):
        self._running = False

    def run(self) -> None:
        while self._running:
            res = self._sock.recv()
            for i in res:
                _log("\033[31mrecv:\033[0m")
                _log(display(i))
                self._locker.acquire()
                try:
                    if i is not None:
                        i.do(self._service)
                except Exception as e:
                    _log(e)
                self._locker.release()


class HeartBeatThread(Thread):
    def __init__(self, service: Service):
        super().__init__()
        self.service = service
        self._running = True

    def terminate(self):
        self._running = False

    def run(self) -> None:
        super().run()
        time.sleep(30)
        cnt = 0
        while self._running:
            self.service.send_msg(HeartbeatParam())
            cnt += 1
            if cnt == self.service.get_scan_interval():
                _log("poll_status")
                cnt = 0
                self.service.poll_status()

            time.sleep(60)


class Service:
    def __init__(self):
        self._socket_client: SocketClient = None
        self._rooms: list[Room] = None
        self._aircons: list[AirCon] = None
        self._new_aircons: list[AirCon] = None
        self._bathrooms: list[AirCon] = None
        self._ready: bool = False
        self._none_stat_dev_cnt: int = 0
        self._status_hook: list[(AirCon, Callable)] = []
        self._sensor_hook: list[(str, Callable)] = []
        self._heartbeat_thread = None
        self._sensors: list[Sensor] = []
        self._scan_interval: int = 5
        self.state_change_listener: Callable[[], None] | None = None

    def init(self, host: str, port: int, scan_interval: int, config: Config) -> None:
        if self._ready:
            return
        self._scan_interval = scan_interval
        self._socket_client = SocketClient(host, port, self, config)
        self._socket_client.send(HandShakeParam())
        self._heartbeat_thread = HeartBeatThread(self)
        self._heartbeat_thread.start()
        while (
            self._rooms is None
            or self._aircons is None
            or self._new_aircons is None
            or self._bathrooms is None
        ):
            time.sleep(1)
        for i in self._aircons:
            for j in self._rooms:
                if i.room_id == j.id:
                    i.alias = j.alias
                    if i.unit_id:
                        i.alias += str(i.unit_id)
        for i in self._new_aircons:
            for j in self._rooms:
                if i.room_id == j.id:
                    i.alias = j.alias
                    if i.unit_id:
                        i.alias += str(i.unit_id)
        for i in self._bathrooms:
            for j in self._rooms:
                if i.room_id == j.id:
                    i.alias = j.alias
                    if i.unit_id:
                        i.alias += str(i.unit_id)
        self._ready = True

    def destroy(self) -> None:
        if self._ready:
            self._heartbeat_thread.terminate()
            self._socket_client.destroy()
            self._socket_client = None
            self._rooms = None
            self._aircons = None
            self._new_aircons = None
            self._bathrooms = None
            self._none_stat_dev_cnt = 0
            self._status_hook = []
            self._sensor_hook = []
            self._heartbeat_thread = None
            self._sensors = []
            self._ready = False

    def get_aircons(self) -> list[AirCon]:
        aircons = []
        if self._new_aircons is not None:
            aircons += self._new_aircons
        if self._aircons is not None:
            aircons += self._aircons
        if self._bathrooms is not None:
            aircons += self._bathrooms
        return aircons

    def control(self, aircon: AirCon, status: AirConStatus):
        p = AirConControlParam(aircon, status)
        self.send_msg(p)

    def register_status_hook(self, device: AirCon, hook: Callable):
        self._status_hook.append((device, hook))

    def register_sensor_hook(self, unique_id: str, hook: Callable):
        self._sensor_hook.append((unique_id, hook))

    # ----split line---- above for component, below for inner call

    def is_ready(self) -> bool:
        return self._ready

    def send_msg(self, p: Param):
        """Send msg to climate gateway"""
        self._socket_client.send(p)

    def get_rooms(self):
        return self._rooms

    def set_rooms(self, v: list[Room]):
        self._rooms = v

    def get_sensors(self):
        return self._sensors

    def set_sensors(self, sensors):
        self._sensors = sensors

    def set_device(self, t: EnumDevice, v: list[AirCon]):
        self._none_stat_dev_cnt += len(v)
        if t == EnumDevice.AIRCON:
            self._aircons = v
        elif t == EnumDevice.NEWAIRCON:
            self._new_aircons = v
        else:
            self._bathrooms = v

    def set_aircon_status(
        self, target: EnumDevice, room: int, unit: int, status: AirConStatus
    ):
        if self._ready:
            self.update_aircon(target, room, unit, status=status)
        else:
            li = []
            if target == EnumDevice.AIRCON:
                li = self._aircons
            elif target == EnumDevice.NEWAIRCON:
                li = self._new_aircons
            elif target == EnumDevice.BATHROOM:
                li = self._bathrooms
            for i in li:
                if i.unit_id == unit and i.room_id == room:
                    i.status = status
                    self._none_stat_dev_cnt -= 1
                    break

    def set_sensors_status(self, sensors: list[Sensor]):
        for new_sensor in sensors:
            for sensor in self._sensors:
                if sensor.unique_id == new_sensor.unique_id:
                    for attr in STATUS_ATTR:
                        setattr(sensor, attr, getattr(new_sensor, attr))
                    break
            for item in self._sensor_hook:
                unique_id, func = item
                if new_sensor.unique_id == unique_id:
                    try:
                        func(new_sensor)
                    except Exception as e:
                        _log(str(e))

    def poll_status(self):
        for i in self._new_aircons:
            p = AirConQueryStatusParam()
            p.target = EnumDevice.NEWAIRCON
            p.device = i
            self.send_msg(p)
        p = Sensor2InfoParam()
        self.send_msg(p)

    def update_aircon(self, target: EnumDevice, room: int, unit: int, **kwargs):
        li = self._status_hook
        for item in li:
            i, func = item
            if (
                i.unit_id == unit
                and i.room_id == room
                and get_device_by_aircon(i) == target
            ):
                try:
                    func(**kwargs)
                except Exception as e:
                    _log("hook error!!")
                    _log(str(e))

    def get_scan_interval(self):
        return self._scan_interval
