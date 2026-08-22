"""Daikin China (金制空气) Cloud API Client.

Reverse-engineered from NLSPSmartClient APK.
Supports dynamic mTLS client certificate fetching, authentication, device discovery,
and cloud synchronization.
"""

from __future__ import annotations

import json
import logging
import os
import random
import socket
import ssl
import struct
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from typing import Any

_LOGGER = logging.getLogger(__name__)

CLOUD_AUTH_URL = "https://newlifemulti.daikin-china.com.cn:443/v2/"
CLOUD_BASE_URL = "https://newlifemulti.daikin-china.com.cn:4443/v2/"


def gen_phone_key() -> str:
    """Generate a random client identifier like the official app.

    App: "Android_" + 20 random chars (digits + a-z minus l/o/1/0) + '-' + epoch_ms.
    This same value is used as MQTT client_id.
    """
    chars = "1234567890abcdefghijkmnpqrstuvwxyz"
    rand = "".join(random.choice(chars) for _ in range(20))
    return f"Android_{rand}-{int(time.time() * 1000)}"


def calc_cert_password(client_id: str) -> str:
    """Calculate CRC-16 password required for dynamic client certificate download."""
    crc = 0
    for b in client_id.encode("utf-8"):
        crc = crc ^ (b & 0xFF)
        for _ in range(8):
            if (crc & 1) == 1:
                crc = crc ^ 0x10811
            crc = (crc >> 1) & 0xFFFFFFFF
    return f"{crc & 0xFFFF:04X}"


