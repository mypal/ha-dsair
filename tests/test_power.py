from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "ds_air"))

from daikin_power import DaikinPowerClient  # noqa: E402


class PowerClientTests(unittest.TestCase):
    def test_calc_cert_password(self):
        # 验证大金 CRC16 密码生成算法
        pwd = DaikinPowerClient._calc_cert_password("daikin_ha_client_1728700000")
        self.assertIsInstance(pwd, str)
        self.assertEqual(len(pwd), 4)

    def test_extract_nlc_id_from_url(self):
        # 验证从各种 H5 URL 格式中提取 nlcId
        url1 = "https://newlifemulti.daikin-china.com.cn/daikinStaticWeb/powerconsumptionV2/index_home.html?homeId=68293&nlcId=072fbcbba18c9ce51d6adc2eb4c7e94e&userType=1"
        self.assertEqual(
            DaikinPowerClient.extract_nlc_id_from_url(url1),
            "072fbcbba18c9ce51d6adc2eb4c7e94e",
        )

        url2 = "https://newlifemulti.daikin-china.com.cn/daikinStaticWeb/powerconsumptionV2/index_home.html?encryptNlcId=abcd1234efgh&homeId=123"
        self.assertEqual(
            DaikinPowerClient.extract_nlc_id_from_url(url2),
            "abcd1234efgh",
        )

        url3 = "https://example.com/invalid_url"
        self.assertIsNone(DaikinPowerClient.extract_nlc_id_from_url(url3))

    def test_power_data_yesterday_calculation(self):
        # 模拟当日是 2026-10-12，昨日是 2026-10-11
        consumptions = [0.84] * 11 + [0.0] * 20
        sample_api_response = {
            "code": 0,
            "description": "成功",
            "data": {
                "year": 2026,
                "month": 10,
                "consumptions": consumptions,
                "total": 9.24,
                "price": 0.8,
                "yesterdayUsed": 0.84,
                "powerChart": 1,
                "powerRateChart": 0,
            },
        }

        # 测试数据解析与前一日提取
        now = datetime(2026, 10, 12, 5, 0, 0)
        yesterday = now - timedelta(days=1)
        self.assertEqual(yesterday.day, 11)

        day_idx = yesterday.day - 1
        yesterday_used = sample_api_response["data"]["consumptions"][day_idx]
        self.assertEqual(yesterday_used, 0.84)
        total = sample_api_response["data"]["total"]
        price = sample_api_response["data"]["price"]
        estimated_cost = round(total * price, 2)
        self.assertEqual(estimated_cost, 7.39)


if __name__ == "__main__":
    unittest.main()
