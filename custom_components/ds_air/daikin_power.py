# -*- coding: utf-8 -*-
"""Daikin Jinzhi Air (金制空气) Power Consumption API Client for Home Assistant."""

import base64
from datetime import datetime
import logging
import os
import ssl
import tempfile
import time
from typing import Any, Dict, List, Optional
import urllib.parse

from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    load_pem_public_key,
    pkcs12,
)
import requests
from requests.adapters import HTTPAdapter

_LOGGER = logging.getLogger(__name__)

# 大金 APK (金制空气 4.7.4) 内置的 RSA 公钥，用于解密 p12 证书密码
RSA_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAm6hQn1LlnQ0DzG0ZiKUP
hNHUUJeFCgw5m/sUPkbOpgwui5Br6OQkrW/+yKeHn6gRLWNqW0+ULha/9lhWWUJm
1O9aYCYPnYrZh6IplBZL72Ad8mHxcXALc9y0wxr9QoF5X2kidZLxiOuoiPq5Pjwx
T/uH/8uYWbAVwlD+e1fjB7hJt8zubxFEbuhvLjMZ8bshCSn55yNVwwOasOORZwjD
UyLdGyl8TA149d7HCUXV0iUqnmfOkniio9nrBc2T1xb4aePP45wJEUFV6I1A3haG
hXBlHNjfR1/vdMViac3DRa+Q2PCDdjcJVE2EzvWapkOxewIYpWlHvqyKkUbhICO/
LQIDAQAB
-----END PUBLIC KEY-----"""

DEFAULT_CLIENT_ID_PREFIX = "daikin_ha_client_"


class MTLSAdapter(HTTPAdapter):
    """支持自定义 SSLContext (含客户端证书与降级加密套件) 的 Requests 适配器"""

    def __init__(self, ssl_context: ssl.SSLContext, **kwargs):
        self.ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = self.ssl_context
        return super().init_poolmanager(*args, **kwargs)


class DaikinPowerClient:
    """大金金制空气 API 客户端"""

    CERT_INFO_URL = "https://newlifemulti.daikin-china.com.cn:443/v2/home/getCertificateInfo"
    API_BASE_URL = "https://newlifemulti.daikin-china.com.cn:4443/v2"
    POWER_DATA_WEB_URL = "https://newlifemulti.daikin-china.com.cn/v2/web/getHomePowerData"

    def __init__(
        self,
        client_id: Optional[str] = None,
        cert_cache_dir: Optional[str] = None,
    ):
        self.client_id = client_id or (DEFAULT_CLIENT_ID_PREFIX + str(int(time.time())))
        self.cert_cache_dir = cert_cache_dir or os.path.join(
            tempfile.gettempdir(), "ds_air_cert"
        )
        self.session = requests.Session()
        self.access_token: Optional[str] = None
        self.ssl_context: Optional[ssl.SSLContext] = None
        self.temp_files: List[str] = []

    def __del__(self):
        # 清理临时证书文件
        for f in self.temp_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass

    @staticmethod
    def _calc_cert_password(client_id: str) -> str:
        """还原 APK 中 CalculateCertPasswordHelper 的 CRC16 累加算法"""
        j2 = 0
        for b in client_id.encode("utf-8"):
            j3 = j2 ^ b
            for _ in range(8):
                if (j3 & 1) == 1:
                    j3 ^= 67601  # 0x10811
                j3 = (j3 & 0xFFFFFFFF) // 2
            j2 = j3 & 0xFFFF
        return f"{j2:04X}"

    @staticmethod
    def _decrypt_cert_password(encrypted_b64: str) -> str:
        """使用内置 RSA 公钥解密证书密码 (RSA/ECB/PKCS1Padding)"""
        key = load_pem_public_key(RSA_PUBLIC_KEY_PEM.encode("utf-8"))
        numbers = key.public_numbers()
        c_bytes = base64.b64decode(encrypted_b64)
        c_int = int.from_bytes(c_bytes, "big")
        m_int = pow(c_int, numbers.e, numbers.n)
        m_bytes = m_int.to_bytes((numbers.n.bit_length() + 7) // 8, "big")
        idx = m_bytes.find(b"\x00", 2)
        if idx == -1:
            raise ValueError("无法解析 PKCS1Padding 填充内容")
        return m_bytes[idx + 1 :].decode("utf-8")

    def init_mtls(self, force_refresh: bool = False):
        """下载并加载大金 mTLS 双向认证客户端证书"""
        os.makedirs(self.cert_cache_dir, exist_ok=True)
        p12_path = os.path.join(self.cert_cache_dir, "client.p12")
        pwd_path = os.path.join(self.cert_cache_dir, "cert_password.txt")

        p12_bytes = None
        cert_password_str = None

        if not force_refresh and os.path.exists(p12_path) and os.path.exists(pwd_path):
            try:
                with open(p12_path, "rb") as f:
                    p12_bytes = f.read()
                with open(pwd_path, "r", encoding="utf-8") as f:
                    cert_password_str = f.read().strip()
            except Exception:
                p12_bytes = None

        if not p12_bytes or not cert_password_str:
            _LOGGER.debug("正在向大金证书服务器请求客户端证书...")
            pwd_calc = self._calc_cert_password(self.client_id)
            payload = {
                "clientId": self.client_id,
                "password": pwd_calc,
                "fileType": "p12",
                "clientType": "APP",
            }
            resp = requests.post(
                self.CERT_INFO_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
            res_json = resp.json()
            if res_json.get("code") != 0:
                raise RuntimeError(f"获取证书信息失败: {res_json}")

            download_info = res_json["data"]["downloadInfo"]
            p12_download_url = download_info["resourcesPath"]
            cert_pwd_enc = download_info["certPassword"]

            cert_password_str = self._decrypt_cert_password(cert_pwd_enc)

            p12_resp = requests.get(p12_download_url, timeout=20)
            p12_resp.raise_for_status()
            p12_bytes = p12_resp.content

            with open(p12_path, "wb") as f:
                f.write(p12_bytes)
            with open(pwd_path, "w", encoding="utf-8") as f:
                f.write(cert_password_str)
            _LOGGER.debug("客户端证书已缓存到本地")

        priv_key, cert, _ = pkcs12.load_key_and_certificates(
            p12_bytes, cert_password_str.encode("utf-8")
        )

        kf = tempfile.NamedTemporaryFile("wb", delete=False)
        cf = tempfile.NamedTemporaryFile("wb", delete=False)
        kf.write(priv_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
        cf.write(cert.public_bytes(Encoding.PEM))
        kf.flush()
        cf.flush()
        kf.close()
        cf.close()

        self.temp_files.extend([kf.name, cf.name])

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.set_ciphers("ALL:@SECLEVEL=0")
        ctx.load_cert_chain(certfile=cf.name, keyfile=kf.name)
        self.ssl_context = ctx

        self.session.mount("https://", MTLSAdapter(ctx))
        _LOGGER.debug("mTLS 安全通道建立成功")

    def request(
        self,
        endpoint: str,
        method: str = "POST",
        json_data: Optional[Dict[str, Any]] = None,
        form_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """发起携带证书与鉴权 Token 的 API 请求 (4443 端口)"""
        if not self.ssl_context:
            self.init_mtls()

        url = f"{self.API_BASE_URL}/{endpoint}"
        headers = {}
        if self.access_token:
            headers["token"] = self.access_token

        if method.upper() == "GET":
            params = params or {}
            params.setdefault("version", "1")

        if form_data:
            form_data = form_data.copy()
            form_data.setdefault("version", "1")
            resp = self.session.request(
                method, url, data=form_data, params=params, headers=headers, timeout=15
            )
        else:
            resp = self.session.request(
                method, url, json=json_data or {}, params=params, headers=headers, timeout=15
            )

        resp.raise_for_status()
        res_json = resp.json()
        return res_json

    def set_token(self, token: str):
        """直接设置已有 accessToken"""
        self.access_token = token

    def login_by_password(self, username: str, password: str) -> str:
        """账号密码登录"""
        res = self.request(
            "app/nlcLoginV2",
            method="POST",
            form_data={
                "authId": username,
                "password": password,
                "pushId": self.client_id,
            },
        )
        if res.get("code") == 0 and res.get("data"):
            self.access_token = res["data"]["accessToken"]
            _LOGGER.debug("登录成功，获取到 accessToken")
            return self.access_token
        raise RuntimeError(f"密码登录失败: {res.get('description', res)}")

    def get_homes(self) -> List[Dict[str, Any]]:
        """获取用户绑定的家庭列表"""
        res = self.request("home/listHomeByLoginUser", method="POST")
        if res.get("code") == 0:
            return res.get("data", [])
        raise RuntimeError(f"获取家庭列表失败: {res}")

    def get_power_consumption_url(self, home_id: int, user_type: str = "1") -> str:
        """获取电量统计 H5 页面的完整访问链接"""
        res = self.request(
            "home/getHomePowerDataUrl",
            method="POST",
            json_data={
                "homeId": int(home_id),
                "userType": str(user_type),
            },
        )
        if res.get("code") == 0 and res.get("data"):
            url = res["data"]["url"]
            _LOGGER.debug("成功获取电量统计 URL: %s", url)
            return url
        raise RuntimeError(f"获取电量统计 URL 失败: {res}")

    @staticmethod
    def extract_nlc_id_from_url(power_url: str) -> Optional[str]:
        """从电量统计 H5 URL 中解析出 nlcId / encryptNlcId"""
        parsed = urllib.parse.urlparse(power_url)
        query_params = urllib.parse.parse_qs(parsed.query)
        if "nlcId" in query_params and query_params["nlcId"]:
            return query_params["nlcId"][0]
        if "encryptNlcId" in query_params and query_params["encryptNlcId"]:
            return query_params["encryptNlcId"][0]
        return None

    def get_home_power_data(
        self,
        encrypt_nlc_id: str,
        home_id: int,
        year: int,
        month: int,
    ) -> Dict[str, Any]:
        """
        调用 Web H5 底层 API 获取指定年月的电量消耗明细 (JSON 格式)
        API: https://newlifemulti.daikin-china.com.cn/v2/web/getHomePowerData
        """
        url = self.POWER_DATA_WEB_URL
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Linux; Android 12; Mobile) Daikin/4.7.4 INLS",
            "Referer": "https://newlifemulti.daikin-china.com.cn/daikinStaticWeb/powerconsumptionV2/index_home.html",
        }
        form_data = {
            "encryptNlcId": str(encrypt_nlc_id),
            "homeId": int(home_id),
            "year": int(year),
            "month": int(month),
        }
        resp = requests.post(url, data=form_data, headers=headers, timeout=15)
        resp.raise_for_status()
        res_json = resp.json()
        if res_json.get("code") != 0:
            raise RuntimeError(f"获取电量数据失败: {res_json.get('description', res_json)}")
        return res_json

    def get_full_power_data(
        self,
        home_id: int,
        year: Optional[int] = None,
        month: Optional[int] = None,
        encrypt_nlc_id: Optional[str] = None,
        user_type: str = "1",
    ) -> Dict[str, Any]:
        """一站式获取电量数据：自动拉取 URL、提取 nlcId、获取底层 JSON 数据"""
        now = datetime.now()
        year = year or now.year
        month = month or now.month

        if not encrypt_nlc_id:
            power_url = self.get_power_consumption_url(home_id=home_id, user_type=user_type)
            encrypt_nlc_id = self.extract_nlc_id_from_url(power_url)
            if not encrypt_nlc_id:
                raise ValueError(f"无法从电量 URL 中提取 nlcId: {power_url}")

        return self.get_home_power_data(
            encrypt_nlc_id=encrypt_nlc_id,
            home_id=home_id,
            year=year,
            month=month,
        )
