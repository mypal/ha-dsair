#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Daikin DS-AIR / 金制空气 (NLS-P Smart Client) Local Protocol Test Suite
========================================================================
Supports:
  1. UDP Broadcast Discovery (UDP 8111)
  2. TCP Socket Connection & Mina Frame Protocol (TCP 8008 / 8009)
  3. Protocol Handshake (0xA000 / SYS_HAND_SHAKE)
  4. Heartbeat (0x0001 / SYS_ACK)
  5. Room & Device Topology Discovery (0x0030 / SYS_GET_ROOM_INFO, 0x0130 / SYS_GET_ROOM_INFO_V1)
  6. Standalone / Direct Air Conditioner (AC) Probing (No Room Topology required)
  7. VRV AC (8,18), New AirCon (8,23), RA 分体机 (10,34), LSM 线控器 (10,33), Bath AC (8,24)
  8. Fresh Air / Ventilation (8,20) & MiniVAM (8,28) Status & Composite Situation
  9. Air Quality Sensors (Temp, Humidity, PM2.5, CO2, TVOC, VOC, HCHO)
  10. Floor Heating / Bath Heater (HD) Status & Control
  11. Direct AC & Ventilation Control
  12. Real-time Live Event Streaming Monitor
  13. Exhaustive Opcode & Device Target Scanner (--probe-all)
  14. Custom Raw Command Sender (--custom-cmd)
  15. Offline Frame Encoder/Decoder & UDP 8111 Self-Test Suite
"""

from __future__ import annotations

import argparse
import logging
import os
import select
import socket
import struct
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union

# Setup logger
logger = logging.getLogger("dsair_local_test")


def setup_logging(debug: bool = False):
    """Configure console logging level and format."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )


# ---------------------------------------------------------------------------
# Protocol Constants
# ---------------------------------------------------------------------------
STX = 0x02
ETX = 0x03
DEFAULT_TCP_PORTS = [8008, 8009]
DEFAULT_UDP_PORT = 8111

# Device Categories & Type IDs (Category, TypeID)
DEV_SYSTEM = (0, 0)
DEV_AIRCON = (8, 18)
DEV_GEOTHERMIC = (8, 19)
DEV_VENTILATION = (8, 20)
DEV_HD = (8, 22)
DEV_NEWAIRCON = (8, 23)
DEV_BATHROOM = (8, 24)
DEV_SENSOR = (8, 25)
DEV_SMALL_VAM = (8, 28)
DEV_SECURITY_MONITOR = (8, 49)
DEV_SMART_HCHO = (8, 50)
DEV_LSM = (10, 33)
DEV_RA = (10, 34)
DEV_IP_MESH_COMMON = (10, 47)
DEV_SLEEP_SENSOR = (10, 48)
DEV_HUMIDIFIER = (10, 50)
DEV_MESHID_LSM = (12, 33)
DEV_MESHID_RA = (12, 34)
DEV_MESHID_MESH_COMMON = (12, 47)

DEVICE_NAMES: Dict[Tuple[int, int], str] = {
    (0, 0): "系统/网关 (System)",
    (8, 18): "VRV空调室内机 (VRV AirCon)",
    (8, 19): "地暖 (Geothermic)",
    (8, 20): "新风机 (Ventilation)",
    (8, 22): "金制地暖/卫浴 (HD)",
    (8, 23): "金制空调室内机 (New AirCon)",
    (8, 24): "卫浴空调 (Bathroom AC)",
    (8, 25): "空气质量传感器 (AirSensor)",
    (8, 28): "微型新风 (MiniVAM)",
    (8, 49): "安防监控 (Security Monitor)",
    (8, 50): "智能甲醛仪 (Smart HCHO)",
    (10, 33): "线控器/情景面板 (LSM)",
    (10, 34): "分体机/家用空调 (RA)",
    (10, 47): "Mesh通用设备 (Mesh Common)",
    (10, 48): "睡眠传感器 (Sleep Sensor)",
    (10, 50): "加湿器 (Humidifier)",
    (12, 33): "Mesh线控器 (Mesh LSM)",
    (12, 34): "Mesh分体机 (Mesh RA)",
    (12, 47): "Mesh通用 (Mesh Common 12)",
}

# Command Types
CMD_SYS_ACK = 0x0001
CMD_SYS_CMD_RSP = 0x0002
CMD_SYS_TIME_SYNC = 0x0005
CMD_SYS_ERR_CODE = 0x0006
CMD_SYS_GET_WEATHER = 0x0007
CMD_SYS_LOGIN = 0x0010
CMD_SYS_CHANGE_PW = 0x0011
CMD_SYS_GET_ROOM_INFO = 0x0030
CMD_SYS_GET_ROOM_INFO_V1 = 0x0130
CMD_SYS_GET_GW_INFO = 0x0050
CMD_SYS_SET_GW_INFO = 0x0051
CMD_SYS_CHECK_NEW_VERSION = 0x0055
CMD_SYS_GET_ALL_SENSOR_STATE = 0x0063
CMD_SYS_GET_ALL_SENSOR_STATE_MESH = 0x00B3
CMD_SYS_HANDSHAKE = 0xA000
CMD_SYS_HANDSHAKE_WEB = 0x00A0

CMD_AIR_STATUS_CONTROL = 0x0001
CMD_AIR_STATUS_CHANGED = 0x0002
CMD_AIR_STATUS_QUERY = 0x0003
CMD_AIR_RECOMMENDED_TEMP = 0x0004
CMD_AIR_CAPABILITY_QUERY = 0x0006
CMD_AIR_CAPABILITY_V2 = 0x0023

CMD_RA_01 = 0x0001
CMD_RA_STATUS_CHANGED = 0x0002
CMD_RA_QUERY_STATUS = 0x0003
CMD_RA_CMD_TYPE = 0x0004
CMD_RA_QUERY_CAPABILITY = 0x0006

CMD_LSM_GET_DETAIL = 0x0001
CMD_LSM_QUERY_STATUS = 0x0002
CMD_LSM_SET_STATUS = 0x0003
CMD_LSM_STATUS_CHANGED = 0x0004
CMD_LSM_QUERY_CAPABILITY = 0x0006
CMD_LSM_DETAIL_COMPLEMENT = 0x0007
CMD_LSM_WIND_SET = 0x0009
CMD_LSM_WIND_INFO = 0x000A

CMD_VAM_STATUS_CONTROL = 0x0001
CMD_VAM_STATUS_CHANGED = 0x0002
CMD_VAM_STATUS_QUERY = 0x0003
CMD_VAM_CAPABILITY_QUERY = 0x0006
CMD_VAM_COMPOSITE_QUERY = 0x0034

CMD_SENSOR_INFO_1 = 0x0051
CMD_SENSOR_INFO_2 = 0x0059
CMD_SENSOR_STATUS_2 = 0x005B
CMD_SENSOR_CHECK = 0x005C
CMD_SENSOR_HCHO_VOC = 0x005D

CMD_HD_STATUS_CONTROL = 0x0001
CMD_HD_STATUS_CHANGED = 0x0002
CMD_HD_STATUS_QUERY = 0x0003
CMD_HD_DEVICE_INFO = 0x000C

# AirCon Control Bitmask Flags
CTRL_FLAG_SWITCH = 1 << 0         # 1
CTRL_FLAG_MODE = 1 << 1           # 2
CTRL_FLAG_AIR_FLOW = 1 << 2       # 4
CTRL_FLAG_CURRENT_TEMP = 1 << 3   # 8
CTRL_FLAG_SETTED_TEMP = 1 << 4    # 16
CTRL_FLAG_FAN_DIRECTION = 1 << 5  # 32
CTRL_FLAG_HUMIDITY = 1 << 6       # 64

# AirCon Enum mappings
AC_MODES = {
    0: "制冷 (Cool)",
    1: "除湿 (Dry)",
    2: "送风 (Fan)",
    3: "自动 (Auto)",
    4: "制热 (Heat)",
    5: "除湿 (Dry)",
    6: "自动 (Auto)",
    7: "自动 (Auto)",
    8: "预热 (Preheating)",
    9: "除湿 (Dry)",
}

AC_FAN_SPEEDS = {
    0: "微风/弱 (Low)",
    1: "稍弱 (Low-Med)",
    2: "中 (Med)",
    3: "稍强 (Med-High)",
    4: "强 (High)",
    5: "自动 (Auto)",
    6: "静音 (Quiet)",
}

AC_FAN_DIRECTIONS = {
    0: "关闭/固定",
    1: "位置1 ➡️",
    2: "位置2 ↘️",
    3: "位置3 ⬇️",
    4: "位置4 ↙️",
    5: "位置5 ⬅️",
    6: "摆动 ↔️",
    7: "循环 🔄",
}

VAM_AIR_VOLUMES = {
    0: "自动 (Auto)",
    1: "弱 (Low)",
    2: "强 (High)",
}


def parse_dev_target_arg(val: str) -> Tuple[int, int]:
    """Parse string device target argument into (dev_cat, dev_type_id) tuple."""
    val_lower = val.lower().strip()
    named_map = {
        "system": DEV_SYSTEM,
        "sys": DEV_SYSTEM,
        "gw": DEV_SYSTEM,
        "aircon": DEV_AIRCON,
        "vrv": DEV_AIRCON,
        "ac": DEV_AIRCON,
        "newaircon": DEV_NEWAIRCON,
        "new_aircon": DEV_NEWAIRCON,
        "newac": DEV_NEWAIRCON,
        "ra": DEV_RA,
        "split": DEV_RA,
        "lsm": DEV_LSM,
        "panel": DEV_LSM,
        "bathroom": DEV_BATHROOM,
        "bath": DEV_BATHROOM,
        "ventilation": DEV_VENTILATION,
        "vam": DEV_VENTILATION,
        "small_vam": DEV_SMALL_VAM,
        "minivam": DEV_SMALL_VAM,
        "sensor": DEV_SENSOR,
        "airsensor": DEV_SENSOR,
        "hd": DEV_HD,
        "geothermic": DEV_GEOTHERMIC,
        "floor_heating": DEV_HD,
        "humidifier": DEV_HUMIDIFIER,
    }
    if val_lower in named_map:
        return named_map[val_lower]

    if "," in val:
        parts = val.split(",")
        return int(parts[0].strip()), int(parts[1].strip())

    try:
        type_id = int(val, 0)
        return 8, type_id
    except ValueError:
        raise ValueError(f"Unknown device target '{val}'. Supported names: {list(named_map.keys())}")


# ---------------------------------------------------------------------------
# Frame Encoding & Packing Helpers
# ---------------------------------------------------------------------------
class BinaryBuffer:
    """Helper to pack binary fields with little-endian formatting."""

    def __init__(self):
        self._fmt = "<"
        self._items = []
        self._len = 0

    def write_u8(self, val: int) -> BinaryBuffer:
        self._fmt += "B"
        self._items.append(int(val) & 0xFF)
        self._len += 1
        return self

    def write_u16(self, val: int) -> BinaryBuffer:
        self._fmt += "H"
        self._items.append(int(val) & 0xFFFF)
        self._len += 2
        return self

    def write_u32(self, val: int) -> BinaryBuffer:
        self._fmt += "I"
        self._items.append(int(val) & 0xFFFFFFFF)
        self._len += 4
        return self

    def write_bytes(self, data: bytes) -> BinaryBuffer:
        self._fmt += f"{len(data)}s"
        self._items.append(data)
        self._len += len(data)
        return self

    def pack(self, rewrite_len: bool = True) -> bytes:
        if rewrite_len and len(self._items) > 1:
            # Bytes 1~2: length of frame payload (excluding STX, ETX, and the length field itself)
            self._items[1] = self._len - 4
        return struct.pack(self._fmt, *self._items)


def build_frame(
    device_target: Union[Tuple[int, int], int],
    cmd_type: int,
    subbody: bytes = b"",
    subbody_ver: int = 0,
    seq_id: int = 1,
    need_ack: int = 1,
) -> bytes:
    """Build a standard Daikin DS-AIR Mina binary frame."""
    if isinstance(device_target, tuple):
        dev_cat, dev_type_id = device_target
    else:
        dev_cat, dev_type_id = (device_target, 0)

    buf = BinaryBuffer()
    buf.write_u8(STX)           # 0: STX (0x02)
    buf.write_u16(0)            # 1~2: Length placeholder
    buf.write_u8(0x0D)          # 3: Reserved (13)
    buf.write_u8(0x00)          # 4: Reserved (0)
    buf.write_u8(subbody_ver)   # 5: Subbody version
    buf.write_u8(0x00)          # 6: Reserved (0)
    buf.write_u32(seq_id)       # 7~10: Sequence ID
    buf.write_u8(dev_cat)       # 11: Target Device Category (0, 8, 10, 12)
    buf.write_u32(dev_type_id)  # 12~15: Target Device Type ID (0, 18, 20, 23, 25, 34, etc.)
    buf.write_u8(need_ack)      # 16: Need Ack flag (0 or 1)
    buf.write_u16(cmd_type)     # 17~18: Command Type
    if subbody:
        buf.write_bytes(subbody)
    buf.write_u8(ETX)           # Last: ETX (0x03)
    return buf.pack(rewrite_len=True)


