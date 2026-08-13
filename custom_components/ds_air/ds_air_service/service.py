from __future__ import annotations

from collections.abc import Callable
import logging
import socket
from threading import Event, Lock, Thread
import time

from .config import Config
from .ctrl_enum import EnumDevice
from .dao import (
    STATUS_ATTR,
    AirCon,
    AirConStatus,
    HD,
    HDStatus,
    Room,
    Sensor,
    Ventilation,
    VentilationStatus,
    get_device_by_aircon,
    get_device_by_vent,
    UNINITIALIZED_VALUE,
)
from .decoder import BaseResult, decoder
from .display import display
from .param import (
    AirConControlParam,
    AirConQueryStatusParam,
    HandShakeParam,
    HeartbeatParam,
    Param,
    Sensor2InfoParam,
    VentilationControlParam,
    VentilationQueryCompositeSituationParam,
    VentilationQueryStatusParam,
)

_LOGGER = logging.getLogger(__name__)
INIT_TIMEOUT_SECONDS = 60.0
SOCKET_TIMEOUT_SECONDS = 5.0
CONNECT_RETRY_INTERVAL_SECONDS = 3.0


def _log(s: str):
    s = str(s)
    for i in s.split("\n"):
        _LOGGER.debug(i)


class SocketClient:
    def __init__(
        self,
        host: str,
        port: int,
        service: Service,
        config: Config,
        deadline: float | None = None,
    ):
        self._host = host
        self._port = port
        self._config = config
        self._locker = Lock()
        self._s = None
        self._ready = False
        self._recv_thread = None
        while not self.do_connect(deadline):
            self._raise_if_expired(deadline, "connecting")
            time.sleep(self._retry_sleep(deadline))
        self._ready = True
        self._recv_thread = RecvThread(self, service)
        self._recv_thread.start()

    def destroy(self):
        self._ready = False
        if self._recv_thread is not None:
            self._recv_thread.terminate()
            self._recv_thread = None
        if self._s is not None:
            self._s.close()
            self._s = None

    def _raise_if_expired(self, deadline: float | None, action: str) -> None:
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError(
                f"Timed out {action} to DS-AIR gateway {self._host}:{self._port}"
            )

    def _retry_sleep(self, deadline: float | None) -> float:
        if deadline is None:
            return CONNECT_RETRY_INTERVAL_SECONDS
        return min(CONNECT_RETRY_INTERVAL_SECONDS, max(0.0, deadline - time.monotonic()))

    def do_connect(self, deadline: float | None = None):
        self._raise_if_expired(deadline, "connecting")
        self._s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        timeout = SOCKET_TIMEOUT_SECONDS
        if deadline is not None:
            timeout = min(timeout, max(0.001, deadline - time.monotonic()))
        self._s.settimeout(timeout)
        try:
            self._s.connect((self._host, self._port))
        except OSError as exc:
            _log("connected error")
            _log(str(exc))
            self._s.close()
            self._s = None
            return False
        else:
            # 该超时只用于建立连接阶段，不能残留到 RecvThread 中常驻的 recv()：
            # 网关只在状态变化时推送，空闲间隔会远超该超时，否则 recv() 会超时抛错，
            # 进而静默重连（且不重新握手），导致此后再也收不到状态推送。
            self._s.settimeout(None)
            _log("connected")
            return True

    def send(self, p: Param, deadline: float | None = None):
        data = p.to_string(self._config)
        with self._locker:
            _log("send hex: 0x" + data.hex())
            _log("\033[31msend:\033[0m")
            _log(display(p))
            done = False
            while not done:
                self._raise_if_expired(deadline, "sending")
                try:
                    self._s.sendall(data)
                    done = True
                except Exception:
                    time.sleep(self._retry_sleep(deadline))
                    self.do_connect(deadline)

    def _reconnect(self) -> None:
        """断线后重连并重新握手。

        网关只会向完成握手的连接推送状态变化，因此重连后必须重新发送握手，
        否则墙板等设备上的状态变化不会再同步到 HA（只能依赖周期轮询）。
        本方法仅由 RecvThread 调用，调用时未持有发送锁，故可安全调用 send()。
        """
        while self._ready and not self.do_connect():
            time.sleep(self._retry_sleep(None))
        if self._ready:
            self.send(HandShakeParam())

    def recv(self) -> list[BaseResult]:
        res = []
        data = None

        while True:
            try:
                data = self._s.recv(1024)
            except Exception:
                if not self._ready:
                    return []
                # 真正的连接错误：重连并重新握手
                self._reconnect()
                continue
            if data:
                break
            # recv 返回空字节表示对端已正常关闭连接（不会抛异常）。
            # 必须重连并重新握手，否则会陷入空读忙循环，且网关不再推送状态。
            if not self._ready:
                return []
            self._reconnect()

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
        self._stop_event = Event()

    def terminate(self):
        self._running = False
        self._stop_event.set()

    def run(self) -> None:
        super().run()
        if self._stop_event.wait(30):
            return
        cnt = 0
        while self._running:
            self.service.send_msg(HeartbeatParam())
            cnt += 1
            if cnt == self.service.get_scan_interval():
                _log("poll_status")
                cnt = 0
                self.service.poll_status()

            if self._stop_event.wait(60):
                return


