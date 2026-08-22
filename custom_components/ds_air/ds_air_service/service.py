from __future__ import annotations

from collections.abc import Callable
import logging
import socket
from threading import Event, Lock, Thread
import time

from .config import Config
from .ctrl_enum import EnumControl, EnumDevice
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
    GetRoomInfoParam,
    HandShakeParam,
    HeartbeatParam,
    MeshGetBasicInfoParam,
    MeshGetNodeListParam,
    MeshNodeQueryParam,
    MeshRAInfoParam,
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
        _LOGGER.info(i)


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
        timeout = SOCKET_TIMEOUT_SECONDS
        if deadline is not None:
            timeout = min(timeout, max(0.001, deadline - time.monotonic()))

        # Smart port detection: try configured port, then alternative port (8008 <-> 8009)
        candidate_ports = [self._port]
        alt_port = 8009 if self._port == 8008 else 8008
        candidate_ports.append(alt_port)

        for p in candidate_ports:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            try:
                s.connect((self._host, p))
                s.settimeout(None)
                self._s = s
                self._port = p
                self._config.detected_port = p
                _log(f"connected to {self._host}:{p}")
                return True
            except OSError as exc:
                _log(f"connect error on port {p}: {exc}")
                s.close()

        self._s = None
        return False

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


class CloudPollThread(Thread):
    """Poll Mesh live state because its MQTT topic has no retained snapshot."""

    def __init__(self, service: Service):
        super().__init__(daemon=True)
        self.service = service
        self._stop_event = Event()

    def terminate(self):
        self._stop_event.set()

    def run(self) -> None:
        while not self._stop_event.wait(60):
            self.service.poll_cloud_status()


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
        self._cloud_client = None
        self._cloud_only = False

    @staticmethod
    def _cloud_enum(enum_cls, value):
        if value is None:
            return None
        try:
            return enum_cls(int(value))
        except (TypeError, ValueError):
            return None

    def _apply_cloud_status(self, aircon: AirCon, status: dict) -> None:
        """Merge an NLSPSmartClient RAModel status into a DS-AIR device."""
        if "switches" in status:
            aircon.status.switch = self._cloud_enum(EnumControl.Switch, status["switches"])
        if "mode" in status:
            aircon.status.mode = self._cloud_enum(EnumControl.Mode, status["mode"])
        if "volume" in status:
            aircon.status.air_flow = self._cloud_enum(EnumControl.AirFlow, status["volume"])
        if "direction1" in status:
            aircon.status.fan_direction1 = self._cloud_enum(EnumControl.FanDirection, status["direction1"])
        if "direction2" in status:
            aircon.status.fan_direction2 = self._cloud_enum(EnumControl.FanDirection, status["direction2"])
        if status.get("temp") is not None:
            aircon.status.setted_temp = round(float(status["temp"]) * 10)

    def init_cloud(self, cloud_client, devices: list[dict], config: Config) -> None:
        """Initialize a service solely from Daikin Cloud direct RA snapshots."""
        self._config = config
        self._cloud_client = cloud_client
        self._cloud_only = True
        self._rooms = []
        self._aircons = []
        self._new_aircons = []
        self._bathrooms = []
        self._ventilations = []
        self._hds = []
        for index, item in enumerate(devices, start=1):
            physics = item.get("physics") or {}
            mac = physics.get("mac") or item.get("key") or ""
            if not mac:
                continue
            device = AirCon(config)
            device.is_mesh = True
            device.mac = str(mac).upper()
            device.cloud_id = "cloud_" + "".join(c for c in device.mac.lower() if c.isalnum())
            device.room_id = int(item.get("homeId") or 0)
            device.unit_id = index
            device.alias = physics.get("name") or physics.get("model_alias") or f"云端空调 {index}"
            device.name = physics.get("model_alias") or physics.get("name") or "Daikin RA"
            device.cool_mode = device.dry_mode = device.heat_mode = device.auto_mode = 1
            device.ventilation_mode = device.temp_set = True
            device.fan_volume_auto = True
            device.soft_id = str(physics.get("soft_id") or "")
            device.cloud_gateway = item.get("mesh_gateway")
            self._apply_cloud_status(device, item.get("status") or {})
            self._aircons.append(device)
        self._ready = True
        self._heartbeat_thread = CloudPollThread(self)
        self._heartbeat_thread.start()

    def poll_cloud_status(self) -> None:
        """Refresh cloud-only Mesh entities using the authenticated socket."""
        for aircon in self.get_aircons():
            gateway = getattr(aircon, "cloud_gateway", None)
            if not gateway:
                continue
            try:
                status = self._cloud_client.get_mesh_ra_status(
                    gateway, aircon.mac, aircon.soft_id
                )
                if not status:
                    continue
                self._apply_cloud_status(aircon, status)
                for device, hook in self._status_hook:
                    if device is aircon:
                        hook()
            except Exception:
                _LOGGER.exception("Cloud Mesh status refresh failed for %s", aircon.mac)

    def handle_cloud_message(self, topic: str, payload: dict) -> None:
        """Apply cloud snapshot events and notify registered HA entities."""
        if "/event/snapshot_change" not in topic:
            return
        topic_mac = topic.split("/", 1)[0].removeprefix("RA:").upper()
        data = payload.get("data") or {}
        candidates = data.get("ra") if isinstance(data, dict) else None
        if not isinstance(candidates, list):
            candidates = [data]
        for item in candidates:
            physics = item.get("physics") or {}
            mac = str(physics.get("mac") or item.get("key") or topic_mac).upper()
            for aircon in self.get_aircons():
                if aircon.mac.upper() != mac:
                    continue
                self._apply_cloud_status(aircon, item.get("status") or item)
                for dev, hook in self._status_hook:
                    if dev is aircon:
                        hook()

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

            # Broadcast multi-protocol discovery queries
            self._socket_client.send(GetRoomInfoParam(), deadline)
            self._socket_client.send(MeshNodeQueryParam(), deadline)
            self._socket_client.send(MeshGetNodeListParam(), deadline)

            start_time = time.monotonic()
            probe_sent = False
            while True:
                # 1. Check if Mesh AC nodes discovered
                if self._config.is_mesh and self.get_aircons():
                    _log("Mesh Smart AC node discovery completed!")
                    break

                # 2. Check if Standard VRV multi-room discovery completed
                if (
                    self._rooms is not None
                    and self._aircons is not None
                    and self._new_aircons is not None
                    and self._bathrooms is not None
                    and self._ventilations is not None
                    and self._hds is not None
                ):
                    _log("Standard VRV topology discovery completed!")
                    break

                # 3. Direct probe fallback if no topology received after 3 seconds
                if not probe_sent and (time.monotonic() - start_time) >= 3.0:
                    probe_sent = True
                    _log("Probing direct Mesh / Standalone AC targets...")
                    self._socket_client.send(MeshGetBasicInfoParam(1, 1))
                    self._socket_client.send(MeshGetBasicInfoParam(0, 0))

                if deadline is not None and time.monotonic() >= deadline:
                    if self.get_aircons() or (self._ventilations is not None and len(self._ventilations) > 0):
                        break
                    raise TimeoutError(
                        f"Timed out initializing DS-AIR gateway {host}:{port}"
                    )
                time.sleep(0.5)

            # Ensure all device lists are initialized
            if self._rooms is None:
                self._rooms = []
            if self._aircons is None:
                self._aircons = []
            if self._new_aircons is None:
                self._new_aircons = []
            if self._bathrooms is None:
                self._bathrooms = []
            if self._ventilations is None:
                self._ventilations = []
            if self._hds is None:
                self._hds = []

            for i in self._aircons:
                for j in self._rooms:
                    if i.room_id == j.id:
                        if not i.alias:
                            i.alias = j.alias
                            if i.unit_id:
                                i.alias += str(i.unit_id)
            for i in self._new_aircons:
                for j in self._rooms:
                    if i.room_id == j.id:
                        if not i.alias:
                            i.alias = j.alias
                            if i.unit_id:
                                i.alias += str(i.unit_id)
            for i in self._bathrooms:
                for j in self._rooms:
                    if i.room_id == j.id:
                        if not i.alias:
                            i.alias = j.alias
                            if i.unit_id:
                                i.alias += str(i.unit_id)
            if self._ventilations is not None:
                for i in self._ventilations:
                    for j in self._rooms:
                        if i.room_id == j.id:
                            if not i.alias:
                                i.alias = j.alias
                                if i.unit_id:
                                    i.alias += str(i.unit_id)
            if self._hds is not None:
                for i in self._hds:
                    for j in self._rooms:
                        if i.room_id == j.id:
                            if not i.alias:
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
        self._cloud_only = False

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

    def set_cloud_client(self, cloud_client) -> None:
        """Set the Daikin China cloud client for MQTT synchronization."""
        self._cloud_client = cloud_client

    def control(self, aircon: AirCon, status: AirConStatus):
        control_ok = True
        if not self._cloud_only:
            p = AirConControlParam(aircon, status)
            self.send_msg(p)

        # Dispatch to Daikin Cloud MQTT if configured
        cloud_client = getattr(self, "_cloud_client", None)
        if cloud_client is not None:
            mac = getattr(aircon, "mac", "")
            if mac:
                try:
                    gateway = getattr(aircon, "cloud_gateway", None)
                    if self._cloud_only and gateway:
                        control_ok = cloud_client.control_mesh_ra(
                            gateway, aircon, status, self._config
                        )
                    else:
                        control_ok = cloud_client.control_ra(
                            mac=mac,
                            switch=int(status.switch) if status.switch is not None else None,
                            mode=int(status.mode) if status.mode is not None else None,
                            temp=(float(status.setted_temp) / 10) if status.setted_temp is not None else None,
                            volume=int(status.air_flow) if status.air_flow is not None else None,
                            direction1=int(status.fan_direction1) if status.fan_direction1 is not None else None,
                            direction2=int(status.fan_direction2) if status.fan_direction2 is not None else None,
                        )
                    if not control_ok:
                        _LOGGER.error("Cloud control was not acknowledged for %s", mac)
                except Exception as e:
                    control_ok = False
                    _LOGGER.error(f"Cloud control failed: {e}")

        if control_ok and aircon.status is not None:
            if status.switch is not None:
                aircon.status.switch = status.switch
            if status.mode is not None:
                aircon.status.mode = status.mode
            if status.setted_temp is not None:
                aircon.status.setted_temp = status.setted_temp
            if status.air_flow is not None:
                aircon.status.air_flow = status.air_flow
            for dev, hook in self._status_hook:
                if (dev.mac and dev.mac == aircon.mac) or (dev.room_id == aircon.room_id and dev.unit_id == aircon.unit_id):
                    try:
                        hook()
                    except Exception as e:
                        _LOGGER.error(f"Status hook error on control: {e}")
        return control_ok

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
        if self._socket_client is None:
            raise RuntimeError("Local gateway is not configured")
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

    def register_mesh_node(
        self, mac: str, node_type: int, room_id: int, unit_id: int, name: str, code: str, soft_id: str = ""
    ):
        """Register a discovered Mesh Smart AC node."""
        self._config.is_mesh = True
        self._config.is_vrv = False
        if self._rooms is None:
            self._rooms = []
        if self._aircons is None:
            self._aircons = []
        if self._new_aircons is None:
            self._new_aircons = []
        if self._bathrooms is None:
            self._bathrooms = []
        if self._ventilations is None:
            self._ventilations = []
        if self._hds is None:
            self._hds = []

        room = None
        for r in self._rooms:
            if r.id == room_id:
                room = r
                break
        if room is None:
            room = Room()
            room.id = room_id
            room.name = name
            room.alias = name
            self._rooms.append(room)

        aircon = None
        for ac in self._aircons:
            if (mac and ac.mac == mac) or (ac.room_id == room_id and ac.unit_id == unit_id):
                aircon = ac
                break

        if aircon is None:
            aircon = AirCon(self._config)
            aircon.is_mesh = True
            aircon.mac = mac
            aircon.soft_id = soft_id
            aircon.room_id = room_id
            aircon.unit_id = unit_id
            aircon.alias = name
            aircon.name = name
            aircon.temp_set = True
            aircon.cool_mode = 1
            aircon.heat_mode = 1
            aircon.dry_mode = 1
            aircon.ventilation_mode = 1
            aircon.auto_mode = 1
            room.air_con = aircon
            self._aircons.append(aircon)

        # Immediately query live telemetry via RA.INFO
        self.send_msg(MeshRAInfoParam(mac, soft_id))

    def update_mesh_status(
        self, mac: str, room_id: int, unit_id: int, status: AirConStatus, name: str = "", soft_id: str = ""
    ):
        """Update telemetry for a Mesh Smart AC node."""
        if self._aircons is None:
            self._aircons = []
        aircon = None
        for ac in self._aircons:
            if (mac and ac.mac == mac) or (ac.room_id == room_id and ac.unit_id == unit_id):
                aircon = ac
                break

        if aircon is None:
            self.register_mesh_node(
                mac=mac,
                node_type=34,
                room_id=room_id,
                unit_id=unit_id,
                name=name or f"AC_{room_id}_{unit_id}",
                code="00",
                soft_id=soft_id,
            )
            for ac in self._aircons:
                if (mac and ac.mac == mac) or (ac.room_id == room_id and ac.unit_id == unit_id):
                    aircon = ac
                    break

        if aircon is not None:
            if soft_id:
                aircon.soft_id = soft_id
            if status.current_temp is not None:
                aircon.status.current_temp = status.current_temp
            if status.setted_temp is not None:
                aircon.status.setted_temp = status.setted_temp
            if status.switch is not None:
                aircon.status.switch = status.switch
            if status.mode is not None:
                aircon.status.mode = status.mode
            if status.air_flow is not None:
                aircon.status.air_flow = status.air_flow
            if status.fan_direction1 is not None:
                aircon.status.fan_direction1 = status.fan_direction1
            if status.fan_direction2 is not None:
                aircon.status.fan_direction2 = status.fan_direction2

            for item in self._status_hook:
                hook_dev, func = item
                if hook_dev.room_id == room_id and hook_dev.unit_id == unit_id:
                    try:
                        func(status=aircon.status)
                    except Exception as e:
                        _log(f"mesh status hook error: {e}")

        if self.state_change_listener is not None:
            try:
                self.state_change_listener()
            except Exception as e:
                _log(f"state_change_listener error: {e}")

    def set_mesh_node_list(self, gw_mac: str, nodes: list[str]):
        """Handle Mesh Node list discovery frame."""
        self._config.is_mesh = True
        self._config.is_vrv = False
        if not nodes:
            self.send_msg(MeshGetBasicInfoParam(1, 1))
        for _ in nodes:
            self.send_msg(MeshGetBasicInfoParam(1, 1))

    def poll_status(self):
        if self._aircons is not None:
            for i in self._aircons:
                if i.is_mesh:
                    p = MeshRAInfoParam(i.mac, getattr(i, "soft_id", ""))
                    self.send_msg(p)
                else:
                    p = AirConQueryStatusParam()
                    p.target = EnumDevice.AIRCON
                    p.device = i
                    self.send_msg(p)
        if self._new_aircons is not None:
            for i in self._new_aircons:
                p = AirConQueryStatusParam()
                p.target = EnumDevice.NEWAIRCON
                p.device = i
                self.send_msg(p)
        if self._bathrooms is not None:
            for i in self._bathrooms:
                p = AirConQueryStatusParam()
                p.target = EnumDevice.BATHROOM
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
        if self._config is None or not self._config.is_mesh:
            p = Sensor2InfoParam()
            self.send_msg(p)

    def update_aircon(self, target: EnumDevice, room: int, unit: int, **kwargs):
        li = self._status_hook
        for item in li:
            i, func = item
            if (
                i.unit_id == unit
                and i.room_id == room
                and (get_device_by_aircon(i) == target or i.is_mesh)
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