# ---------------------------------------------------------------------------
# Network Interface Helper & Multi-NIC UDP Discovery
# ---------------------------------------------------------------------------
def get_network_interfaces() -> Dict[str, Dict[str, Any]]:
    """Enumerate all network interfaces with their IPv4, broadcast address, and status."""
    ifaces: Dict[str, Dict[str, Any]] = {}

    try:
        import fcntl
        SIOCGIFADDR = 0x8915
        SIOCGIFBRDADDR = 0x8919
        SIOCGIFFLAGS = 0x8913

        if os.path.exists("/proc/net/dev"):
            with open("/proc/net/dev", "r") as f:
                lines = f.readlines()[2:]
            for line in lines:
                iface_name = line.split(":")[0].strip()
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    ifreq = struct.pack("256s", iface_name.encode("utf-8")[:15])
                    flags = struct.unpack("H", fcntl.ioctl(s.fileno(), SIOCGIFFLAGS, ifreq)[16:18])[0]
                    is_up = bool(flags & 1)
                    is_loopback = bool(flags & 8)

                    ip = socket.inet_ntoa(fcntl.ioctl(s.fileno(), SIOCGIFADDR, ifreq)[20:24])
                    try:
                        brd = socket.inet_ntoa(fcntl.ioctl(s.fileno(), SIOCGIFBRDADDR, ifreq)[20:24])
                    except Exception:
                        brd = "255.255.255.255"

                    ifaces[iface_name] = {
                        "name": iface_name,
                        "ip": ip,
                        "broadcast": brd,
                        "is_up": is_up,
                        "is_loopback": is_loopback,
                    }
                except Exception:
                    pass
                finally:
                    s.close()
    except Exception as e:
        logger.debug("Failed to query interfaces via fcntl: %s", e)

    # Fallback if no interfaces detected
    if not ifaces:
        try:
            hostname = socket.gethostname()
            host_ip = socket.gethostbyname(hostname)
            ifaces["default"] = {
                "name": "default",
                "ip": host_ip,
                "broadcast": "255.255.255.255",
                "is_up": True,
                "is_loopback": False,
            }
        except Exception:
            ifaces["default"] = {
                "name": "default",
                "ip": "0.0.0.0",
                "broadcast": "255.255.255.255",
                "is_up": True,
                "is_loopback": False,
            }

    return ifaces


def print_network_interfaces():
    """Print formatted list of detected network interfaces."""
    ifaces = get_network_interfaces()
    logger.info("🌐 Detected Network Interfaces (%d total):", len(ifaces))
    for name, info in ifaces.items():
        status = "UP" if info["is_up"] else "DOWN"
        if info["is_loopback"]:
            status += " (Loopback)"
        logger.info("   • [%s] IP: %-15s | Broadcast: %-15s | Status: %s",
                    name, info["ip"], info["broadcast"], status)


def build_udp_search_packet(mac_hex: str = "FFFFFFFFFFFF") -> bytes:
    """Build UDP 8111 gateway search discovery packet."""
    clean_mac = bytes.fromhex(mac_hex.replace(":", "").replace("-", ""))
    buf = BinaryBuffer()
    buf.write_u8(0x32)  # Header 0x32
    if len(clean_mac) == 6:
        buf.write_u8(0x01)
        buf.write_u16(len(clean_mac))
        buf.write_bytes(clean_mac)
    else:
        buf.write_u8(0x03)
        buf.write_u16(len(clean_mac))
        buf.write_bytes(clean_mac)
    buf.write_u8(0x03)  # Footer 0x03
    return buf.pack(rewrite_len=False)


def decode_udp_discovery_packet(data: bytes, sender_addr: Tuple[str, int]) -> Optional[Dict[str, Any]]:
    """Parse UDP 8111 response packet from DS-AIR Gateway."""
    if len(data) < 10 or data[0] != 0x32 or data[-1] != 0x03:
        return None

    try:
        resp_type = data[1]
        length = struct.unpack("<H", data[2:4])[0]
        payload = data[4 : 4 + length]

        ip_str = sender_addr[0]
        mac_str = "00:00:00:00:00:00"

        if len(payload) >= 6:
            import re
            m = re.search(rb"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", payload)
            if m:
                ip_str = m.group(1).decode("ascii")
                ip_end_idx = m.end()
                if len(payload) >= ip_end_idx + 6:
                    mac_bytes = payload[ip_end_idx : ip_end_idx + 6]
                else:
                    mac_bytes = payload[-6:]
            else:
                mac_bytes = payload[-6:]
            mac_str = ":".join(f"{b:02X}" for b in mac_bytes)

        return {
            "ip": ip_str,
            "mac": mac_str,
            "resp_type": resp_type,
            "sender_addr": sender_addr,
            "raw_hex": data.hex(),
        }
    except Exception as e:
        logger.debug("Failed to decode UDP packet: %s", e)
        return None


def probe_tcp_port(ip: str, port: int, timeout: float = 1.0) -> bool:
    """Check if TCP port is open (e.g. 8008 or 8009)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        res = s.connect_ex((ip, port))
        s.close()
        return res == 0
    except Exception:
        return False


def probe_gateway_services(ip: str, timeout: float = 2.0) -> Dict[str, Any]:
    """Scan and probe TCP 8008, TCP 8009, and UDP 8111 on target gateway."""
    logger.info("🔍 [Service Probe] Scanning ports on target IP: %s ...", ip)
    results = {
        "ip": ip,
        "tcp_8008": probe_tcp_port(ip, 8008, timeout=timeout),
        "tcp_8009": probe_tcp_port(ip, 8009, timeout=timeout),
        "udp_8111": False,
        "mac": None,
    }

    # UDP 8111 direct unicast probe
    udp_resp = unicast_udp_probe(ip, port=8111, timeout=timeout)
    if udp_resp:
        results["udp_8111"] = True
        results["mac"] = udp_resp.get("mac")
        results["udp_data"] = udp_resp

    logger.info("  📊 Port Scan Results for %s:", ip)
    logger.info("     ├─ TCP 8008 (Standard Mina Protocol) : %s", "🟢 OPEN" if results["tcp_8008"] else "🔴 CLOSED")
    logger.info("     ├─ TCP 8009 (Alternative Protocol)  : %s", "🟢 OPEN" if results["tcp_8009"] else "🔴 CLOSED")
    logger.info("     └─ UDP 8111 (Discovery Protocol)    : %s (MAC: %s)",
                "🟢 RESPONDING" if results["udp_8111"] else "⚪ NO RESPONSE", results["mac"] or "N/A")

    return results


def unicast_udp_probe(target_ip: str, port: int = DEFAULT_UDP_PORT, timeout: float = 2.0) -> Optional[Dict[str, Any]]:
    """Send direct UDP 8111 probe to a specific gateway IP."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        pkt1 = build_udp_search_packet()
        pkt2 = bytes([0x32, 0x03, 0x07, 0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x03])
        sock.sendto(pkt1, (target_ip, port))
        sock.sendto(pkt2, (target_ip, port))

        start_t = time.time()
        while time.time() - start_t < timeout:
            try:
                data, addr = sock.recvfrom(2048)
                decoded = decode_udp_discovery_packet(data, addr)
                if decoded:
                    return decoded
            except socket.timeout:
                break
    except Exception as e:
        logger.debug("Unicast UDP probe error: %s", e)
    finally:
        sock.close()
    return None


def listen_udp_broadcast(port: int = DEFAULT_UDP_PORT, duration_sec: int = 30):
    """Listen for incoming UDP 8111 broadcast packets."""
    logger.info("👂 [UDP Listener] Listening on 0.0.0.0:%d for %d seconds...", port, duration_sec)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("0.0.0.0", port))
    except Exception as e:
        logger.error("Failed to bind UDP port %d: %s (Check if another service is using it)", port, e)
        sock.close()
        return

    sock.settimeout(1.0)
    start_t = time.time()
    try:
        while time.time() - start_t < duration_sec:
            try:
                data, addr = sock.recvfrom(2048)
                t_str = time.strftime("%H:%M:%S")
                decoded = decode_udp_discovery_packet(data, addr)
                logger.info("📡 [%s] UDP 8111 Packet from %s:%d (Hex: %s)", t_str, addr[0], addr[1], data.hex())
                if decoded:
                    logger.info("     └─ Parsed Gateway IP: %s | MAC: %s | Type: 0x%02X",
                                decoded["ip"], decoded["mac"], decoded.get("resp_type", 0))
            except socket.timeout:
                continue
    except KeyboardInterrupt:
        logger.info("\n🛑 UDP Listener stopped by user.")
    finally:
        sock.close()


def discover_gateways(
    iface: Optional[str] = None,
    timeout: float = 3.0,
    port: int = DEFAULT_UDP_PORT,
    probe_tcp: bool = True,
) -> List[Dict[str, Any]]:
    """Broadcast UDP search packets across specified or all active network interfaces."""
    all_ifaces = get_network_interfaces()
    target_ifaces: List[Dict[str, Any]] = []

    if iface:
        matched = None
        for name, info in all_ifaces.items():
            if iface.lower() == name.lower() or iface == info["ip"]:
                matched = info
                break
        if matched:
            target_ifaces.append(matched)
            logger.info("📡 [UDP Discovery] Target Interface: [%s] (IP: %s, Broadcast: %s)",
                        matched["name"], matched["ip"], matched["broadcast"])
        else:
            logger.warning("⚠️ Interface '%s' not found. Using custom IP with default broadcast.", iface)
            target_ifaces.append({
                "name": iface,
                "ip": iface,
                "broadcast": "255.255.255.255",
                "is_up": True,
                "is_loopback": False,
            })
    else:
        for name, info in all_ifaces.items():
            if info["is_up"] and not info["is_loopback"]:
                target_ifaces.append(info)
        if not target_ifaces:
            target_ifaces.append({
                "name": "default",
                "ip": "0.0.0.0",
                "broadcast": "255.255.255.255",
                "is_up": True,
                "is_loopback": False,
            })
        logger.info("📡 [UDP Discovery] Scanning %d active interface(s) on port %d...", len(target_ifaces), port)

    packet_v1 = build_udp_search_packet()
    packet_v2 = bytes([0x32, 0x03, 0x07, 0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x03])

    sockets: List[Tuple[socket.socket, Dict[str, Any]]] = []
    for info in target_ifaces:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                bind_ip = info["ip"] if info["ip"] != "255.255.255.255" else "0.0.0.0"
                s.bind((bind_ip, 0))
            except Exception as e:
                logger.debug("Failed to bind socket to %s: %s", info["ip"], e)

            brd_addr = info.get("broadcast", "255.255.255.255")
            logger.info("   ↳ Sending broadcast to %s:%d via [%s] (%s)...", brd_addr, port, info["name"], info["ip"])
            s.sendto(packet_v1, (brd_addr, port))
            s.sendto(packet_v2, (brd_addr, port))

            if brd_addr != "255.255.255.255":
                try:
                    s.sendto(packet_v1, ("255.255.255.255", port))
                    s.sendto(packet_v2, ("255.255.255.255", port))
                except Exception:
                    pass

            sockets.append((s, info))
        except Exception as e:
            logger.debug("Error creating socket for interface %s: %s", info["name"], e)

    gateways: List[Dict[str, Any]] = []
    if not sockets:
        logger.error("No valid discovery sockets could be opened.")
        return gateways

    start_time = time.time()
    try:
        while time.time() - start_time < timeout:
            readable_socks = [s for s, _ in sockets]
            ready, _, _ = select.select(readable_socks, [], [], 0.3)
            for r_sock in ready:
                iface_info = next((info for s, info in sockets if s == r_sock), {})
                try:
                    data, addr = r_sock.recvfrom(2048)
                    decoded = decode_udp_discovery_packet(data, addr)
                    if decoded:
                        gw_ip = decoded["ip"]
                        gw_mac = decoded["mac"]
                        if not any(g["ip"] == gw_ip for g in gateways):
                            open_port = 8008
                            if probe_tcp:
                                is_8008 = probe_tcp_port(gw_ip, 8008, timeout=1.0)
                                is_8009 = probe_tcp_port(gw_ip, 8009, timeout=1.0)
                                if is_8009 and not is_8008:
                                    open_port = 8009
                            gw_entry = {
                                "ip": gw_ip,
                                "port": open_port,
                                "mac": gw_mac,
                                "interface": iface_info.get("name", "unknown"),
                                "raw_hex": data.hex(),
                            }
                            gateways.append(gw_entry)
                            logger.info("  ✨ Discovered Gateway: IP=%s (Preferred Port: %d), MAC=%s on [%s]",
                                        gw_ip, open_port, gw_mac, gw_entry["interface"])
                except Exception as e:
                    logger.debug("UDP receive error: %s", e)
    finally:
        for s, _ in sockets:
            try:
                s.close()
            except Exception:
                pass

    return gateways