class Service:
    def __init__(self):
        self._socket_client: SocketClient = None
        self._rooms: list[Room] = None
        self._aircons: list[AirCon] = None
        self._new_aircons: list[AirCon] = None
        self._bathrooms: list[AirCon] = None
        self._ventilations: list[Ventilation] = None
        self._hds: list[HD] = None
        self._ready: bool = False
        self._none_stat_dev_cnt: int = 0
        self._status_hook: list[(AirCon, Callable)] = []
        self._sensor_hook: list[(str, Callable)] = []
        self._vent_hook: list[(Ventilation, Callable)] = []
        self._hd_hook: list[(HD, Callable)] = []
        self._heartbeat_thread = None
        self._sensors: list[Sensor] = []
        self._scan_interval: int = 5
        self.state_change_listener: Callable[[], None] | None = None
        self._config: Config = None

    def init(
        self,
        host: str,
        port: int,
        scan_interval: int,
        config: Config,
        timeout: float | None = INIT_TIMEOUT_SECONDS,
    ) -> None:
        if self._ready:
            return
        deadline = time.monotonic() + timeout if timeout is not None else None
        try:
            self._scan_interval = scan_interval
            self._config = config
            self._socket_client = SocketClient(host, port, self, config, deadline)
            self._socket_client.send(HandShakeParam(), deadline)
            self._heartbeat_thread = HeartBeatThread(self)
            self._heartbeat_thread.start()
            while (
                self._rooms is None
                or self._aircons is None
                or self._new_aircons is None
                or self._bathrooms is None
                or self._ventilations is None
                or self._hds is None
            ):
                if deadline is not None and time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"Timed out initializing DS-AIR gateway {host}:{port}"
                    )
                if deadline is None:
                    time.sleep(1)
                else:
                    time.sleep(min(1, max(0.0, deadline - time.monotonic())))
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
            if self._ventilations is not None:
                for i in self._ventilations:
                    for j in self._rooms:
                        if i.room_id == j.id:
                            i.alias = j.alias
                            if i.unit_id:
                                i.alias += str(i.unit_id)
            if self._hds is not None:
                for i in self._hds:
                    for j in self._rooms:
                        if i.room_id == j.id:
                            i.alias = j.alias
                            if i.unit_id:
                                i.alias += str(i.unit_id)
            self._ready = True
        except Exception:
            self.destroy()
            raise

    def destroy(self) -> None:
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.terminate()
            self._heartbeat_thread = None
        if self._socket_client is not None:
            self._socket_client.destroy()
            self._socket_client = None
        self._rooms = None
        self._aircons = None
        self._new_aircons = None
        self._bathrooms = None
        self._ventilations = None
        self._hds = None
        self._none_stat_dev_cnt = 0
        self._status_hook = []
        self._sensor_hook = []
        self._vent_hook = []
        self._hd_hook = []
        self._sensors = []
        self._ready = False
        self._config = None

    def get_aircons(self) -> list[AirCon]:
        aircons = []
        if self._new_aircons is not None:
            aircons += self._new_aircons
        if self._aircons is not None:
            aircons += self._aircons
        if self._bathrooms is not None:
            aircons += self._bathrooms
        return aircons

    def get_ventilations(self) -> list[Ventilation]:
        if self._ventilations is None:
            return []
        return self._ventilations

    def get_hds(self) -> list[HD]:
        """获取所有HD设备"""
        if self._hds is None:
            return []
        return self._hds

    def get_bathrooms(self) -> list[AirCon]:
        """获取所有浴室空调设备"""
        if self._bathrooms is None:
            return []
        return self._bathrooms

    def control(self, aircon: AirCon, status: AirConStatus):
        p = AirConControlParam(aircon, status)
        self.send_msg(p)

    def control_vent(self, ventilation: Ventilation, status: VentilationStatus):
        p = VentilationControlParam(ventilation, status)
        self.send_msg(p)

    def hd_control(self, hd: HD, status: HDStatus):
        """控制HD设备"""
        from .param import HDBaseControlParam
        p = HDBaseControlParam(hd, status)
        self.send_msg(p)

    def register_status_hook(self, device: AirCon, hook: Callable):
        self._status_hook.append((device, hook))

    def register_sensor_hook(self, unique_id: str, hook: Callable):
        self._sensor_hook.append((unique_id, hook))

    def register_vent_hook(self, device: Ventilation, hook: Callable):
        self._vent_hook.append((device, hook))

    def register_hd_hook(self, device: HD, hook: Callable):
        """注册HD设备状态钩子"""
        self._hd_hook.append((device, hook))

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

    def set_device(self, t: EnumDevice, v: list):
        self._none_stat_dev_cnt += len(v)
        if t == EnumDevice.AIRCON:
            self._aircons = v
        elif t == EnumDevice.NEWAIRCON:
            self._new_aircons = v
        elif t == EnumDevice.BATHROOM:
            self._bathrooms = v
        elif t in (EnumDevice.VENTILATION, EnumDevice.SMALL_VAM):
            if self._ventilations is None:
                self._ventilations = v
            else:
                self._ventilations.extend(v)
        elif t == EnumDevice.HD:
            if self._hds is None:
                self._hds = v
            else:
                self._hds.extend(v)

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
        if self._ventilations is not None:
            for v in self._ventilations:
                p = VentilationQueryStatusParam()
                p.target = get_device_by_vent(v)
                p.device = v
                self.send_msg(p)
                if v.is_small_vam:
                    p = VentilationQueryCompositeSituationParam()
                    p.target = get_device_by_vent(v)
                    p.device = v
                    self.send_msg(p)
        if self._hds is not None:
            for hd in self._hds:
                from .param import HDQueryStatusParam
                p = HDQueryStatusParam()
                p.device = hd
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

    # 新风相关方法

    def set_ventilations(self, ventilations: list[Ventilation]):
        self._ventilations = ventilations

    def set_ventilation_status(
        self, room: int, unit: int, status: VentilationStatus
    ):
        if self._ready:
            self.update_ventilation(room, unit, status=status)
        else:
            if self._ventilations is not None:
                for i in self._ventilations:
                    if i.unit_id == unit and i.room_id == room:
                        for attr in i.status.__dict__.keys():
                            value = getattr(status, attr)
                            if value is not None and value != UNINITIALIZED_VALUE:
                                setattr(i.status, attr, value)
                        break

    def update_ventilation(self, room: int, unit: int, **kwargs):
        li = self._vent_hook
        if li is None:
            return
        for item in li:
            i, func = item
            if i.unit_id == unit and i.room_id == room:
                try:
                    func(**kwargs)
                except Exception as e:
                    _log("vent hook error!!")
                    _log(str(e))

    # HD 相关方法

    def set_hds(self, hds: list[HD]):
        """设置HD设备列表"""
        self._none_stat_dev_cnt += len(hds)
        self._hds = hds

    def set_hd_status(self, room: int, unit: int, status: HDStatus):
        """设置HD设备状态"""
        if self._ready:
            self.update_hd(room, unit, status=status)
        else:
            if self._hds is None:
                return
            for hd in self._hds:
                if hd.unit_id == unit and hd.room_id == room:
                    for attr in hd.status.__dict__.keys():
                        value = getattr(status, attr)
                        if value is not None and value != UNINITIALIZED_VALUE:
                            setattr(hd.status, attr, value)
                    self._none_stat_dev_cnt -= 1
                    break

    def update_hd(self, room: int, unit: int, **kwargs):
        """更新HD设备状态"""
        li = self._hd_hook
        if li is None:
            return
        for item in li:
            i, func = item
            if i.unit_id == unit and i.room_id == room:
                try:
                    func(**kwargs)
                except Exception as e:
                    _log("hd hook error!!")
                    _log(str(e))