class DaikinCloudClient:
    """Client for Daikin China / 金制空气 Cloud REST & MQTT API."""

    def __init__(self, username: str | None = None, password: str | None = None, token: str | None = None):
        self.username = username
        self.password = password
        self.access_token = token
        self.refresh_token_val: str | None = None
        self.token_expire_time: float = 0
        self._ssl_context: ssl.SSLContext | None = None
        self._client_id = f"ha_dsair_{int(time.time())}"
        self._phone_key = gen_phone_key()
        self._cert_path: str | None = None
        self._key_path: str | None = None
        self._mqtt_client = None
        self._mqtt_connected = False
        self._mqtt_ready = threading.Event()
        self._home_id: int | None = None
        self._message_callback = None
        self._nlc_id: str | None = None
        self._mqtt_pending: dict[str, tuple[threading.Event, dict[str, Any]]] = {}
        self._mqtt_pending_lock = threading.Lock()

    def ensure_ssl_context(self) -> ssl.SSLContext:
        """Fetch client certificates dynamically and build mTLS SSL context."""
        if self._ssl_context is not None:
            return self._ssl_context

        # Request certificate information from Daikin Auth Endpoint
        pwd = calc_cert_password(self._client_id)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        # 1. Download PEM cert
        req_pem = urllib.request.Request(
            urllib.parse.urljoin(CLOUD_AUTH_URL, "home/getCertificateInfo"),
            data=json.dumps({
                "clientId": self._client_id,
                "password": pwd,
                "fileType": "PEM",
                "clientType": "APP"
            }).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "okhttp/4.9.1"}
        )
        with urllib.request.urlopen(req_pem, context=ctx, timeout=10) as resp:
            data_pem = json.loads(resp.read().decode("utf-8"))
        pem_url = data_pem["data"]["downloadInfo"]["resourcesPath"]

        with urllib.request.urlopen(pem_url, timeout=10) as resp:
            pem_bytes = resp.read()

        # 2. Download Key
        req_key = urllib.request.Request(
            urllib.parse.urljoin(CLOUD_AUTH_URL, "home/getCertificateInfo"),
            data=json.dumps({
                "clientId": self._client_id,
                "password": pwd,
                "fileType": "KEY",
                "clientType": "APP"
            }).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "okhttp/4.9.1"}
        )
        with urllib.request.urlopen(req_key, context=ctx, timeout=10) as resp:
            data_key = json.loads(resp.read().decode("utf-8"))
        key_url = data_key["data"]["downloadInfo"]["resourcesPath"]

        with urllib.request.urlopen(key_url, timeout=10) as resp:
            key_bytes = resp.read()

        # Save to temp files
        tf_cert = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
        tf_cert.write(pem_bytes)
        tf_cert.close()

        tf_key = tempfile.NamedTemporaryFile(delete=False, suffix=".key")
        tf_key.write(key_bytes)
        tf_key.close()

        self._cert_path = tf_cert.name
        self._key_path = tf_key.name

        # Build mTLS SSL context
        m_ctx = ssl.create_default_context()
        m_ctx.check_hostname = False
        m_ctx.verify_mode = ssl.CERT_NONE
        m_ctx.set_ciphers("DEFAULT@SECLEVEL=0")
        m_ctx.load_cert_chain(certfile=self._cert_path, keyfile=self._key_path)

        self._ssl_context = m_ctx
        return self._ssl_context

    def request(self, endpoint: str, data: dict | None = None, is_form: bool = False, use_token: bool = True) -> dict:
        """Send authenticated request to Daikin Cloud API."""
        m_ctx = self.ensure_ssl_context()
        url = urllib.parse.urljoin(CLOUD_BASE_URL, endpoint)

        headers = {
            "User-Agent": "okhttp/4.9.1"
        }
        if use_token and self.access_token:
            headers["token"] = self.access_token

        if is_form and data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            payload = urllib.parse.urlencode(data).encode("utf-8")
        elif data is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
            payload = json.dumps(data).encode("utf-8")
        else:
            headers["Content-Type"] = "application/json; charset=utf-8"
            payload = b"{}"

        req = urllib.request.Request(url, data=payload, headers=headers)
        try:
            with urllib.request.urlopen(req, context=m_ctx, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
                res = json.loads(raw)
                _LOGGER.debug(
                    "Daikin Cloud API [%s] response: %s",
                    endpoint,
                    self._redact_secrets(res),
                )
                return res
        except Exception as e:
            _LOGGER.error("Daikin Cloud API [%s] error: %s", endpoint, e)
            return {"code": -1, "description": str(e)}

    @classmethod
    def _redact_secrets(cls, value):
        """Return a log-safe copy of an API response."""
        if isinstance(value, dict):
            return {
                key: (
                    "<redacted>"
                    if any(word in key.lower() for word in ("token", "password", "secret"))
                    else cls._redact_secrets(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [cls._redact_secrets(item) for item in value]
        return value

    def login(self, username: str | None = None, password: str | None = None) -> bool:
        """Authenticate user with username (mobile) and password."""
        user = username or self.username
        pwd = password or self.password
        if not user or not pwd:
            _LOGGER.error("Daikin Cloud Login requires mobile and password")
            return False

        try:
            res = self.request("app/nlcLoginV2", data={
                "authId": user,
                "password": pwd,
                "pushId": self._client_id
            }, is_form=True, use_token=False)

            if res.get("code") == 0 and res.get("data"):
                token_data = res["data"]
                self.access_token = token_data.get("accessToken")
                self.refresh_token_val = token_data.get("refreshToken")
                expire_in = token_data.get("accessExpireIn", 7200)
                # Current API returns an absolute epoch in milliseconds; older
                # server builds returned a duration in seconds.
                self.token_expire_time = (
                    float(expire_in) / 1000 - 300
                    if float(expire_in) > 10_000_000_000
                    else time.time() + float(expire_in) - 300
                )
                _LOGGER.info("Daikin Cloud login successful (user: %s)", user)
                return True
            else:
                _LOGGER.error("Daikin Cloud login failed: %s", res.get("description", res))
                return False
        except Exception as e:
            _LOGGER.error("Daikin Cloud login exception: %s", e)
            return False

    def list_homes(self) -> list[dict]:
        """Fetch list of user homes."""
        res = self.request("home/listHomeByLoginUser")
        if res.get("code") == 0:
            return res.get("data", [])
        return []

    def get_home_details(self, home_id: int) -> dict:
        """Fetch detailed devices and topology for a specific home."""
        res = self.request("home/getHome", data={"homeId": home_id})
        if res.get("code") == 0:
            return res.get("data", {})
        return {}

    def get_direct_devices(self, home_id: int) -> list[dict]:
        """Fetch directly connected RA devices, as used by the official app."""
        res = self.request("snapshot/direct/getByHomeId", data={"homeId": home_id})
        if res.get("code") != 0:
            _LOGGER.debug(
                "Daikin direct snapshot failed for home %s: code=%s description=%s",
                home_id,
                res.get("code"),
                res.get("description"),
            )
            return []
        data = res.get("data") or {}
        return data.get("ra") or data.get("RA") or []

    def list_home_gateways(self, home_id: int) -> list[dict]:
        """Return gateway topology for a home (NLSPSmartClient listGatewayAuth)."""
        res = self.request("home/listGatewayAuth", data={"homeId": home_id})
        if res.get("code") == 0:
            return res.get("data") or []
        _LOGGER.warning(
            "Daikin gateway discovery failed for home %s: code=%s description=%s",
            home_id,
            res.get("code"),
            res.get("description"),
        )
        return []

    def get_gateway_devices(self, terminal_mac: str) -> list[dict]:
        """Fetch RA children below an IPBox/Smart gateway."""
        res = self.request(
            "snapshot/ipbox/getFullSub", data={"terminalMac": terminal_mac}
        )
        if res.get("code") != 0:
            _LOGGER.debug(
                "Daikin full gateway snapshot unavailable for %s: code=%s",
                terminal_mac,
                res.get("code"),
            )
            return []
        data = res.get("data") or {}
        return data.get("ra") or data.get("RA") or []

    def discover(self) -> tuple[list[dict], list[dict]]:
        """Return homes and all cloud RA devices with their home metadata."""
        homes = self.list_homes()
        devices: list[dict] = []
        for home in homes:
            home_id = home.get("homeId")
            if not home_id:
                continue
            home_devices = self.get_direct_devices(int(home_id))
            for gateway in self.list_home_gateways(int(home_id)):
                terminal_mac = gateway.get("gatewayMac") or gateway.get("gatewayKey")
                if int(gateway.get("gatewayType") or 0) == 2:
                    home_devices.extend(self._mesh_ra_devices(gateway))
                elif terminal_mac:
                    home_devices.extend(self.get_gateway_devices(str(terminal_mac)))

            seen: set[str] = set()
            for device in home_devices:
                item = dict(device)
                physics = item.get("physics") or {}
                key = str(physics.get("mac") or item.get("key") or "").upper()
                if not key or key in seen:
                    continue
                seen.add(key)
                item["homeId"] = int(home_id)
                item["homeName"] = home.get("homeName", "")
                devices.append(item)
        return homes, devices

    def get_mesh_devices(self, mesh_id: str) -> list[dict]:
        """Fetch Mesh Hub devices using the form request used by the app."""
        res = self.request(
            "mesh/getMeshDeviceList",
            data={"meshId": mesh_id, "pageNum": "1", "pageSize": "100"},
            is_form=True,
        )
        if res.get("code") == 0:
            return res.get("data", {}).get("deviceList", [])
        _LOGGER.warning(
            "Daikin Mesh discovery failed for %s: code=%s description=%s",
            mesh_id,
            res.get("code"),
            res.get("description"),
        )
        return []

    @staticmethod
    def _format_mac(value: str) -> str:
        clean = "".join(char for char in str(value) if char.isalnum()).upper()
        if len(clean) == 12:
            return ":".join(clean[index : index + 2] for index in range(0, 12, 2))
        return str(value).replace("-", ":").upper()

    def _mesh_ra_devices(self, gateway: dict) -> list[dict]:
        """Convert Mesh device-list RA records to the common cloud RA shape."""
        mesh_id = gateway.get("gatewayKey") or gateway.get("gatewayMac")
        if not mesh_id:
            return []
        result = []
        for item in self.get_mesh_devices(str(mesh_id)):
            if int(item.get("deviceType") or 0) != 34:  # APK DeviceType.RA
                continue
            mac = self._format_mac(item.get("deviceMac") or "")
            if not mac:
                continue
            status = self.get_mesh_ra_status(gateway, mac, str(item.get("softId") or ""))
            result.append(
                {
                    "key": mac,
                    "physics": {
                        "mac": mac,
                        "name": item.get("deviceName"),
                        "soft_id": item.get("softId"),
                        "connect_type": 1,
                    },
                    "status": status or {},
                    "online": 1,
                    "mesh_gateway": dict(gateway),
                }
            )
        return result

    @staticmethod
    def _socket_frame(cmd: int, subbody: bytes = b"", command_id: int = 1) -> bytes:
        tail = (
            b"\x0d\x00\x00\x00"
            + struct.pack("<I", command_id)
            + b"\x00"
            + struct.pack("<I", 0)
            + b"\x01"
            + struct.pack("<H", cmd)
            + subbody
            + b"\x03"
        )
        return b"\x02" + struct.pack("<H", len(tail) - 1) + tail

    @staticmethod
    def _recv_socket_frame(sock: socket.socket) -> bytes:
        header = b""
        while len(header) < 3:
            chunk = sock.recv(3 - len(header))
            if not chunk:
                raise ConnectionError("Daikin remote socket closed")
            header += chunk
        remaining = struct.unpack("<H", header[1:3])[0] + 1
        body = b""
        while len(body) < remaining:
            chunk = sock.recv(remaining - len(body))
            if not chunk:
                raise ConnectionError("Daikin remote socket closed")
            body += chunk
        return header + body

    def get_mesh_ra_status(self, gateway: dict, mac: str, soft_id: str) -> dict:
        """Read live Mesh RA state through the app's authenticated cloud socket."""
        host = gateway.get("socketIp")
        port = int(gateway.get("socketPort") or 8001)
        gateway_id = str(gateway.get("gatewayKey") or gateway.get("gatewayMac") or "")
        if not host or not gateway_id:
            return {}
        if not self._nlc_id:
            user = self.request("home/getUserInfo").get("data") or {}
            self._nlc_id = str(user.get("nlcId") or "")
        nlc_id = self._nlc_id
        if not nlc_id:
            return {}
        clean_mac = "".join(char for char in mac if char.isalnum())
        try:
            mac_bytes = bytes.fromhex(clean_mac)
            soft_bytes = bytes.fromhex(soft_id)
        except ValueError:
            return {}
        login = (
            b"\x02"
            + struct.pack("<H", len(nlc_id.encode()) + len(gateway_id.encode()) + 3)
            + b"\x04"
            + bytes([len(nlc_id.encode())])
            + nlc_id.encode()
            + bytes([len(gateway_id.encode())])
            + gateway_id.encode()
        )
        # RA.INFO inner request: Mesh target (12/34), RA type/count/MAC/softId.
        inner_tail = (
            b"\x0d\x00\x00\x00\x01\x00\x00\x00"
            + b"\x0c\x22\x00\x00\x00\x01\x01\x00"
            + b"\x22\x01"
            + mac_bytes
            + soft_bytes
            + b"\x03"
        )
        inner = b"\x02" + struct.pack("<H", len(inner_tail) - 1) + inner_tail
        transfer = self._socket_frame(0xA001, struct.pack("<H", len(inner)) + inner, 2)
        try:
            with socket.create_connection((str(host), port), timeout=8) as sock:
                sock.settimeout(8)
                sock.sendall(self._socket_frame(0x10, login))
                login_response = self._recv_socket_frame(sock)
                if len(login_response) < 21 or login_response[-2] != 1:
                    return {}
                sock.sendall(transfer)
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    packet = self._recv_socket_frame(sock)
                    # TRANSFER response contains ushort length then the inner frame.
                    marker = packet.find(b"\x02", 19)
                    if marker < 0 or len(packet) < marker + 22:
                        continue
                    nested = packet[marker:]
                    if nested[11] != 0x0C or nested[12:16] != b"\x22\x00\x00\x00":
                        continue
                    if nested[17:19] != b"\x01\x00":
                        continue
                    payload = nested[19:-2]
                    if len(payload) < 16 or payload[0] != 0x22:
                        continue
                    pos = 2 + 6 + 4
                    pos += 1  # controlEnable
                    flags = payload[pos]
                    pos += 3  # controlType1, controlType2, data length
                    result: dict[str, Any] = {}
                    if flags & 1:
                        result["switches"] = payload[pos]
                        pos += 1
                    if flags & 2:
                        result["mode"] = {1: 3, 2: 1, 3: 0, 4: 4, 6: 2}.get(payload[pos])
                        pos += 1
                    if flags & 4:
                        result["temp"] = (payload[pos] - 28) / 2
                        pos += 1
                    if flags & 8:
                        raw_volume = struct.unpack("<H", payload[pos : pos + 2])[0]
                        result["volume"] = {1: 0, 3: 1, 5: 2, 7: 3, 9: 4, 10: 5, 11: 6}.get(raw_volume, 5)
                    return {key: value for key, value in result.items() if value is not None}
        except (OSError, ValueError, struct.error) as err:
            _LOGGER.warning("Daikin Mesh live-state query failed for %s: %s", mac, err)
        return {}

    def control_mesh_ra(self, gateway: dict, aircon, status, config) -> bool:
        """Control a Mesh RA through the remote socket and verify by readback."""
        from .ds_air_service.param import AirConControlParam

        host = gateway.get("socketIp")
        port = int(gateway.get("socketPort") or 8001)
        gateway_id = str(gateway.get("gatewayKey") or gateway.get("gatewayMac") or "")
        if not host or not gateway_id:
            return False
        if not self._nlc_id:
            user = self.request("home/getUserInfo").get("data") or {}
            self._nlc_id = str(user.get("nlcId") or "")
        nlc_id = self._nlc_id or ""
        if not nlc_id:
            return False

        nlc_bytes = nlc_id.encode()
        gateway_bytes = gateway_id.encode()
        login = (
            b"\x02"
            + struct.pack("<H", len(nlc_bytes) + len(gateway_bytes) + 3)
            + b"\x04"
            + bytes([len(nlc_bytes)])
            + nlc_bytes
            + bytes([len(gateway_bytes)])
            + gateway_bytes
        )
        inner = AirConControlParam(aircon, status).to_string(config)
        transfer = self._socket_frame(0xA001, struct.pack("<H", len(inner)) + inner, 2)
        try:
            with socket.create_connection((str(host), port), timeout=8) as sock:
                sock.settimeout(8)
                sock.sendall(self._socket_frame(0x10, login))
                login_response = self._recv_socket_frame(sock)
                if len(login_response) < 21 or login_response[-2] != 1:
                    return False
                sock.sendall(transfer)
                # At minimum require the cloud relay to acknowledge the transfer.
                self._recv_socket_frame(sock)
        except (OSError, ValueError, struct.error) as err:
            _LOGGER.error("Daikin Mesh control transport failed for %s: %s", aircon.mac, err)
            return False

        # The relay ACK only proves delivery. Verify the requested values using
        # a fresh RA.INFO query before HA updates its optimistic state.
        time.sleep(0.4)
        actual = self.get_mesh_ra_status(gateway, aircon.mac, aircon.soft_id)
        expected = {
            "switches": int(status.switch) if status.switch is not None else None,
            "mode": int(status.mode) if status.mode is not None else None,
            "temp": (
                float(status.setted_temp) / 10
                if status.setted_temp is not None
                else None
            ),
            "volume": int(status.air_flow) if status.air_flow is not None else None,
        }
        for key, value in expected.items():
            if value is not None and actual.get(key) != value:
                _LOGGER.warning(
                    "Daikin Mesh control readback mismatch for %s: %s expected=%s actual=%s",
                    aircon.mac,
                    key,
                    value,
                    actual.get(key),
                )
                return False
        return bool(actual)

    def get_emq_token(self, home_id: int | None = None, phone_key: str | None = None) -> dict | None:
        """Fetch EMQX MQTT token and broker credentials.

        Mirrors the official app: normal home users call home/authMqtt with a
        JSON body {"homeId": <int>, "phoneKey": "<Android_...>"}. The
        app/getEmqToken endpoint is only used for installer/IPBox mode.
        """
        phone_key = phone_key or self._phone_key
        if not home_id:
            try:
                homes = self.list_homes()
                if homes and isinstance(homes, list) and len(homes) > 0:
                    home_id = homes[0].get("homeId")
            except Exception as e:
                _LOGGER.warning("Could not fetch homeId for authMqtt: %s", e)

        res = self.request("home/authMqtt", data={
            "homeId": int(home_id) if home_id else 0,
            "phoneKey": phone_key,
        })
        _LOGGER.debug(
            "home/authMqtt completed (homeId=%s, code=%s)",
            home_id,
            res.get("code"),
        )
        if isinstance(res, dict) and res.get("code") == 0:
            return res.get("data")
        return None

    def start_mqtt(
        self,
        home_id: int | None = None,
        message_callback=None,
        device_macs: list[str] | None = None,
    ) -> bool:
        """Connect to Daikin Cloud EMQX broker.

        Matches the official app: client_id = phoneKey ("Android_..."),
        username = deviceKey ("HOME:<homeId>"), password = MQTT token.
        """
        try:
            # 1. Obtain homeId for deviceKey
            homes = self.list_homes()
            if home_id is None and homes:
                home_id = homes[0].get("homeId")
            self._home_id = int(home_id) if home_id else None
            self._message_callback = message_callback

            device_key = f"HOME:{home_id}" if home_id else ""
            phone_key = self._phone_key

            # 2. Fetch token with homeId and phoneKey
            token_data = self.get_emq_token(home_id=home_id, phone_key=phone_key)
            if not token_data or not token_data.get("token"):
                _LOGGER.error("Failed to fetch EMQX token from Daikin Cloud: %s", token_data)
                return False

            token = token_data.get("token")
            username = device_key
            client_id = phone_key
            host = "newlifemulti-nb-core.daikin-china.com.cn"
            port = 8886

            import paho.mqtt.client as mqtt

            try:
                self._mqtt_client = mqtt.Client(
                    mqtt.CallbackAPIVersion.VERSION2, client_id=client_id, protocol=mqtt.MQTTv31
                )
            except Exception:
                self._mqtt_client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv31)

            self._mqtt_client.tls_set_context(self.ensure_ssl_context())
            self._mqtt_client.username_pw_set(username, token)

            def on_connect(client, userdata, flags, rc, properties=None):
                _LOGGER.info("Connected to Daikin Cloud MQTT Broker (%s:%s as %s), rc=%s", host, port, client_id, rc)
                success = int(getattr(rc, "value", rc)) == 0
                self._mqtt_connected = success
                if success:
                    self._mqtt_ready.set()
                    # Snapshot events update HA and service responses acknowledge commands.
                    for mac in device_macs or []:
                        key = mac.upper()
                        client.subscribe(f"RA:{key}/app_mqtt/event/snapshot_change", qos=1)
                        client.subscribe(f"RA:{key}/app_mqtt/service_response/control/{client_id}", qos=1)

            def on_message(client, userdata, msg):
                payload = msg.payload.decode("utf-8", "ignore")
                _LOGGER.debug("Daikin Cloud MQTT RX [%s]: %s", msg.topic, payload)
                try:
                    decoded = json.loads(payload)
                except (TypeError, ValueError):
                    _LOGGER.warning("Ignoring invalid Daikin MQTT JSON on %s", msg.topic)
                    return
                client_token = decoded.get("client_token")
                if client_token:
                    with self._mqtt_pending_lock:
                        pending = self._mqtt_pending.get(str(client_token))
                    if pending is not None:
                        event, response = pending
                        response.update(decoded)
                        event.set()
                if self._message_callback is not None:
                    try:
                        self._message_callback(msg.topic, decoded)
                    except Exception:
                        _LOGGER.exception("Unable to process Daikin Cloud MQTT message")

            def on_disconnect(client, userdata, flags, rc, properties=None):
                self._mqtt_connected = False
                self._mqtt_ready.clear()

            self._mqtt_client.on_connect = on_connect
            self._mqtt_client.on_message = on_message
            self._mqtt_client.on_disconnect = on_disconnect

            self._mqtt_client.connect_async(host, port, keepalive=60)
            self._mqtt_client.loop_start()
            return self._mqtt_ready.wait(10)
        except Exception as e:
            _LOGGER.error("Failed to start Daikin Cloud MQTT client: %s", e)
            return False

    def stop_mqtt(self) -> None:
        """Stop MQTT client."""
        if getattr(self, "_mqtt_client", None) is not None:
            try:
                self._mqtt_client.loop_stop()
                self._mqtt_client.disconnect()
            except Exception:
                pass
            self._mqtt_client = None
            self._mqtt_connected = False
            self._mqtt_ready.clear()

    def close(self) -> None:
        """Release MQTT and temporary certificate files."""
        self.stop_mqtt()
        for path in (self._cert_path, self._key_path):
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass
        self._cert_path = self._key_path = None

    def control_ra(
        self,
        mac: str,
        switch: int | None = None,
        mode: int | None = None,
        temp: float | None = None,
        volume: int | None = None,
        direction1: int | None = None,
        direction2: int | None = None,
    ) -> bool:
        """Send RA AC control command via MQTT."""
        if not getattr(self, "_mqtt_connected", False) or getattr(self, "_mqtt_client", None) is None:
            if not self.start_mqtt():
                _LOGGER.error("Cannot control RA AC: MQTT client not connected")
                return False

        clean_mac = mac.replace("-", ":").upper()
        topic = f"RA:{clean_mac}/app_mqtt/service/control"
        now = int(time.time() * 1000)
        data = {}
        for key, value, cast in (
            ("switches", switch, int), ("mode", mode, int),
            ("volume", volume, int), ("temp", temp, float),
            ("direction1", direction1, int), ("direction2", direction2, int),
        ):
            if value is not None:
                data[key] = cast(value)
        # NLSPSmartClient MqttBaseModel: control data must be nested and the
        # REST access token is also required in the MQTT message envelope.
        client_token = f"android-{now}-{random.randint(1000000000, 9999999999)}"
        payload = {
            "data": data,
            "client_token": client_token,
            "timestamp": now,
            "access_token": self.access_token,
        }

        response_event = threading.Event()
        response: dict[str, Any] = {}
        with self._mqtt_pending_lock:
            self._mqtt_pending[client_token] = (response_event, response)
        try:
            msg_str = json.dumps(payload, separators=(",", ":"))
            _LOGGER.debug(
                "Daikin Cloud MQTT TX [%s] fields=%s client_token=%s...",
                topic,
                sorted(data),
                client_token[:24],
            )
            info = self._mqtt_client.publish(topic, msg_str, qos=1)
            info.wait_for_publish(timeout=10)
            if info.rc != 0 or not info.is_published():
                return False
            if not response_event.wait(10):
                _LOGGER.warning("Timed out waiting for Daikin MQTT control response")
                return False
            code = response.get("code")
            try:
                success = int(code) == 0
            except (TypeError, ValueError):
                success = False
            if not success:
                _LOGGER.warning(
                    "Daikin MQTT control rejected: code=%s description=%s",
                    code,
                    response.get("description") or response.get("msg"),
                )
                return False
            return True
        except Exception as e:
            _LOGGER.error("Failed to publish RA control message via MQTT: %s", e)
            return False
        finally:
            with self._mqtt_pending_lock:
                self._mqtt_pending.pop(client_token, None)