# ---------------------------------------------------------------------------
# Frame Decoder & Parser
# ---------------------------------------------------------------------------
class FrameDecoder:
    """Decodes binary streams from DS-AIR TCP Socket into structured Python objects."""

    @staticmethod
    def decode_frames(buffer: bytes) -> Tuple[List[Dict[str, Any]], bytes]:
        results = []
        while len(buffer) >= 4:
            if buffer[0] != STX:
                idx = buffer.find(bytes([STX]))
                if idx == -1:
                    return results, b""
                buffer = buffer[idx:]
                continue

            length = struct.unpack("<H", buffer[1:3])[0]
            total_frame_len = length + 4

            if len(buffer) < total_frame_len:
                break

            frame_data = buffer[:total_frame_len]
            if frame_data[-1] != ETX:
                logger.warning("Frame ETX mismatch (expected 0x03, got 0x%02X), discarding byte", frame_data[-1])
                buffer = buffer[1:]
                continue

            parsed = FrameDecoder.parse_single_frame(frame_data)
            if parsed:
                results.append(parsed)

            buffer = buffer[total_frame_len:]

        return results, buffer

    @staticmethod
    def parse_single_frame(frame: bytes) -> Optional[Dict[str, Any]]:
        if len(frame) < 20:
            return None

        # Header format: <BHBBBBIBIBH (19 bytes: 0..18)
        hdr = struct.unpack("<BHBBBBIBIBH", frame[:19])
        stx, length, r1, r2, subbody_ver, r3, seq_id, dev_cat, dev_type_id, need_ack, cmd_type = hdr
        subbody = frame[19:-1]

        dev_key = (dev_cat, dev_type_id)
        dev_type_name = DEVICE_NAMES.get(dev_key, f"Device(0x{dev_cat:02X},0x{dev_type_id:04X})")

        result = {
            "seq_id": seq_id,
            "dev_cat": dev_cat,
            "dev_type_id": dev_type_id,
            "dev_key": dev_key,
            "dev_type_name": dev_type_name,
            "subbody_ver": subbody_ver,
            "need_ack": need_ack,
            "cmd_type": cmd_type,
            "cmd_hex": f"0x{cmd_type:04X}",
            "subbody_len": len(subbody),
            "raw_hex": frame.hex(),
            "raw_subbody": subbody.hex(),
            "data": {},
        }

        # Decode specific subbodies
        if dev_key == DEV_SYSTEM:
            if cmd_type in (CMD_SYS_HANDSHAKE, CMD_SYS_HANDSHAKE_WEB):
                result["cmd_name"] = "SYS_HANDSHAKE"
                try:
                    s_time = subbody.decode("utf-8", errors="ignore").strip()
                    if len(s_time) == 14 and s_time.isdigit():
                        result["data"]["server_time"] = f"{s_time[0:4]}-{s_time[4:6]}-{s_time[6:8]} {s_time[8:10]}:{s_time[10:12]}:{s_time[12:14]}"
                    else:
                        result["data"]["server_time"] = s_time or subbody.hex()
                except Exception:
                    result["data"]["server_time"] = subbody.hex()

            elif cmd_type == CMD_SYS_ACK:
                result["cmd_name"] = "SYS_ACK"
                if len(subbody) >= 1:
                    result["data"]["version_flag"] = subbody[0]

            elif cmd_type in (CMD_SYS_GET_ROOM_INFO, CMD_SYS_GET_ROOM_INFO_V1):
                result["cmd_name"] = "SYS_GET_ROOM_INFO"
                result["data"]["topology"] = FrameDecoder.parse_room_info(subbody, subbody_ver)

            elif cmd_type == CMD_SYS_GET_GW_INFO:
                result["cmd_name"] = "SYS_GET_GW_INFO"
                result["data"]["gw_info"] = FrameDecoder.parse_gw_info(subbody)

            elif cmd_type == CMD_SYS_TIME_SYNC:
                result["cmd_name"] = "SYS_TIME_SYNC"
                result["data"]["time_sync"] = subbody.hex()

            elif cmd_type == CMD_SYS_ERR_CODE:
                result["cmd_name"] = "SYS_ERR_CODE"
                result["data"]["err_code"] = subbody.hex()

            elif cmd_type == CMD_SYS_CHECK_NEW_VERSION:
                result["cmd_name"] = "SYS_CHECK_NEW_VERSION"
                result["data"]["version_check"] = subbody.hex()

        elif dev_key in (DEV_AIRCON, DEV_NEWAIRCON, DEV_BATHROOM):
            if cmd_type in (CMD_AIR_STATUS_QUERY, CMD_AIR_STATUS_CHANGED, CMD_AIR_STATUS_CONTROL):
                result["cmd_name"] = "AIRCON_STATUS"
                result["data"]["status"] = FrameDecoder.parse_aircon_status(subbody)
            elif cmd_type in (CMD_AIR_CAPABILITY_QUERY, CMD_AIR_CAPABILITY_V2):
                result["cmd_name"] = "AIRCON_CAPABILITY"
                result["data"]["capability"] = FrameDecoder.parse_aircon_capability(subbody)
            elif cmd_type == CMD_AIR_RECOMMENDED_TEMP:
                result["cmd_name"] = "AIR_RECOMMENDED_TEMP"
                result["data"]["rec_temp"] = subbody.hex()

        elif dev_key in (DEV_RA, DEV_MESHID_RA):
            if cmd_type in (CMD_RA_QUERY_STATUS, CMD_RA_STATUS_CHANGED, CMD_RA_01, CMD_RA_CMD_TYPE):
                result["cmd_name"] = "RA_STATUS"
                result["data"]["status"] = FrameDecoder.parse_ra_status(subbody)
            elif cmd_type == CMD_RA_QUERY_CAPABILITY:
                result["cmd_name"] = "RA_CAPABILITY"
                result["data"]["capability"] = FrameDecoder.parse_aircon_capability(subbody)

        elif dev_key in (DEV_LSM, DEV_MESHID_LSM):
            if cmd_type in (CMD_LSM_QUERY_STATUS, CMD_LSM_STATUS_CHANGED, CMD_LSM_GET_DETAIL):
                result["cmd_name"] = "LSM_STATUS"
                result["data"]["status"] = FrameDecoder.parse_aircon_status(subbody)
            elif cmd_type == CMD_LSM_QUERY_CAPABILITY:
                result["cmd_name"] = "LSM_CAPABILITY"
                result["data"]["capability"] = FrameDecoder.parse_aircon_capability(subbody)

        elif dev_key == DEV_SENSOR:
            if cmd_type in (CMD_SENSOR_INFO_2, CMD_SENSOR_STATUS_2, CMD_SENSOR_INFO_1, CMD_SENSOR_HCHO_VOC):
                result["cmd_name"] = "AIR_SENSOR_DATA"
                result["data"]["sensor"] = FrameDecoder.parse_sensor_data(subbody)

        elif dev_key in (DEV_VENTILATION, DEV_SMALL_VAM):
            if cmd_type in (CMD_VAM_STATUS_QUERY, CMD_VAM_STATUS_CHANGED, CMD_VAM_STATUS_CONTROL):
                result["cmd_name"] = "VENTILATION_STATUS"
                result["data"]["status"] = FrameDecoder.parse_ventilation_status(subbody)
            elif cmd_type == CMD_VAM_COMPOSITE_QUERY:
                result["cmd_name"] = "VENTILATION_COMPOSITE"
                result["data"]["composite"] = FrameDecoder.parse_ventilation_composite(subbody)

        elif dev_key in (DEV_HD, DEV_GEOTHERMIC):
            if cmd_type in (CMD_HD_STATUS_QUERY, CMD_HD_STATUS_CHANGED, CMD_HD_STATUS_CONTROL, CMD_HD_DEVICE_INFO):
                result["cmd_name"] = "HD_STATUS"
                result["data"]["status"] = FrameDecoder.parse_hd_status(subbody)

        elif dev_key in (DEV_IP_MESH_COMMON, DEV_MESHID_MESH_COMMON) or cmd_type in (0x000A, 0x0081, 0x0083):
            if cmd_type == 0x000A:
                result["cmd_name"] = "MESH_NODE_INFO"
                result["data"]["mesh_node"] = FrameDecoder.parse_mesh_node_info(subbody)
            elif cmd_type == 0x0081:
                result["cmd_name"] = "MESH_GET_NODE_LIST"
                result["data"]["node_list"] = FrameDecoder.parse_mesh_node_list(subbody)
            elif cmd_type == 0x0083:
                result["cmd_name"] = "MESH_GET_BASIC_INFO"
                b_info = FrameDecoder.parse_mesh_basic_info(subbody)
                result["data"]["basic_info"] = b_info
                result["data"]["status"] = b_info
            elif cmd_type in (CMD_AIR_STATUS_QUERY, CMD_AIR_STATUS_CHANGED):
                result["cmd_name"] = "MESH_AC_STATUS"
                result["data"]["status"] = FrameDecoder.parse_aircon_status(subbody)
            else:
                result["cmd_name"] = f"MESH_CMD_0x{cmd_type:04X}"
                result["data"]["raw"] = subbody.hex()

        elif dev_key == DEV_HUMIDIFIER:
            result["cmd_name"] = "HUMIDIFIER_STATUS"
            result["data"]["raw"] = subbody.hex()

        return result

    @staticmethod
    def parse_mesh_basic_info(subbody: bytes) -> Dict[str, Any]:
        """Parse Mesh Node Basic Info / Full Telemetry response (0x0083)."""
        res: Dict[str, Any] = {"raw_hex": subbody.hex(), "room_id": 1, "unit_id": 1}
        try:
            offset = 0
            if len(subbody) >= 7:
                res["status_code"] = subbody[0]
                offset += 1
                res["hub_mac"] = ":".join(f"{b:02X}" for b in subbody[offset : offset + 6])
                offset += 6

            if len(subbody) > offset:
                res["node_index"] = subbody[offset]
                offset += 1

            if len(subbody) >= offset + 6:
                res["mac"] = ":".join(f"{b:02X}" for b in subbody[offset : offset + 6])
                offset += 6

            if len(subbody) >= offset + 2:
                res["model_id"] = struct.unpack("<H", subbody[offset : offset + 2])[0]
                offset += 2

            if len(subbody) > offset:
                name_len = subbody[offset]
                offset += 1
                if offset + name_len <= len(subbody):
                    res["name"] = subbody[offset : offset + name_len].decode("utf-8", errors="ignore")
                    offset += name_len

            if len(subbody) > offset:
                res["online_flag"] = subbody[offset]
                offset += 1

            if len(subbody) >= offset + 2:
                res["mode_tag"] = struct.unpack("<H", subbody[offset : offset + 2])[0]
                offset += 2

            if len(subbody) >= offset + 2:
                raw_temp = struct.unpack("<H", subbody[offset : offset + 2])[0]
                res["target_temp"] = float(raw_temp) if raw_temp < 100 else raw_temp / 10.0
                offset += 2

            if len(subbody) >= offset + 2:
                raw_cur_temp = struct.unpack("<H", subbody[offset : offset + 2])[0]
                res["current_temp"] = raw_cur_temp / 10.0 if raw_cur_temp > 100 else float(raw_cur_temp)
                offset += 2

            if len(subbody) > offset:
                offset += 1

            if len(subbody) >= offset + 4:
                res["dev_type_field"] = struct.unpack("<I", subbody[offset : offset + 4])[0]
                offset += 4

            if len(subbody) >= offset + 2:
                fan_raw = struct.unpack("<H", subbody[offset : offset + 2])[0]
                res["fan_speed_raw"] = fan_raw
                res["fan_speed"] = AC_FAN_SPEEDS.get(fan_raw, f"Speed_{fan_raw}")
                offset += 2

            if len(subbody) >= offset + 2:
                mode_raw = subbody[offset]
                power_raw = subbody[offset + 1]
                res["mode_raw"] = mode_raw
                res["mode"] = AC_MODES.get(mode_raw, f"Mode_{mode_raw}")
                res["power_raw"] = power_raw
                res["is_on"] = bool(power_raw == 1)
                offset += 2
        except Exception as e:
            logger.debug("Error parsing mesh basic info: %s", e)

        return res

    @staticmethod
    def parse_mesh_node_info(subbody: bytes) -> Dict[str, Any]:
        """Parse Mesh Node Announcement / Info packet (0x000A)."""
        info: Dict[str, Any] = {"raw_hex": subbody.hex()}
        try:
            if len(subbody) >= 6:
                info["mac"] = ":".join(f"{b:02X}" for b in subbody[0:6])
                offset = 6
                if len(subbody) > offset:
                    info["node_type"] = subbody[offset]
                    offset += 1
                if len(subbody) >= offset + 2:
                    info["room_id"] = subbody[offset]
                    info["unit_id"] = subbody[offset + 1]
                    offset += 2
                if offset < len(subbody):
                    name_len = subbody[offset]
                    offset += 1
                    if offset + name_len <= len(subbody):
                        info["name"] = subbody[offset : offset + name_len].decode("utf-8", errors="ignore")
                        offset += name_len
                if offset < len(subbody):
                    code_len = subbody[offset]
                    offset += 1
                    if offset + code_len <= len(subbody):
                        info["code"] = subbody[offset : offset + code_len].decode("utf-8", errors="ignore")
                        offset += code_len
        except Exception as e:
            logger.debug("Error parsing mesh node info: %s", e)
        return info

    @staticmethod
    def parse_mesh_node_list(subbody: bytes) -> Dict[str, Any]:
        """Parse Mesh Node List response (0x0081)."""
        res: Dict[str, Any] = {"raw_hex": subbody.hex(), "nodes": []}
        try:
            offset = 0
            if len(subbody) >= 7:
                offset += 1  # status flag
                gw_mac_bytes = subbody[offset : offset + 6]
                res["gw_mac"] = ":".join(f"{b:02X}" for b in gw_mac_bytes)
                offset += 6

                if offset < len(subbody):
                    node_cnt = subbody[offset]
                    offset += 1
                    for _ in range(node_cnt):
                        if offset + 6 > len(subbody):
                            break
                        n_mac = ":".join(f"{b:02X}" for b in subbody[offset : offset + 6])
                        res["nodes"].append(n_mac)
                        offset += 6
        except Exception as e:
            logger.debug("Error parsing mesh node list: %s", e)
        return res

    @staticmethod
    def parse_gw_info(subbody: bytes) -> Dict[str, Any]:
        """Parse Gateway info payload (0x0050)."""
        info: Dict[str, Any] = {"raw_hex": subbody.hex()}
        try:
            ascii_str = subbody.decode("utf-8", errors="ignore").strip()
            if any(c.isalnum() for c in ascii_str):
                info["string"] = ascii_str
        except Exception:
            pass
        return info

    @staticmethod
    def parse_room_info(subbody: bytes, subbody_ver: int = 1) -> Dict[str, Any]:
        """Parse topology and room structure (Rooms, ACs, VAMs, Sensors)."""
        topology = {"rooms": [], "devices": []}
        if len(subbody) < 2:
            return topology

        try:
            offset = 0
            total_count = struct.unpack("<H", subbody[offset : offset + 2])[0]
            offset += 2

            if offset >= len(subbody):
                return topology

            room_cnt = subbody[offset]
            offset += 1

            for r_idx in range(room_cnt):
                if offset >= len(subbody):
                    break
                room_id = struct.unpack("<H", subbody[offset : offset + 2])[0]
                offset += 2

                ver_flag = 1
                if subbody_ver == 1 and offset < len(subbody):
                    ver_flag = subbody[offset]
                    offset += 1

                room_name = f"Room_{room_id}"
                room_alias = room_name
                room_icon = ""

                if ver_flag != 2 and offset < len(subbody):
                    name_len = subbody[offset]
                    offset += 1
                    room_name = subbody[offset : offset + name_len].decode("utf-8", errors="ignore")
                    offset += name_len

                    if offset < len(subbody):
                        alias_len = subbody[offset]
                        offset += 1
                        room_alias = subbody[offset : offset + alias_len].decode("utf-8", errors="ignore")
                        offset += alias_len

                    if offset < len(subbody):
                        icon_len = subbody[offset]
                        offset += 1
                        room_icon = subbody[offset : offset + icon_len].decode("utf-8", errors="ignore")
                        offset += icon_len

                room_entry = {
                    "room_id": room_id,
                    "name": room_name,
                    "alias": room_alias,
                    "icon": room_icon,
                    "devices": [],
                }

                if offset + 2 <= len(subbody):
                    unit_count = struct.unpack("<H", subbody[offset : offset + 2])[0]
                    offset += 2

                    for _u in range(unit_count):
                        if offset + 6 > len(subbody):
                            break
                        dev_type_id = struct.unpack("<I", subbody[offset : offset + 4])[0]
                        offset += 4
                        dev_count = struct.unpack("<H", subbody[offset : offset + 2])[0]
                        offset += 2

                        dev_key = (8, dev_type_id)
                        dev_name = DEVICE_NAMES.get(dev_key, f"Device(8,{dev_type_id})")

                        for unit_idx in range(dev_count):
                            dev_info = {
                                "dev_key": dev_key,
                                "dev_cat": 8,
                                "dev_type_id": dev_type_id,
                                "device_type_name": dev_name,
                                "room_id": room_id,
                                "unit_id": unit_idx,
                                "alias": f"{room_alias or room_name} ({dev_name})",
                                "code": f"R{room_id}U{unit_idx}",
                            }
                            if ver_flag > 2 and offset < len(subbody):
                                length = subbody[offset]
                                offset += 1
                                dev_info["name"] = subbody[offset : offset + length].decode("utf-8", errors="ignore")
                                offset += length
                                if offset < len(subbody):
                                    length = subbody[offset]
                                    offset += 1
                                    custom_alias = subbody[offset : offset + length].decode("utf-8", errors="ignore")
                                    offset += length
                                    if custom_alias:
                                        dev_info["alias"] = custom_alias

                            room_entry["devices"].append(dev_info)
                            topology["devices"].append(dev_info)

                topology["rooms"].append(room_entry)

        except Exception as e:
            logger.debug("Error parsing room topology: %s", e)

        return topology

    @staticmethod
    def parse_aircon_status(subbody: bytes) -> Dict[str, Any]:
        """Parse Air Conditioner status payload."""
        res: Dict[str, Any] = {"raw_hex": subbody.hex()}
        if len(subbody) < 3:
            return res

        try:
            offset = 0
            room_id = subbody[offset]
            unit_id = subbody[offset + 1] if len(subbody) > 1 else 0
            offset += 2

            res["room_id"] = room_id
            res["unit_id"] = unit_id

            flag = subbody[offset]
            offset += 1

            if flag & CTRL_FLAG_SWITCH and offset < len(subbody):
                res["is_on"] = bool(subbody[offset] & 0x01)
                offset += 1

            if flag & CTRL_FLAG_MODE and offset < len(subbody):
                mode_raw = subbody[offset]
                res["mode_raw"] = mode_raw
                res["mode"] = AC_MODES.get(mode_raw, f"Mode_{mode_raw}")
                offset += 1

            if flag & CTRL_FLAG_AIR_FLOW and offset < len(subbody):
                fan_raw = subbody[offset]
                res["fan_speed_raw"] = fan_raw
                res["fan_speed"] = AC_FAN_SPEEDS.get(fan_raw, f"Speed_{fan_raw}")
                offset += 1

            if flag & CTRL_FLAG_CURRENT_TEMP and offset + 2 <= len(subbody):
                raw_cur_temp = struct.unpack("<h", subbody[offset : offset + 2])[0]
                res["current_temp"] = raw_cur_temp / 10.0 if raw_cur_temp != -1000 else None
                offset += 2

            if flag & CTRL_FLAG_SETTED_TEMP and offset + 2 <= len(subbody):
                raw_set_temp = struct.unpack("<h", subbody[offset : offset + 2])[0]
                res["target_temp"] = raw_set_temp / 10.0 if raw_set_temp != -1000 else None
                offset += 2

            if flag & CTRL_FLAG_FAN_DIRECTION and offset < len(subbody):
                dir_val = subbody[offset]
                dir1 = dir_val & 0x0F
                dir2 = (dir_val >> 4) & 0x0F
                res["fan_direction_raw"] = dir1
                res["fan_direction"] = AC_FAN_DIRECTIONS.get(dir1, f"Dir_{dir1}")
                res["fan_direction2"] = AC_FAN_DIRECTIONS.get(dir2, f"Dir_{dir2}")
                offset += 1

            if flag & CTRL_FLAG_HUMIDITY and offset < len(subbody):
                res["humidity"] = subbody[offset]
                offset += 1
        except Exception as e:
            logger.debug("Error parsing AC status: %s", e)

        return res

    @staticmethod
    def parse_ra_status(subbody: bytes) -> Dict[str, Any]:
        """Parse RA (Residential AC / 分体机) status payload."""
        res: Dict[str, Any] = FrameDecoder.parse_aircon_status(subbody)
        res["device_type"] = "RA (分体机)"
        return res

    @staticmethod
    def parse_aircon_capability(subbody: bytes) -> Dict[str, Any]:
        """Parse AC supported modes, temperature ranges, and fan speeds."""
        caps: Dict[str, Any] = {"modes": [], "raw_hex": subbody.hex()}
        try:
            offset = 0
            if len(subbody) >= 1:
                mode_cnt = subbody[0]
                offset += 1
                for _ in range(mode_cnt):
                    if offset + 4 > len(subbody):
                        break
                    mode_idx, fan_flags, min_temp, max_temp = subbody[offset : offset + 4]
                    offset += 4
                    caps["modes"].append({
                        "mode": AC_MODES.get(mode_idx, f"Mode_{mode_idx}"),
                        "fan_flags": fan_flags,
                        "min_temp": min_temp / 2.0 if min_temp > 0 else 16.0,
                        "max_temp": max_temp / 2.0 if max_temp > 0 else 32.0,
                    })
        except Exception as e:
            logger.debug("Error parsing AC capabilities: %s", e)
        return caps

    @staticmethod
    def parse_sensor_data(subbody: bytes) -> Dict[str, Any]:
        """Parse Air Quality Sensor (Sensor 2.0 / SensorKit) telemetry."""
        sensor: Dict[str, Any] = {"raw_hex": subbody.hex()}
        try:
            offset = 0
            if len(subbody) >= 2:
                temp = struct.unpack("<h", subbody[offset : offset + 2])[0] / 10.0
                sensor["temperature"] = temp
                offset += 2

            if len(subbody) >= offset + 2:
                humidity = struct.unpack("<H", subbody[offset : offset + 2])[0]
                sensor["humidity"] = humidity if humidity <= 100 else humidity / 10.0
                offset += 2

            if len(subbody) >= offset + 2:
                pm25 = struct.unpack("<H", subbody[offset : offset + 2])[0]
                sensor["pm25"] = pm25
                offset += 2

            if len(subbody) >= offset + 2:
                co2 = struct.unpack("<H", subbody[offset : offset + 2])[0]
                sensor["co2"] = co2
                offset += 2

            if len(subbody) >= offset + 2:
                tvoc = struct.unpack("<H", subbody[offset : offset + 2])[0]
                sensor["tvoc"] = tvoc
                offset += 2

            if len(subbody) >= offset + 2:
                hcho = struct.unpack("<H", subbody[offset : offset + 2])[0] / 100.0
                sensor["hcho"] = hcho
                offset += 2
        except Exception as e:
            logger.debug("Error parsing sensor data: %s", e)

        return sensor

    @staticmethod
    def parse_ventilation_status(subbody: bytes) -> Dict[str, Any]:
        """Parse Ventilation unit status."""
        res: Dict[str, Any] = {"raw_hex": subbody.hex()}
        if len(subbody) < 2:
            return res
        try:
            res["is_on"] = bool(subbody[0] & 0x01)
            vol_raw = subbody[1]
            res["air_volume_raw"] = vol_raw
            res["air_volume"] = VAM_AIR_VOLUMES.get(vol_raw, f"Vol_{vol_raw}")
        except Exception as e:
            logger.debug("Error parsing VAM status: %s", e)
        return res

    @staticmethod
    def parse_ventilation_composite(subbody: bytes) -> Dict[str, Any]:
        """Parse MiniVAM / VAM Composite Situation."""
        res: Dict[str, Any] = {"raw_hex": subbody.hex()}
        try:
            if len(subbody) >= 4:
                res["indoor_temp"] = struct.unpack("<h", subbody[0:2])[0] / 10.0
                res["outdoor_temp"] = struct.unpack("<h", subbody[2:4])[0] / 10.0
            if len(subbody) >= 6:
                res["outdoor_humidity"] = struct.unpack("<H", subbody[4:6])[0]
            if len(subbody) >= 8:
                res["outdoor_pm25"] = struct.unpack("<H", subbody[6:8])[0]
        except Exception as e:
            logger.debug("Error parsing VAM composite: %s", e)
        return res

    @staticmethod
    def parse_hd_status(subbody: bytes) -> Dict[str, Any]:
        """Parse Floor Heating (HD) status."""
        res: Dict[str, Any] = {"raw_hex": subbody.hex()}
        if len(subbody) < 2:
            return res
        try:
            res["is_on"] = bool(subbody[0] & 0x01)
            if len(subbody) >= 4:
                res["target_temp"] = struct.unpack("<h", subbody[2:4])[0] / 10.0
            if len(subbody) >= 6:
                res["current_temp"] = struct.unpack("<h", subbody[4:6])[0] / 10.0
        except Exception as e:
            logger.debug("Error parsing HD status: %s", e)
        return res


