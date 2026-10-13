"""回归测试：官方 App 同款 ``subbody_ver=0`` 与 ``SYS_GET_GW_INFO`` 解析。

背景（真机实测，固件 02.18.12）：

* 用 ``subbody_ver=1`` 握手建立的会话里，网关会对 ``CONTROL`` 帧回 ACK，
  然后**静默忽略**——内机状态不变（反复验证：单发开关位、带模式、带温度都无效）。
* 把握手帧与控制帧都换成官方 App 同款的 ``subbody_ver=0`` 后，控制立即生效
  （另开一个会话读网关回报：ON → OFF 均正确）。
* ``SYS_GET_GW_INFO(80)`` 之前落到 ``UnknownResult``，这里顺带锁住其子体解析。

本文件只依赖协议层，不引入 Home Assistant。
"""

from pathlib import Path
import select  # noqa: F401 — 先加载标准库 select，避免被 ds_air/select.py 遮蔽
import struct
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "ds_air"))

from ds_air_service.config import Config  # noqa: E402
from ds_air_service.ctrl_enum import EnumControl  # noqa: E402
from ds_air_service.dao import AirCon, AirConStatus  # noqa: E402
from ds_air_service.decoder import decoder  # noqa: E402
from ds_air_service.param import AirConControlParam, HandShakeParam, Param  # noqa: E402

# 官方 App 抓帧（仓库 tests/protocol-demo.txt）里的握手帧
OFFICIAL_HANDSHAKE = "0210000d0000000100000000000000000100a003"


def make_config() -> Config:
    config = Config()
    config.gateway_id = "test-gateway"
    config.is_c611 = True
    return config


class FakeService:
    """只实现本测试用到的两个 setter。"""

    def __init__(self):
        self.gw_info = None
        self.last_error = None

    def set_gw_info(self, value):
        self.gw_info = value

    def set_last_error(self, value):
        self.last_error = value


def tlv(text: str) -> bytes:
    """按长度前缀封一段文本（子体里每个字段都是 [len][payload]）。"""
    raw = text.encode("ascii")
    return bytes([len(raw)]) + raw


def build_frame(
    cmd_type: int,
    subbody: bytes,
    cmd_id: int = 1,
    dev_type: int = 0,
    dev_id: int = 0,
    subbody_ver: int = 0,
) -> bytes:
    body = (
        bytes([0x0D, 0x00, subbody_ver, 0x00])
        + cmd_id.to_bytes(4, "little")
        + bytes([dev_type])
        + dev_id.to_bytes(4, "little")
        + bytes([0x01])
        + cmd_type.to_bytes(2, "little")
        + subbody
    )
    total = 1 + 2 + len(body) + 1
    return bytes([0x02]) + (total - 4).to_bytes(2, "little") + body + bytes([0x03])


class SubbodyVersionTests(unittest.TestCase):
    """会话版本必须与官方 App 一致，否则控制会被静默丢弃。"""

    def test_handshake_matches_official_app_frame(self):
        Param.cnt = 0  # 命令 ID 是全局自增计数器，先归零才能逐字节比对
        frame = HandShakeParam().to_string(make_config())
        self.assertEqual(frame.hex(), OFFICIAL_HANDSHAKE)

    def test_handshake_subbody_version_is_zero(self):
        self.assertEqual(HandShakeParam().to_string(make_config())[5], 0)

    def test_aircon_control_subbody_version_is_zero(self):
        config = make_config()
        aircon = AirCon(config)
        aircon.room_id = 1
        aircon.unit_id = 0
        status = AirConStatus(switch=EnumControl.Switch.ON)

        frame = AirConControlParam(aircon, status).to_string(config)

        self.assertEqual(frame[5], 0)  # subbody_ver
        self.assertEqual(frame[17:19], b"\x01\x00")  # CONTROL
        # room / unit / flag(SWITCH) / value(ON)
        self.assertEqual(frame[19:23], bytes([1, 0, 0x01, 0x01]))


class GatewayInfoTests(unittest.TestCase):
    """SYS_GET_GW_INFO(80) 的子体解析（原实现是空的 Todo）。"""

    def test_get_gw_info_is_parsed_and_stored(self):
        subbody = (
            tlv("03.01.00")
            + b"\x00"
            + bytes([0x00, 0x11, 0x22, 0x33, 0x44, 0x55])
            + tlv("10.0.0.5")
            + tlv("255.255.255.0")
            + tlv("10.0.0.1")
            + tlv("8.8.8.8")
            + tlv("10.0.0.254")
            + bytes([7])
            + struct.pack("<H", 2026)
            + bytes([10, 13, 12, 30, 56])
        )

        result, rest = decoder(build_frame(0x0050, subbody), make_config())

        self.assertFalse(rest, "整帧应被消费完")
        self.assertEqual(result.__class__.__name__, "GetGWInfoResult")

        service = FakeService()
        result.do(service)
        self.assertEqual(service.gw_info["version"], "03.01.00")
        self.assertEqual(service.gw_info["mac"], "00:11:22:33:44:55")
        self.assertEqual(service.gw_info["ip"], "10.0.0.5")
        self.assertEqual(service.gw_info["mask"], "255.255.255.0")
        self.assertEqual(service.gw_info["dns1"], "10.0.0.1")
        self.assertEqual(service.gw_info["dns2"], "8.8.8.8")
        self.assertEqual(service.gw_info["gateway"], "10.0.0.254")
        self.assertEqual(service.gw_info["time"], "2026-10-13 12:30:56")


class ErrCodeTests(unittest.TestCase):
    """故障码：4 字节标志位与 ASCII 故障码要分开。"""

    def test_err_code_keeps_flag_and_clean_code(self):
        subbody = bytes([0x12, 0, 0, 0, 6, 0]) + bytes([0x01, 0, 0, 0x02]) + b"00"

        result, _ = decoder(build_frame(0x0006, subbody), make_config())

        self.assertEqual(result.__class__.__name__, "ErrCodeResult")
        self.assertEqual(result.code, "00")
        self.assertEqual(result.flag.hex(), "01000002")
        self.assertEqual(result.room, 6)
        self.assertEqual(result.unit, 0)


if __name__ == "__main__":
    unittest.main()