# ---------------------------------------------------------------------------
# Daikin DS-AIR Local Protocol Client & Tester
# ---------------------------------------------------------------------------
class DairLocalTester:
    """Complete Local Socket Client for Testing Daikin DS-AIR Gateway Protocol (Ports 8008 / 8009)."""

    def __init__(
        self,
        host: str,
        port: int = 8008,
        timeout: float = 5.0,
        auto_fallback: bool = True,
        show_raw: bool = False,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.auto_fallback = auto_fallback
        self.show_raw = show_raw
        self.sock: Optional[socket.socket] = None
        self.recv_buffer = b""
        self.seq_cnt = 1
        self.topology: Dict[str, Any] = {"rooms": [], "devices": []}
        self.device_states: Dict[str, Any] = {}
        self.discovered_targets: List[Dict[str, Any]] = []

    def connect(self) -> bool:
        """Establish TCP connection with gateway (with automatic 8008 / 8009 fallback)."""
        candidate_ports = [self.port]
        if self.auto_fallback:
            alt_port = 8009 if self.port == 8008 else 8008
            if alt_port not in candidate_ports:
                candidate_ports.append(alt_port)

        connected = False
        for p in candidate_ports:
            logger.info("🔌 Connecting to DS-AIR Gateway at %s:%d ...", self.host, p)
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(self.timeout)
                s.connect((self.host, p))
                self.sock = s
                self.port = p
                logger.info("  ✅ Connected successfully to %s:%d!", self.host, p)
                connected = True
                break
            except Exception as e:
                logger.warning("  ⚠️ Connection failed to %s:%d: %s", self.host, p, e)
                if len(candidate_ports) > 1 and p == candidate_ports[0]:
                    logger.info("     ↳ Trying alternative port...")

        if not connected:
            logger.error("❌ Failed to connect to gateway at %s on ports %s", self.host, candidate_ports)
            self.sock = None
            return False

        return True

    def close(self):
        """Close TCP socket."""
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        logger.info("🔌 Disconnected.")

    def _next_seq(self) -> int:
        self.seq_cnt += 1
        return self.seq_cnt

    def send_raw_frame(self, frame: bytes) -> bool:
        """Send raw binary frame to socket."""
        if not self.sock:
            logger.error("Cannot send: socket is not connected.")
            return False
        try:
            if self.show_raw or logger.isEnabledFor(logging.DEBUG):
                logger.info("  >>> TX (%d bytes): %s", len(frame), frame.hex())
            self.sock.sendall(frame)
            return True
        except Exception as e:
            logger.error("Error sending frame: %s", e)
            return False

    def send_cmd(
        self,
        device_target: Union[Tuple[int, int], int],
        cmd_type: int,
        subbody: bytes = b"",
        subbody_ver: int = 0,
        need_ack: int = 1,
    ) -> bool:
        """Build and send command frame."""
        seq = self._next_seq()
        frame = build_frame(
            device_target=device_target,
            cmd_type=cmd_type,
            subbody=subbody,
            subbody_ver=subbody_ver,
            seq_id=seq,
            need_ack=need_ack,
        )
        return self.send_raw_frame(frame)

    def recv_frames(self, wait_sec: float = 2.0) -> List[Dict[str, Any]]:
        """Read and decode incoming frames until quiet or timeout."""
        if not self.sock:
            return []

        all_parsed = []
        end_time = time.time() + wait_sec

        while time.time() < end_time:
            ready, _, _ = select.select([self.sock], [], [], 0.3)
            if ready:
                try:
                    chunk = self.sock.recv(4096)
                    if not chunk:
                        logger.warning("Connection closed by peer.")
                        break
                    if self.show_raw or logger.isEnabledFor(logging.DEBUG):
                        logger.info("  <<< RX (%d bytes): %s", len(chunk), chunk.hex())
                    self.recv_buffer += chunk

                    parsed, self.recv_buffer = FrameDecoder.decode_frames(self.recv_buffer)
                    if parsed:
                        all_parsed.extend(parsed)
                        for item in parsed:
                            self._update_state_cache(item)
                except Exception as e:
                    logger.debug("Read exception: %s", e)
                    break
            else:
                if all_parsed:
                    break

        return all_parsed

    def _update_state_cache(self, frame: Dict[str, Any]):
        """Update local device cache with parsed frame telemetry."""
        dev_key = frame["dev_key"]
        data = frame.get("data", {})

        if "status" in data:
            room_id = data["status"].get("room_id", 1)
            unit_id = data["status"].get("unit_id", 1)
            cache_key = f"{dev_key[0]}_{dev_key[1]}_{room_id}_{unit_id}"
            if cache_key not in self.device_states:
                self.device_states[cache_key] = {}
            self.device_states[cache_key].update(data["status"])

            # Cross-register for mesh devices
            for fallback_key in (f"12_34_{room_id}_{unit_id}", f"10_34_{room_id}_{unit_id}", f"12_47_{room_id}_{unit_id}", f"8_23_{room_id}_{unit_id}", f"8_18_{room_id}_{unit_id}"):
                if fallback_key not in self.device_states:
                    self.device_states[fallback_key] = {}
                self.device_states[fallback_key].update(data["status"])

        if "basic_info" in data and isinstance(data["basic_info"], dict):
            room_id = data["basic_info"].get("room_id", 1)
            unit_id = data["basic_info"].get("unit_id", 1)
            for fallback_key in (f"{dev_key[0]}_{dev_key[1]}_{room_id}_{unit_id}", f"12_34_{room_id}_{unit_id}", f"10_34_{room_id}_{unit_id}", f"12_47_{room_id}_{unit_id}", f"8_23_{room_id}_{unit_id}", f"8_18_{room_id}_{unit_id}"):
                if fallback_key not in self.device_states:
                    self.device_states[fallback_key] = {}
                self.device_states[fallback_key].update(data["basic_info"])

        if "sensor" in data:
            cache_key = f"{dev_key[0]}_{dev_key[1]}_sensor"
            if cache_key not in self.device_states:
                self.device_states[cache_key] = {}
            self.device_states[cache_key].update(data["sensor"])

    # -----------------------------------------------------------------------
    # Protocol Operations
    # -----------------------------------------------------------------------
    def test_handshake(self) -> bool:
        """Step 1: Perform protocol handshake (0xA000 / SYS_HAND_SHAKE)."""
        logger.info("🤝 [Test 1] Executing Protocol Handshake...")
        self.send_cmd(DEV_SYSTEM, CMD_SYS_HANDSHAKE, subbody_ver=0)
        frames = self.recv_frames(wait_sec=2.0)
        handshake_resp = next((f for f in frames if f.get("cmd_name") == "SYS_HANDSHAKE"), None)

        if handshake_resp:
            server_time = handshake_resp.get("data", {}).get("server_time", "")
            logger.info("  ✅ Handshake ACK received! Gateway Timestamp: %s", server_time or "(Empty/ACK)")
            return True
        elif frames:
            logger.info("  ✅ Handshake accepted (Received %d frame(s): %s)", len(frames), frames[0].get("cmd_hex"))
            return True
        else:
            self.send_cmd(DEV_SYSTEM, CMD_SYS_HANDSHAKE, subbody_ver=1)
            frames = self.recv_frames(wait_sec=2.0)
            if frames:
                logger.info("  ✅ Handshake accepted with subbody_ver=1! (Frames: %d)", len(frames))
                return True
            logger.warning("  ⚠️ No Handshake ACK received.")
            return False

    def test_heartbeat(self) -> bool:
        """Step 2: Send Heartbeat (0x0001 / SYS_ACK)."""
        logger.info("💓 [Test 2] Sending Heartbeat (SYS_ACK)...")
        self.send_cmd(DEV_SYSTEM, CMD_SYS_ACK, need_ack=0)
        frames = self.recv_frames(wait_sec=1.5)
        ack_resp = next((f for f in frames if f.get("cmd_name") == "SYS_ACK"), None)
        if ack_resp or self.sock is not None:
            logger.info("  ✅ Heartbeat accepted.")
            return True
        return False

    def test_probe_gateway_info(self) -> Dict[str, Any]:
        """Query Gateway System Info (0x0050 / SYS_GET_GW_INFO & 0x0005 / SYS_TIME_SYNC)."""
        logger.info("ℹ️ [Probe] Querying Gateway System Info (SYS_GET_GW_INFO / TIME_SYNC)...")
        self.send_cmd(DEV_SYSTEM, CMD_SYS_GET_GW_INFO, subbody_ver=0)
        self.send_cmd(DEV_SYSTEM, CMD_SYS_TIME_SYNC, subbody_ver=0)
        self.send_cmd(DEV_SYSTEM, CMD_SYS_CHECK_NEW_VERSION, subbody_ver=0)
        frames = self.recv_frames(wait_sec=2.5)

        info_found = {}
        for f in frames:
            cmd = f.get("cmd_name", f["cmd_hex"])
            raw = f.get("raw_subbody", "")
            logger.info("  📥 System Response [%s]: Payload: %s", cmd, raw)
            if "gw_info" in f.get("data", {}):
                info_found["gw_info"] = f["data"]["gw_info"]
        return info_found

    def test_query_rooms_and_topology(self) -> Dict[str, Any]:
        """Step 3: Query room topology & device list (0x0030 / SYS_GET_ROOM_INFO / MESH Discovery)."""
        logger.info("🏢 [Test 3] Querying Room & Device Topology & Mesh Node Discovery...")
        subbody = bytes([0x01, 0xFF, 0xFF])
        # 1. Standard VRV / DS-AIR Multi-room query
        self.send_cmd(DEV_SYSTEM, CMD_SYS_GET_ROOM_INFO, subbody=subbody, subbody_ver=1)
        # 2. Mesh Node Discovery query (triggers 0x000A node announcement on Mesh hubs!)
        self.send_cmd(DEV_SYSTEM, 0x0005, subbody=subbody, subbody_ver=0)
        # 3. Mesh Node List query
        self.send_cmd(DEV_IP_MESH_COMMON, 0x0081, subbody=b"", subbody_ver=0)
        self.send_cmd(DEV_MESHID_MESH_COMMON, 0x0081, subbody=b"", subbody_ver=0)

        frames = self.recv_frames(wait_sec=3.5)

        # Check for standard topology response
        room_resp = next((f for f in frames if f.get("cmd_name") == "SYS_GET_ROOM_INFO"), None)
        if room_resp and "topology" in room_resp.get("data", {}):
            topo = room_resp["data"]["topology"]
            if topo.get("rooms") or topo.get("devices"):
                self.topology = topo
                logger.info("  ✅ Discovered %d Room(s) and %d Device(s) in Gateway Topology:",
                            len(topo.get("rooms", [])), len(topo.get("devices", [])))
                return self.topology

        # Check for Mesh node announcement (0x000A / MESH_NODE_INFO) or Mesh node list (0x0081)
        mesh_nodes = [f["data"]["mesh_node"] for f in frames if "mesh_node" in f.get("data", {})]
        node_lists = [f["data"]["node_list"] for f in frames if "node_list" in f.get("data", {})]

        if mesh_nodes:
            logger.info("  🎉 Discovered %d Mesh Smart AC Node(s):", len(mesh_nodes))
            for node in mesh_nodes:
                r_id = node.get("room_id", 1)
                u_id = node.get("unit_id", 1)
                name = node.get("name", f"AC_{r_id}_{u_id}")
                mac = node.get("mac", "")
                code = node.get("code", "00")
                logger.info("     🏠 Mesh Node [%s]: Room=%d | Unit=%d | MAC=%s | Code=%s", name, r_id, u_id, mac, code)
                dev_entry = {
                    "dev_key": DEV_MESHID_RA,
                    "dev_cat": 12,
                    "dev_type_id": 34,
                    "device_type_name": "智联空调室内机 (Mesh RA)",
                    "room_id": r_id,
                    "unit_id": u_id,
                    "name": name,
                    "mac": mac,
                    "alias": f"{name} (Mesh RA R{r_id}U{u_id})",
                    "code": f"R{r_id}U{u_id}",
                }
                if not any(d["room_id"] == r_id and d["unit_id"] == u_id for d in self.topology["devices"]):
                    self.topology["devices"].append(dev_entry)
            return self.topology

        if node_lists and node_lists[0].get("nodes"):
            logger.info("  🎉 Discovered %d Mesh Node MAC(s) from Hub %s:",
                        len(node_lists[0]["nodes"]), node_lists[0].get("gw_mac", ""))
            for idx, n_mac in enumerate(node_lists[0]["nodes"], 1):
                dev_entry = {
                    "dev_key": DEV_MESHID_RA,
                    "dev_cat": 12,
                    "dev_type_id": 34,
                    "device_type_name": "智联空调室内机 (Mesh RA)",
                    "room_id": 1,
                    "unit_id": idx,
                    "name": f"Mesh_Node_{idx}",
                    "mac": n_mac,
                    "alias": f"Mesh AC {idx} (MAC: {n_mac})",
                    "code": f"R1U{idx}",
                }
                self.topology["devices"].append(dev_entry)
            return self.topology

        logger.info("  ℹ️ No Room topology table returned by gateway.")
        logger.info("  💡 Automatically switching to Standalone Direct AC Device Probing...")
        return self.test_probe_direct_devices()

    def test_probe_direct_devices(self) -> Dict[str, Any]:
        """Probe standalone Air Conditioners directly across known device targets and unit IDs."""
        logger.info("🔬 [Standalone AC Probe] Probing Direct AC Targets & OpCodes (No Room Topology Required)...")

        probe_targets = [
            (DEV_MESHID_RA, "智联空调室内机 (Mesh RA)"),
            (DEV_RA, "分体机/家用空调 (RA AC)"),
            (DEV_NEWAIRCON, "金制空调室内机 (New AirCon)"),
            (DEV_AIRCON, "VRV空调室内机 (VRV AC)"),
            (DEV_MESHID_MESH_COMMON, "Mesh通用设备 (Mesh Common)"),
            (DEV_IP_MESH_COMMON, "IP Mesh网关 (IP Mesh)"),
            (DEV_LSM, "线控器/情景面板 (LSM)"),
            (DEV_MESHID_LSM, "Mesh线控器 (Mesh LSM)"),
            (DEV_BATHROOM, "卫浴空调 (Bathroom AC)"),
            (DEV_VENTILATION, "新风机 (Ventilation)"),
            (DEV_SMALL_VAM, "微型新风 (MiniVAM)"),
            (DEV_HD, "地暖/卫浴 (HD)"),
            (DEV_SENSOR, "空气传感器 (Sensor)"),
        ]

        candidate_addrs = [(1, 1), (1, 0), (0, 0), (0, 1), (2, 0)]
        responsive_devs = []

        for dev_target, dev_name in probe_targets:
            logger.info("  🔎 Probing [%s] (Cat: %d, Type: %d) ...", dev_name, dev_target[0], dev_target[1])

            if dev_target in (DEV_AIRCON, DEV_NEWAIRCON, DEV_BATHROOM):
                for r_id, u_id in candidate_addrs:
                    self.send_cmd(dev_target, CMD_AIR_STATUS_QUERY, subbody=bytes([r_id, u_id, 0x77]))
                    self.send_cmd(dev_target, CMD_AIR_CAPABILITY_QUERY, subbody=bytes([0x01, r_id, 0x01, 0x00]))
                self.send_cmd(dev_target, CMD_AIR_RECOMMENDED_TEMP)

            elif dev_target in (DEV_RA, DEV_MESHID_RA):
                for r_id, u_id in candidate_addrs:
                    self.send_cmd(dev_target, CMD_RA_01, subbody=bytes([r_id, u_id]))
                    self.send_cmd(dev_target, CMD_RA_QUERY_STATUS, subbody=bytes([r_id, u_id, 0x77]))
                    self.send_cmd(dev_target, CMD_RA_CMD_TYPE, subbody=bytes([r_id, u_id]))
                    self.send_cmd(dev_target, CMD_RA_QUERY_CAPABILITY, subbody=bytes([0x01, r_id, 0x01, 0x00]))

            elif dev_target in (DEV_IP_MESH_COMMON, DEV_MESHID_MESH_COMMON):
                self.send_cmd(dev_target, 0x0003, subbody=bytes([0x01, 0x01, 0x77]))
                self.send_cmd(dev_target, 0x0004, subbody=bytes([0x01, 0x01]))
                self.send_cmd(dev_target, 0x0081, subbody=b"")
                self.send_cmd(dev_target, 0x0083, subbody=bytes([0x01, 0x01]))

            elif dev_target in (DEV_LSM, DEV_MESHID_LSM):
                self.send_cmd(dev_target, CMD_LSM_GET_DETAIL, subbody=bytes([0x01, 0x01]))
                self.send_cmd(dev_target, CMD_LSM_QUERY_STATUS, subbody=bytes([0x01, 0x01]))
                self.send_cmd(dev_target, CMD_LSM_QUERY_CAPABILITY, subbody=bytes([0x01, 0x01]))

            elif dev_target in (DEV_VENTILATION, DEV_SMALL_VAM):
                for r_id, u_id in candidate_addrs[:2]:
                    self.send_cmd(dev_target, CMD_VAM_STATUS_QUERY, subbody=bytes([r_id, u_id, 0x77]))
                    self.send_cmd(dev_target, CMD_VAM_COMPOSITE_QUERY, subbody=bytes([r_id, u_id]))

            elif dev_target == DEV_HD:
                for r_id, u_id in candidate_addrs[:2]:
                    self.send_cmd(dev_target, CMD_HD_STATUS_QUERY, subbody=bytes([r_id, u_id]))
                    self.send_cmd(dev_target, CMD_HD_DEVICE_INFO, subbody=bytes([r_id, u_id]))

            elif dev_target == DEV_SENSOR:
                self.send_cmd(DEV_SENSOR, CMD_SENSOR_INFO_2, subbody=bytes([0xFF]))
                self.send_cmd(DEV_SENSOR, CMD_SENSOR_INFO_1, subbody=bytes([0xFF]))

            frames = self.recv_frames(wait_sec=1.5)
            if frames:
                logger.info("    🎉 Target [%s] responded with %d frame(s)!", dev_name, len(frames))
                for f in frames:
                    cmd = f.get("cmd_name", f["cmd_hex"])
                    data = f.get("data", {})
                    logger.info("       ├─ Cmd: %s (%s) | Raw: %s", cmd, f["cmd_hex"], f.get("raw_subbody", ""))
                    if "status" in data:
                        st = data["status"]
                        r_id = st.get("room_id", 1)
                        u_id = st.get("unit_id", 1)
                        name = st.get("name", dev_name)
                        mac = st.get("mac", "")
                        dev_entry = {
                            "dev_key": dev_target,
                            "dev_cat": dev_target[0],
                            "dev_type_id": dev_target[1],
                            "device_type_name": dev_name,
                            "room_id": r_id,
                            "unit_id": u_id,
                            "name": name,
                            "mac": mac,
                            "alias": f"{name} (Addr: R{r_id}U{u_id})",
                            "code": f"R{r_id}U{u_id}",
                        }
                        if not any(d["dev_key"] == dev_target and d["room_id"] == r_id and d["unit_id"] == u_id for d in responsive_devs):
                            responsive_devs.append(dev_entry)

                    elif "mesh_node" in data:
                        node = data["mesh_node"]
                        r_id = node.get("room_id", 1)
                        u_id = node.get("unit_id", 1)
                        name = node.get("name", "Mesh_Node")
                        mac = node.get("mac", "")
                        dev_entry = {
                            "dev_key": DEV_MESHID_RA,
                            "dev_cat": 12,
                            "dev_type_id": 34,
                            "device_type_name": "智联空调室内机 (Mesh RA)",
                            "room_id": r_id,
                            "unit_id": u_id,
                            "name": name,
                            "mac": mac,
                            "alias": f"{name} (Mesh RA R{r_id}U{u_id})",
                            "code": f"R{r_id}U{u_id}",
                        }
                        if not any(d["room_id"] == r_id and d["unit_id"] == u_id for d in responsive_devs):
                            responsive_devs.append(dev_entry)

                    elif "capability" in data:
                        logger.info("       └─ Supported Modes: %s", [m["mode"] for m in data["capability"].get("modes", [])])

        if responsive_devs:
            logger.info("  🎯 Discovered %d Responsive Standalone/Mesh AC Unit(s):", len(responsive_devs))
            for d in responsive_devs:
                logger.info("     • [%s] Target: %s | Addr: Room %d, Unit %d",
                            d["alias"], d["dev_key"], d["room_id"], d["unit_id"])
            self.topology["devices"] = responsive_devs
        else:
            logger.info("  ℹ️ Registering default target addresses (R1U1, R0U0, R1U0) for Status Query...")
            fallback_devices = [
                {
                    "dev_key": DEV_MESHID_RA,
                    "dev_cat": 12,
                    "dev_type_id": 34,
                    "device_type_name": "智联空调室内机 (Mesh RA)",
                    "room_id": 1,
                    "unit_id": 1,
                    "alias": "小木屋空调 (Mesh RA R1U1)",
                    "code": "R1U1",
                    "mac": "22:10:06:1C:44:50",
                },
                {
                    "dev_key": DEV_RA,
                    "dev_cat": 10,
                    "dev_type_id": 34,
                    "device_type_name": "分体机 (RA AC)",
                    "room_id": 1,
                    "unit_id": 1,
                    "alias": "分体机空调 (RA R1U1)",
                    "code": "R1U1",
                },
                {
                    "dev_key": DEV_NEWAIRCON,
                    "dev_cat": 8,
                    "dev_type_id": 23,
                    "device_type_name": "金制空调室内机 (New AirCon)",
                    "room_id": 1,
                    "unit_id": 1,
                    "alias": "金制空调 (NewAirCon R1U1)",
                    "code": "R1U1",
                },
                {
                    "dev_key": DEV_AIRCON,
                    "dev_cat": 8,
                    "dev_type_id": 18,
                    "device_type_name": "VRV空调室内机 (VRV AC)",
                    "room_id": 1,
                    "unit_id": 1,
                    "alias": "独立空调 (AirCon R1U1)",
                    "code": "R1U1",
                },
            ]
            self.topology["devices"] = fallback_devices

        return self.topology

    def test_query_all_devices_status(self):
        """Step 4: Query real-time status & capabilities for all discovered devices."""
        logger.info("📊 [Test 4] Querying Real-time Status for all Devices...")
        devices = self.topology.get("devices", [])
        if not devices:
            logger.warning("  ⚠️ No devices found in cache.")
            return

        for dev in devices:
            dev_key = dev["dev_key"]
            room_id = dev.get("room_id", 1)
            unit_id = dev.get("unit_id", 1)
            alias = dev["alias"]
            mac_str = dev.get("mac", "")
            mac_raw = bytes.fromhex(mac_str.replace(":", "")) if mac_str else b""

            logger.info("  ❄️ Querying AC Status for [%s] (Room %d, Unit %d, MAC: %s)...", alias, room_id, unit_id, mac_str or "N/A")

            # Try multiple protocol addressing formats
            # Format A: (12, 34) MESHID_RA
            self.send_cmd(DEV_MESHID_RA, CMD_RA_QUERY_STATUS, subbody=bytes([room_id, unit_id, 0x77]))
            self.send_cmd(DEV_MESHID_RA, CMD_RA_01, subbody=bytes([room_id, unit_id]))
            self.send_cmd(DEV_MESHID_RA, CMD_RA_CMD_TYPE, subbody=bytes([room_id, unit_id]))
            self.send_cmd(DEV_MESHID_RA, CMD_RA_QUERY_CAPABILITY, subbody=bytes([0x01, room_id, 0x01, 0x00]))

            # Format B: (10, 34) IP_RA
            self.send_cmd(DEV_RA, CMD_RA_QUERY_STATUS, subbody=bytes([room_id, unit_id, 0x77]))
            self.send_cmd(DEV_RA, CMD_RA_01, subbody=bytes([room_id, unit_id]))

            # Format C: (8, 23) NEWAIRCON & (8, 18) AIRCON
            self.send_cmd(DEV_NEWAIRCON, CMD_AIR_STATUS_QUERY, subbody=bytes([room_id, unit_id, 0x77]))
            self.send_cmd(DEV_AIRCON, CMD_AIR_STATUS_QUERY, subbody=bytes([room_id, unit_id, 0x77]))

            # Format D: With MAC payload if available
            if mac_raw:
                self.send_cmd(DEV_MESHID_RA, CMD_RA_QUERY_STATUS, subbody=mac_raw + bytes([room_id, unit_id, 0x77]))
                self.send_cmd(DEV_MESHID_MESH_COMMON, 0x0003, subbody=mac_raw + bytes([0x77]))
                self.send_cmd(DEV_MESHID_MESH_COMMON, 0x0004, subbody=mac_raw)
                self.send_cmd(DEV_MESHID_MESH_COMMON, 0x0083, subbody=mac_raw)
                self.send_cmd(DEV_IP_MESH_COMMON, 0x0083, subbody=mac_raw)

            # Format E: Direct Mesh Basic Info (0x0083) with [room_id, unit_id]
            self.send_cmd(DEV_MESHID_MESH_COMMON, 0x0083, subbody=bytes([room_id, unit_id]))
            self.send_cmd(DEV_IP_MESH_COMMON, 0x0083, subbody=bytes([room_id, unit_id]))

            if dev_key == DEV_LSM or dev_key == DEV_MESHID_LSM:
                self.send_cmd(dev_key, CMD_LSM_QUERY_STATUS, subbody=bytes([room_id, unit_id]))

            elif dev_key == DEV_SENSOR:
                self.send_cmd(DEV_SENSOR, CMD_SENSOR_INFO_2, subbody=bytes([0xFF]))

            elif dev_key in (DEV_VENTILATION, DEV_SMALL_VAM):
                self.send_cmd(dev_key, CMD_VAM_STATUS_QUERY, subbody=bytes([room_id, unit_id, 0x77]))

            elif dev_key in (DEV_HD, DEV_GEOTHERMIC):
                self.send_cmd(dev_key, CMD_HD_STATUS_QUERY, subbody=bytes([room_id, unit_id]))

        # Receive all responses
        frames = self.recv_frames(wait_sec=3.5)
        logger.info("  ✅ Received %d telemetry frame(s). Current Device Telemetry Summary:", len(frames))

        for dev in devices:
            dev_key = dev["dev_key"]
            room_id = dev.get("room_id", 1)
            unit_id = dev.get("unit_id", 1)
            alias = dev["alias"]
            state = self.device_states.get(f"{dev_key[0]}_{dev_key[1]}_{room_id}_{unit_id}", {})
            if not state:
                # Also check cross-dev state
                for k, v in self.device_states.items():
                    if f"_{room_id}_{unit_id}" in k:
                        state = v
                        break

            if dev_key in (DEV_AIRCON, DEV_NEWAIRCON, DEV_BATHROOM, DEV_RA, DEV_MESHID_RA, DEV_LSM, DEV_MESHID_LSM, DEV_MESHID_MESH_COMMON, DEV_IP_MESH_COMMON):
                logger.info(
                    "    ❄️ AC [%s]: Power=%s | Mode=%s | TargetTemp=%s°C | CurrentTemp=%s°C | Fan=%s | Swing=%s",
                    alias,
                    "ON" if state.get("is_on") else "OFF" if "is_on" in state else "N/A",
                    state.get("mode", "N/A"),
                    state.get("target_temp", "N/A"),
                    state.get("current_temp", "N/A"),
                    state.get("fan_speed", "N/A"),
                    state.get("fan_direction", "N/A"),
                )
            elif dev_key == DEV_SENSOR:
                s_state = self.device_states.get(f"{dev_key[0]}_{dev_key[1]}_sensor", {})
                logger.info(
                    "    🌡️ Sensor [%s]: Temp=%s°C | Humidity=%s%% | PM2.5=%s ug/m³ | CO2=%s ppm | TVOC=%s | HCHO=%s mg/m³",
                    alias,
                    s_state.get("temperature", "N/A"),
                    s_state.get("humidity", "N/A"),
                    s_state.get("pm25", "N/A"),
                    s_state.get("co2", "N/A"),
                    s_state.get("tvoc", "N/A"),
                    s_state.get("hcho", "N/A"),
                )

    def control_aircon(
        self,
        target_dev: Tuple[int, int] = DEV_AIRCON,
        room_id: int = 1,
        unit_id: int = 1,
        mac: str = "",
        power: Optional[bool] = None,
        mode: Optional[int] = None,
        temp: Optional[float] = None,
        fan_speed: Optional[int] = None,
        fan_direction: Optional[int] = None,
        dry_run: bool = False,
    ) -> bool:
        """Send AC Control command to specified target and address."""
        dev_name = DEVICE_NAMES.get(target_dev, f"Device{target_dev}")
        logger.info("🎮 [Control AC] Target=%s | RoomID=%d | UnitID=%d | Power=%s | Mode=%s | Temp=%s | Fan=%s (DryRun=%s)",
                    dev_name, room_id, unit_id, power, mode, temp, fan_speed, dry_run)
        buf = BinaryBuffer()
        buf.write_u8(room_id)
        buf.write_u8(unit_id)

        flag = 0
        val_list: List[Tuple[int, int]] = []  # (bytes_len, value)

        if power is not None:
            flag |= CTRL_FLAG_SWITCH
            val_list.append((1, 1 if power else 2))

        if mode is not None:
            flag |= CTRL_FLAG_MODE
            val_list.append((1, int(mode)))

        if fan_speed is not None:
            flag |= CTRL_FLAG_AIR_FLOW
            val_list.append((1, int(fan_speed)))

        if temp is not None:
            flag |= CTRL_FLAG_SETTED_TEMP
            val_list.append((2, int(temp * 10)))

        if fan_direction is not None:
            flag |= CTRL_FLAG_FAN_DIRECTION
            val_list.append((1, int(fan_direction)))

        buf.write_u8(flag)
        for val_len, val in val_list:
            if val_len == 1:
                buf.write_u8(val)
            elif val_len == 2:
                buf.write_u16(val)

        subbody = buf.pack(rewrite_len=False)

        # Build candidate control frames
        frames_to_send = [
            (target_dev, CMD_AIR_STATUS_CONTROL, subbody),
            (DEV_MESHID_RA, CMD_AIR_STATUS_CONTROL, subbody),
            (DEV_RA, CMD_AIR_STATUS_CONTROL, subbody),
            (DEV_NEWAIRCON, CMD_AIR_STATUS_CONTROL, subbody),
            (DEV_MESHID_MESH_COMMON, 0x0001, subbody),
        ]

        mac_raw = bytes.fromhex(mac.replace(":", "")) if mac else b""
        if not mac_raw:
            for d in self.topology.get("devices", []):
                if d.get("mac"):
                    mac_raw = bytes.fromhex(d["mac"].replace(":", ""))
                    break

        if mac_raw:
            frames_to_send.append((DEV_MESHID_MESH_COMMON, 0x000E, mac_raw + bytes([
                1 if power else 2 if power is False else 0,
                int(mode) if mode is not None else 0,
                int(temp) if temp is not None else 25,
                int(fan_speed) if fan_speed is not None else 5,
                int(fan_direction) if fan_direction is not None else 0,
            ])))
            frames_to_send.append((DEV_MESHID_MESH_COMMON, 0x0001, mac_raw + subbody))
            frames_to_send.append((DEV_MESHID_RA, CMD_AIR_STATUS_CONTROL, mac_raw + subbody))

        if dry_run:
            for d_t, cmd, s_b in frames_to_send:
                f = build_frame(d_t, cmd, subbody=s_b, seq_id=self._next_seq())
                logger.info("  [DryRun] Frame (%s / 0x%04X): %s", DEVICE_NAMES.get(d_t, d_t), cmd, f.hex())
            return True

        for d_t, cmd, s_b in frames_to_send:
            f = build_frame(d_t, cmd, subbody=s_b, seq_id=self._next_seq())
            logger.info("  >>> Sending Control (%s / 0x%04X): %s", DEVICE_NAMES.get(d_t, d_t), cmd, f.hex())
            self.send_raw_frame(f)

        frames = self.recv_frames(wait_sec=2.5)
        logger.info("  ✅ Received %d response frame(s).", len(frames))
        return True

    def test_probe_all_opcodes(self):
        """Exhaustive OpCode and Device Category Prober."""
        logger.info("🔬 [Exhaustive Scanner] Scanning all known Daikin Mina OpCodes and Device Categories...")
        scan_devs = [
            DEV_SYSTEM,
            DEV_AIRCON,
            DEV_NEWAIRCON,
            DEV_RA,
            DEV_LSM,
            DEV_BATHROOM,
            DEV_VENTILATION,
            DEV_SMALL_VAM,
            DEV_HD,
            DEV_SENSOR,
            DEV_HUMIDIFIER,
        ]
        scan_cmds = [
            (0x0001, "0x0001 (SYS_ACK / CONTROL / DETAIL)"),
            (0x0002, "0x0002 (STATUS_CHANGED / RSP)"),
            (0x0003, "0x0003 (QUERY_STATUS)"),
            (0x0004, "0x0004 (RECOMMENDED_TEMP / RA_CMD)"),
            (0x0005, "0x0005 (TIME_SYNC)"),
            (0x0006, "0x0006 (CAPABILITY_QUERY)"),
            (0x0007, "0x0007 (WEATHER)"),
            (0x0010, "0x0010 (LOGIN)"),
            (0x0023, "0x0023 (CAPABILITY_V2)"),
            (0x0030, "0x0030 (GET_ROOM_INFO)"),
            (0x0130, "0x0130 (GET_ROOM_INFO_V1)"),
            (0x0034, "0x0034 (COMPOSITE_QUERY)"),
            (0x0050, "0x0050 (GET_GW_INFO)"),
            (0x0055, "0x0055 (CHECK_NEW_VERSION)"),
            (0x0059, "0x0059 (SENSOR2_INFO)"),
            (0x005B, "0x005B (SENSOR2_STATUS)"),
            (0xA000, "0xA000 (HANDSHAKE)"),
        ]

        results = []
        for dev in scan_devs:
            dev_name = DEVICE_NAMES.get(dev, f"Dev{dev}")
            for cmd_code, cmd_label in scan_cmds:
                subbodies = [b"", bytes([0x00, 0x00, 0x77]), bytes([0x01, 0x00, 0x77]), bytes([0x01, 0xFF, 0xFF])]
                for sub in subbodies:
                    self.send_cmd(dev, cmd_code, subbody=sub, subbody_ver=0)
                frames = self.recv_frames(wait_sec=0.4)
                if frames:
                    for f in frames:
                        res_entry = {
                            "target_dev": dev,
                            "target_name": dev_name,
                            "cmd_sent": cmd_code,
                            "cmd_label": cmd_label,
                            "resp_cmd": f.get("cmd_hex"),
                            "resp_name": f.get("cmd_name", "UNKNOWN"),
                            "subbody_hex": f.get("raw_subbody", ""),
                        }
                        results.append(res_entry)
                        logger.info("  🎯 HIT! Target: %s | Sent: %s -> Response: %s (%s) | Data: %s",
                                    dev_name, cmd_label, f.get("cmd_hex"), f.get("cmd_name", ""), f.get("raw_subbody", ""))

        logger.info("\n📋 [Exhaustive Scan Summary] Found %d responsive command response(s):", len(results))
        for r in results:
            logger.info("   • Target %s: Cmd %s -> Resp %s: %s",
                        r["target_name"], r["cmd_label"], r["resp_cmd"], r["subbody_hex"])

    def send_custom_command(
        self,
        dev_cat: int,
        dev_type_id: int,
        cmd_type: int,
        subbody_hex: str = "",
        subbody_ver: int = 0,
        need_ack: int = 1,
    ):
        """Send arbitrary custom command frame and display raw response."""
        dev_target = (dev_cat, dev_type_id)
        dev_name = DEVICE_NAMES.get(dev_target, f"Device({dev_cat},{dev_type_id})")
        subbody = bytes.fromhex(subbody_hex) if subbody_hex else b""

        logger.info("🛠️ [Custom Command] Target: %s (Cat: %d, Type: %d) | Cmd: 0x%04X | Subbody: %s",
                    dev_name, dev_cat, dev_type_id, cmd_type, subbody.hex() or "(None)")
        self.send_cmd(dev_target, cmd_type, subbody=subbody, subbody_ver=subbody_ver, need_ack=need_ack)
        frames = self.recv_frames(wait_sec=3.0)
        logger.info("  ✅ Received %d response frame(s):", len(frames))
        for idx, f in enumerate(frames, 1):
            logger.info("    [%d] Cmd: %s (%s) | Subbody Len: %d | Hex: %s",
                        idx, f.get("cmd_name", "UNKNOWN"), f["cmd_hex"], f["subbody_len"], f.get("raw_subbody", ""))

    def start_monitor(self, duration_sec: int = 60, heartbeat_interval: int = 30):
        """Live streaming event monitor."""
        logger.info("📡 [Live Monitor] Starting Real-time Push Stream (Duration: %ds, Heartbeat: %ds)...",
                    duration_sec, heartbeat_interval)
        logger.info("   (Press Ctrl+C to stop monitoring at any time)\n")

        start_time = time.time()
        last_hb = start_time

        try:
            while time.time() - start_time < duration_sec:
                if time.time() - last_hb >= heartbeat_interval:
                    self.send_cmd(DEV_SYSTEM, CMD_SYS_ACK, need_ack=0)
                    last_hb = time.time()

                ready, _, _ = select.select([self.sock], [], [], 1.0)
                if ready:
                    chunk = self.sock.recv(4096)
                    if not chunk:
                        logger.warning("Server disconnected stream.")
                        break
                    if self.show_raw:
                        logger.info("  <<< RX (%d bytes): %s", len(chunk), chunk.hex())
                    self.recv_buffer += chunk
                    frames, self.recv_buffer = FrameDecoder.decode_frames(self.recv_buffer)
                    for f in frames:
                        t_str = time.strftime("%H:%M:%S")
                        logger.info("🔔 [%s] Event from %s - Cmd %s (%s):",
                                    t_str, f["dev_type_name"], f.get("cmd_name", "UNKNOWN"), f["cmd_hex"])
                        if "data" in f:
                            for k, v in f["data"].items():
                                logger.info("     └─ %s: %s", k, v)
        except KeyboardInterrupt:
            logger.info("\n🛑 Monitor stopped by user.")


# ---------------------------------------------------------------------------
# Offline Decoder Self-Test Suite
# ---------------------------------------------------------------------------
def run_offline_self_test():
    """Verify frame encoding & decoding against protocol test vectors."""
    logger.info("🧪 [Self-Test] Running offline protocol frame verification...")

    test_vectors = [
        # Vector 1: SYS_ACK
        ("0211000d0000000100000000000000000001000203", DEV_SYSTEM, CMD_SYS_ACK),
        # Vector 2: SYS_HAND_SHAKE
        ("0210000d0000000100000000000000000100a003", DEV_SYSTEM, CMD_SYS_HANDSHAKE),
        # Vector 3: SYS_HAND_SHAKE with Timestamp
        ("021e000d0000000100000000000000000000a0323031393036323430303137313803", DEV_SYSTEM, CMD_SYS_HANDSHAKE),
        # Vector 4: SYS_GET_ROOM_INFO Query
        ("0213000d00010002000000000000000001300001ffff03", DEV_SYSTEM, CMD_SYS_GET_ROOM_INFO),
        # Vector 5: AIR_CAPABILITY_QUERY
        ("0211000d0000000500000008120000000106000003", DEV_AIRCON, CMD_AIR_CAPABILITY_QUERY),
        # Vector 6: AIR_STATUS_QUERY (New AirCon)
        ("0213000d00000009000000081700000001030002007703", DEV_NEWAIRCON, CMD_AIR_STATUS_QUERY),
    ]

    passed = 0
    for idx, (raw_hex, expected_dev, expected_cmd) in enumerate(test_vectors, 1):
        raw_bytes = bytes.fromhex(raw_hex)
        frames, rem = FrameDecoder.decode_frames(raw_bytes)
        if len(frames) == 1:
            f = frames[0]
            if f["dev_key"] == expected_dev and f["cmd_type"] == expected_cmd:
                logger.info("  ✅ Vector %d passed: dev_key=%s (%s), cmd=0x%04X (%s)",
                            idx, f["dev_key"], f["dev_type_name"], f["cmd_type"], f.get("cmd_name", ""))
                passed += 1
            else:
                logger.error("  ❌ Vector %d mismatch: expected %s / 0x%04X, got %s / 0x%04X",
                             idx, expected_dev, expected_cmd, f["dev_key"], f["cmd_type"])
        else:
            logger.error("  ❌ Vector %d failed to decode: got %d frames", idx, len(frames))

    # Test Frame Builder roundtrip
    built_frame = build_frame(DEV_AIRCON, CMD_AIR_STATUS_CONTROL, subbody=bytes([0x01, 0x01, 0x03]), seq_id=42)
    frames, _ = FrameDecoder.decode_frames(built_frame)
    if frames and frames[0]["dev_key"] == DEV_AIRCON and frames[0]["cmd_type"] == CMD_AIR_STATUS_CONTROL:
        logger.info("  ✅ Frame Builder roundtrip test passed: %s", built_frame.hex())
        passed += 1
    else:
        logger.error("  ❌ Frame Builder roundtrip test failed!")

    # Test UDP 8111 Packet Builder
    udp_pkt_6 = build_udp_search_packet("AABBCCDDEEFF")
    udp_pkt_7 = build_udp_search_packet("AABBCCDDEEFF00")
    if len(udp_pkt_6) == 11 and udp_pkt_6[0] == 0x32 and udp_pkt_6[1] == 1 and udp_pkt_6[-1] == 3:
        logger.info("  ✅ UDP 8111 Search Packet (6-byte) builder passed: %s", udp_pkt_6.hex())
        passed += 1
    else:
        logger.error("  ❌ UDP 8111 Search Packet builder failed")

    if len(udp_pkt_7) == 12 and udp_pkt_7[0] == 0x32 and udp_pkt_7[1] == 3 and udp_pkt_7[-1] == 3:
        logger.info("  ✅ UDP 8111 7-byte Search Packet builder passed: %s", udp_pkt_7.hex())
        passed += 1
    else:
        logger.error("  ❌ UDP 8111 7-byte Search Packet builder failed")

    # Test UDP 8111 Response Decoder
    mock_ip = b"192.168.1.100"
    mock_mac = bytes([0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF])
    i2 = len(mock_ip) + 12 + 1  # 26
    payload = mock_ip + mock_mac + bytes([0] * (i2 - len(mock_ip) - len(mock_mac)))
    mock_udp_resp = bytes([0x32, 0x02, i2, 0x00]) + payload + bytes([0x03])
    decoded_udp = decode_udp_discovery_packet(mock_udp_resp, ("192.168.1.100", 8111))
    if decoded_udp and decoded_udp["ip"] == "192.168.1.100" and decoded_udp["mac"] == "AA:BB:CC:DD:EE:FF":
        logger.info("  ✅ UDP 8111 Response Decoder test passed: IP=%s, MAC=%s", decoded_udp["ip"], decoded_udp["mac"])
        passed += 1
    else:
        logger.error("  ❌ UDP 8111 Response Decoder test failed: %s", decoded_udp)

    total_tests = len(test_vectors) + 4
    logger.info("🎉 Self-test complete: %d/%d test cases passed successfully!\n", passed, total_tests)
    return passed == total_tests


# ---------------------------------------------------------------------------
# Main CLI Entry Point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Daikin DS-AIR / 金制空气 Local Protocol Test Suite (Ports 8008, 8009, 8111)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 1. Connect and automatically probe gateway/standalone AC (auto-fallback 8008/8009):
  python3 test_local_protocol.py --host 192.168.22.132

  # 2. Verbose / Debug mode showing all raw hex frames exchanged:
  python3 test_local_protocol.py --host 192.168.22.132 --debug

  # 3. Exhaustively scan all known device categories & opcodes:
  python3 test_local_protocol.py --host 192.168.22.132 --probe-all

  # 4. Query status for specific device target (e.g. aircon, newaircon, ra, lsm, sensor):
  python3 test_local_protocol.py --host 192.168.22.132 --dev-type aircon --room 0 --unit 0 --status

  # 5. Send AC control command (Turn ON, 25°C, Cool mode) to Standalone AC (Room 0 Unit 0):
  python3 test_local_protocol.py --host 192.168.22.132 --control-ac --dev-type aircon --room 0 --unit 0 --power on --temp 25.0 --mode 0

  # 6. Send custom raw command frame (e.g. Cat 8, Type 18, Cmd 0x0003, Subbody 000077):
  python3 test_local_protocol.py --host 192.168.22.132 --custom-cmd 8 18 3 000077

  # 7. Monitor live streaming events:
  python3 test_local_protocol.py --host 192.168.22.132 --monitor 60
        """,
    )
    parser.add_argument("--self-test", action="store_true", help="Run offline decoder self-test suite")
    parser.add_argument("--list-ifaces", action="store_true", help="List all detected network interfaces")
    parser.add_argument("--discover", action="store_true", help="Run UDP broadcast discovery for gateways")
    parser.add_argument("--iface", "--interface", dest="iface", type=str, default="", help="Network interface name or IP for UDP discovery")
    parser.add_argument("--scan", action="store_true", help="Scan and probe TCP 8008, TCP 8009, and UDP 8111 on target host")
    parser.add_argument("--udp-probe", action="store_true", help="Send direct unicast search packet to target host on UDP 8111")
    parser.add_argument("--listen-udp", type=int, nargs="?", const=30, default=0, help="Listen for UDP 8111 broadcasts for N seconds")
    parser.add_argument("--udp-port", type=int, default=DEFAULT_UDP_PORT, help="UDP discovery port (default: 8111)")
    parser.add_argument("--host", type=str, default="", help="DS-AIR Gateway / Standalone AC IP address")
    parser.add_argument("--port", type=int, default=8008, help="DS-AIR Gateway TCP port (default: 8008, auto-fallbacks to 8009)")
    parser.add_argument("--no-fallback", action="store_true", help="Disable automatic fallback between ports 8008 and 8009")
    parser.add_argument("--timeout", type=float, default=5.0, help="Socket timeout in seconds (default: 5.0)")
    parser.add_argument("--debug", "-v", "--verbose", action="store_true", help="Enable verbose debug logging and raw frame traces")
    parser.add_argument("--raw", action="store_true", help="Print all raw hex packets sent and received")
    parser.add_argument("--probe-all", action="store_true", help="Exhaustively probe all known opcodes and device categories")
    parser.add_argument("--probe-devices", action="store_true", help="Run direct standalone device probing")
    parser.add_argument("--status", "--query-status", dest="query_status", action="store_true", help="Direct query device status")
    parser.add_argument("--dev-type", "--dev-target", dest="dev_type", type=str, default="aircon",
                        help="Target device type (aircon, newaircon, ra, lsm, bathroom, ventilation, sensor, hd, or 'cat,type_id')")
    parser.add_argument("--room", type=int, default=0, help="Target room ID (default: 0)")
    parser.add_argument("--unit", type=int, default=0, help="Target unit ID (default: 0)")
    parser.add_argument("--monitor", type=int, nargs="?", const=60, default=0, help="Start live push stream monitor for N seconds (default: 60s)")
    parser.add_argument("--control-ac", action="store_true", help="Send test control command to AC unit")
    parser.add_argument("--power", choices=["on", "off"], help="Power state for control")
    parser.add_argument("--temp", type=float, help="Target temperature (°C)")
    parser.add_argument("--mode", type=int, choices=list(range(10)), help="AC mode index (0:Cool, 1:Dry, 2:Fan, 3:Auto, 4:Heat)")
    parser.add_argument("--fan", type=int, choices=list(range(7)), help="Fan speed index (0..6)")
    parser.add_argument("--direction", "--swing", type=int, choices=list(range(8)), help="Fan direction / swing (0..7)")
    parser.add_argument("--dry-run", action="store_true", help="Dry-run: show control frame without sending")
    parser.add_argument("--custom-cmd", nargs="+", help="Send custom command: <dev_cat> <dev_type_id> <cmd_type> [subbody_hex]")

    args = parser.parse_args()

    # Configure logging level
    setup_logging(debug=args.debug)

    # If --list-ifaces requested
    if args.list_ifaces:
        print_network_interfaces()
        return

    # If --listen-udp requested
    if args.listen_udp > 0:
        listen_udp_broadcast(port=args.udp_port, duration_sec=args.listen_udp)
        return

    # If --self-test requested or no arguments passed
    if args.self_test or len(sys.argv) == 1:
        run_offline_self_test()
        if len(sys.argv) == 1:
            parser.print_help()
        return

    # If --discover requested
    if args.discover:
        gws = discover_gateways(iface=args.iface, timeout=args.timeout, port=args.udp_port)
        if gws and not args.host:
            args.host = gws[0]["ip"]
            args.port = gws[0].get("port", args.port)
            logger.info("💡 Auto-selected first discovered gateway: %s (Port: %d)", args.host, args.port)
        elif not gws:
            logger.info("ℹ️ No gateways responded to UDP broadcast on local network.")
            return

    # Host check
    if not args.host:
        logger.error("❌ Please provide gateway IP with --host <IP> or use --discover")
        sys.exit(1)

    # If --scan requested
    if args.scan:
        probe_gateway_services(args.host, timeout=args.timeout)
        return

    # If --udp-probe requested
    if args.udp_probe:
        res = unicast_udp_probe(args.host, port=args.udp_port, timeout=args.timeout)
        if res:
            logger.info("✅ UDP 8111 Probe Succeeded! Gateway IP: %s | MAC: %s", res["ip"], res["mac"])
        else:
            logger.warning("❌ No response to UDP 8111 probe from %s", args.host)
        return

    # Parse target device
    target_dev_tuple = parse_dev_target_arg(args.dev_type)

    # Initialize Tester Client with Port Fallback
    tester = DairLocalTester(
        host=args.host,
        port=args.port,
        timeout=args.timeout,
        auto_fallback=not args.no_fallback,
        show_raw=args.raw or args.debug,
    )
    if not tester.connect():
        sys.exit(1)

    try:
        # If custom command requested
        if args.custom_cmd:
            cat = int(args.custom_cmd[0], 0)
            t_id = int(args.custom_cmd[1], 0)
            c_type = int(args.custom_cmd[2], 0)
            sub_hex = args.custom_cmd[3] if len(args.custom_cmd) > 3 else ""
            tester.send_custom_command(cat, t_id, c_type, sub_hex)
            return

        # 1. Handshake
        tester.test_handshake()
        time.sleep(0.2)

        # 2. Heartbeat
        tester.test_heartbeat()
        time.sleep(0.2)

        # 3. Query System / Gateway info
        tester.test_probe_gateway_info()
        time.sleep(0.2)

        # If --probe-all requested: run exhaustive opcode probe
        if args.probe_all:
            tester.test_probe_all_opcodes()
            return

        # 4. Topology & Room Info (with automatic standalone direct probing fallback)
        if args.probe_devices:
            tester.test_probe_direct_devices()
        else:
            tester.test_query_rooms_and_topology()
        time.sleep(0.2)

        # 5. Device Status Query
        tester.test_query_all_devices_status()

        # 6. Control test if requested
        if args.control_ac:
            power_val = True if args.power == "on" else False if args.power == "off" else None
            tester.control_aircon(
                target_dev=target_dev_tuple,
                room_id=args.room,
                unit_id=args.unit,
                power=power_val,
                mode=args.mode,
                temp=args.temp,
                fan_speed=args.fan,
                fan_direction=args.direction,
                dry_run=args.dry_run,
            )

        # 7. Live Stream Monitor if requested
        if args.monitor > 0:
            tester.start_monitor(duration_sec=args.monitor)

    finally:
        tester.close()


if __name__ == "__main__":
    main()
