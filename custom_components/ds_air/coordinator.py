"""DataUpdateCoordinator for Daikin Jinzhi Air Power Consumption."""

from datetime import datetime, timedelta
import logging
from typing import Any, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_HOME_ID, CONF_HOME_NAME, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from .daikin_power import DaikinPowerClient

_LOGGER = logging.getLogger(__name__)


class DsAirPowerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage fetching power consumption data from Daikin Cloud."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: Optional[DaikinPowerClient] = None,
    ) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.home_id: int = int(entry.data[CONF_HOME_ID])
        self.home_name: str = entry.data.get(CONF_HOME_NAME) or f"家庭 {self.home_id}"
        self.username: str = entry.data[CONF_USERNAME]
        self.password: str = entry.data[CONF_PASSWORD]
        self.month_statistic_id: Optional[str] = None

        cert_cache_dir = hass.config.path(".storage", "ds_air_cert")
        self.client = client or DaikinPowerClient(cert_cache_dir=cert_cache_dir)
        if CONF_TOKEN in entry.data and entry.data[CONF_TOKEN]:
            self.client.set_token(entry.data[CONF_TOKEN])

        super().__init__(
            hass,
            _LOGGER,
            name=f"DsAirPower_{self.home_id}",
            update_interval=None,  # 采用每天早上 5:00 定时触发，不使用高频轮询
        )

        self._unsub_timer: Optional[CALLBACK_TYPE] = None

    def set_month_statistic_id(self, statistic_id: str) -> None:
        """设置用于长期统计导入的实体 ID"""
        self.month_statistic_id = statistic_id

    def _update_token_threadsafe(self, new_token: str) -> None:
        """安全地在事件循环主线程中更新 ConfigEntry token"""
        def _do_update() -> None:
            self.hass.config_entries.async_update_entry(
                self.entry,
                data={**self.entry.data, CONF_TOKEN: new_token},
            )

        if hasattr(self.hass, "loop") and self.hass.loop is not None:
            self.hass.loop.call_soon_threadsafe(_do_update)
        else:
            _do_update()

    def start_scheduler(self) -> None:
        """注册每天早上 5:00 的定时任务"""
        if self._unsub_timer is not None:
            self._unsub_timer()

        @callback
        def _scheduled_update(now: datetime) -> None:
            _LOGGER.info(
                "触发大金电量统计每日 5:00 定时拉取任务 (家庭 ID: %s, 名称: %s)",
                self.home_id,
                self.home_name,
            )
            self.hass.async_create_task(self.async_request_refresh())

        self._unsub_timer = async_track_time_change(
            self.hass,
            _scheduled_update,
            hour=5,
            minute=0,
            second=0,
        )
        _LOGGER.debug(
            "已为家庭 %s 注册每天早上 05:00:00 的电量数据同步定时器", self.home_id
        )

    def stop_scheduler(self) -> None:
        """停止每日定时任务"""
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None
            _LOGGER.debug("已移除家庭 %s 的电量定时器", self.home_id)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch power data from Daikin Cloud in executor."""
        try:
            data = await self.hass.async_add_executor_job(self._sync_fetch_power_data)
            # 若已绑定统计实体，自动触发当月数据长期统计写入
            if self.month_statistic_id:
                self.hass.async_create_task(
                    self.async_import_month_statistics(
                        data.get("year", datetime.now().year),
                        data.get("month", datetime.now().month),
                        data,
                        statistic_id=self.month_statistic_id,
                    )
                )
            return data
        except Exception as err:
            _LOGGER.exception("获取大金电量数据异常: %s", err)
            raise UpdateFailed(f"获取电量数据失败: {err}") from err

    def _sync_fetch_power_data(self) -> dict[str, Any]:
        """同步执行网络请求拉取前一天及当月电量数据"""
        now = datetime.now()
        yesterday = now - timedelta(days=1)

        # 1. 尝试获取电量页面 URL，若 Token 失效则自动重新密码登录
        try:
            power_url = self.client.get_power_consumption_url(self.home_id)
        except Exception as err:
            _LOGGER.info("Token 可能已过期，尝试重新登录: %s", err)
            new_token = self.client.login_by_password(self.username, self.password)
            self._update_token_threadsafe(new_token)
            power_url = self.client.get_power_consumption_url(self.home_id)

        # 2. 从 URL 中解析 encryptNlcId
        encrypt_nlc_id = self.client.extract_nlc_id_from_url(power_url)
        if not encrypt_nlc_id:
            raise RuntimeError(f"未能从 URL 中提取 nlcId: {power_url}")

        # 3. 请求当前年月的电量数据
        res = self.client.get_home_power_data(
            encrypt_nlc_id=encrypt_nlc_id,
            home_id=self.home_id,
            year=now.year,
            month=now.month,
        )

        data = res.get("data", {})
        consumptions = data.get("consumptions", []) or []
        total = float(data.get("total", 0.0) or 0.0)
        price = float(data.get("price", 0.0) or 0.0)

        # 4. 提取“前一天”的电量数据
        yesterday_used: Optional[float] = None

        if yesterday.year == now.year and yesterday.month == now.month:
            # 昨天在当月内（非当月1号）
            day_idx = yesterday.day - 1
            if 0 <= day_idx < len(consumptions):
                yesterday_used = float(consumptions[day_idx])
        else:
            # 今天是当月 1 号，昨天在上个月，需跨月查询上个月的数据
            _LOGGER.debug(
                "检测到跨月查询前一天数据 (年份: %s, 月份: %s)",
                yesterday.year,
                yesterday.month,
            )
            try:
                prev_res = self.client.get_home_power_data(
                    encrypt_nlc_id=encrypt_nlc_id,
                    home_id=self.home_id,
                    year=yesterday.year,
                    month=yesterday.month,
                )
                prev_consumptions = prev_res.get("data", {}).get("consumptions", []) or []
                day_idx = yesterday.day - 1
                if 0 <= day_idx < len(prev_consumptions):
                    yesterday_used = float(prev_consumptions[day_idx])
            except Exception as e:
                _LOGGER.warning("跨月查询上月电量数据失败: %s", e)

        # 5. 若通过 consumptions 数组未能获取到有效值，则回退使用 API 返回的 yesterdayUsed
        if yesterday_used is None:
            raw_yesterday = data.get("yesterdayUsed")
            yesterday_used = float(raw_yesterday) if raw_yesterday is not None else 0.0

        estimated_cost = round(total * price, 2)

        _LOGGER.debug(
            "家庭 %s 电量更新完成: 前一日用电=%.3f kWh, 当月总用电=%.3f kWh, 单价=%.3f, 预估电费=%.2f",
            self.home_id,
            yesterday_used,
            total,
            price,
            estimated_cost,
        )

        return {
            "yesterday_used": yesterday_used,
            "yesterday_date": yesterday.strftime("%Y-%m-%d"),
            "total": total,
            "price": price,
            "estimated_cost": estimated_cost,
            "consumptions": consumptions,
            "year": data.get("year", now.year),
            "month": data.get("month", now.month),
            "home_id": self.home_id,
            "home_name": self.home_name,
            "last_updated": datetime.now().isoformat(),
        }

    def fetch_historical_power(self, year: int, month: int) -> dict[str, Any]:
        """按指定年份和月份直接查询电量数据 (供服务或外部调用)"""
        try:
            power_url = self.client.get_power_consumption_url(self.home_id)
        except Exception as err:
            _LOGGER.info("Token 可能已过期，尝试重新登录: %s", err)
            new_token = self.client.login_by_password(self.username, self.password)
            self._update_token_threadsafe(new_token)
            power_url = self.client.get_power_consumption_url(self.home_id)

        encrypt_nlc_id = self.client.extract_nlc_id_from_url(power_url)
        if not encrypt_nlc_id:
            raise RuntimeError(f"未能从 URL 中提取 nlcId: {power_url}")

        res = self.client.get_home_power_data(
            encrypt_nlc_id=encrypt_nlc_id,
            home_id=self.home_id,
            year=year,
            month=month,
        )

        data = res.get("data", {})
        consumptions = data.get("consumptions", []) or []
        total = float(data.get("total", 0.0) or 0.0)
        price = float(data.get("price", 0.0) or 0.0)
        estimated_cost = round(total * price, 2)
        raw_yesterday = data.get("yesterdayUsed")

        daily_details = [
            {
                "day": day_idx,
                "date": f"{year:04d}-{month:02d}-{day_idx:02d}",
                "consumption": float(val or 0.0),
            }
            for day_idx, val in enumerate(consumptions, start=1)
        ]

        return {
            "home_id": self.home_id,
            "home_name": self.home_name,
            "year": int(data.get("year", year)),
            "month": int(data.get("month", month)),
            "total": total,
            "price": price,
            "estimated_cost": estimated_cost,
            "yesterday_used": float(raw_yesterday) if raw_yesterday is not None else 0.0,
            "consumptions": consumptions,
            "daily_details": daily_details,
        }

    async def _async_get_base_sum_before(
        self, statistic_id: str, before_dt: datetime
    ) -> float:
        """查询在 before_dt 之前的最后一条统计数据的 sum 作为累加基准，避免重复累加。"""
        def _get_base():
            try:
                from homeassistant.components.recorder import get_instance
                from homeassistant.components.recorder.db_schema import Statistics
                from homeassistant.components.recorder.statistics import _statistics_at_time
                from homeassistant.components.recorder.util import session_scope

                instance = get_instance(self.hass)
                with session_scope(hass=self.hass, read_only=True) as session:
                    meta = instance.statistics_meta_manager.get_many(
                        session, statistic_ids={statistic_id}
                    )
                    if not meta or statistic_id not in meta:
                        return 0.0
                    metadata_id = meta[statistic_id][0]
                    rows = _statistics_at_time(
                        instance, session, {metadata_id}, Statistics, before_dt, {"sum"}
                    )
                    if rows:
                        for row in rows:
                            if getattr(row, "sum", None) is not None:
                                return float(row.sum)
            except Exception as err:
                _LOGGER.debug("查询基础累计值失败: %s", err)
            return 0.0

        try:
            from homeassistant.components.recorder import get_instance
            return await get_instance(self.hass).async_add_executor_job(_get_base)
        except Exception:
            return await self.hass.async_add_executor_job(_get_base)

    async def async_import_month_statistics(
        self,
        year: int,
        month: int,
        data: dict[str, Any],
        statistic_id: Optional[str] = None,
    ) -> None:
        """将某月每日用电数据直接注入 Home Assistant 长期统计库 (Long-Term Statistics)"""
        target_stat_id = statistic_id or self.month_statistic_id
        if not target_stat_id:
            _LOGGER.debug("未配置 statistic_id，跳过长期统计导入")
            return

        try:
            from homeassistant.components.recorder.models import (
                StatisticData,
                StatisticMetaData,
            )
            from homeassistant.components.recorder.statistics import async_import_statistics
            from homeassistant.util import dt as dt_util
        except ImportError:
            _LOGGER.debug("Recorder 组件未就绪，跳过长期统计写入")
            return

        consumptions = data.get("consumptions", [])
        if not consumptions:
            return

        tz = dt_util.get_time_zone(self.hass.config.time_zone)
        now = datetime.now()
        month_start_dt = datetime(year, month, 1, 0, 0, 0, tzinfo=tz)

        # 动态查询该月 1 号之前的最后一条统计累计值作为 base_sum
        base_sum = await self._async_get_base_sum_before(target_stat_id, month_start_dt)

        stats_to_import: list[StatisticData] = []
        accumulated_sum = 0.0

        for day_idx, val in enumerate(consumptions, start=1):
            # 若为当月，超过当前日期的数据（未来日期）不予导入
            if year == now.year and month == now.month and day_idx > now.day:
                break

            c_val = float(val or 0.0)
            accumulated_sum += c_val
            # 统计点时间设为当日当地时间 00:00:00 (随后由 HA 转为整点 UTC)
            day_dt = datetime(year, month, day_idx, 0, 0, 0, tzinfo=tz)

            stats_to_import.append(
                StatisticData(
                    start=day_dt,
                    state=c_val,
                    sum=round(base_sum + accumulated_sum, 3),
                )
            )

        if not stats_to_import:
            return

        try:
            from homeassistant.components.recorder.models import StatisticMeanType
            mean_type = StatisticMeanType.NONE
        except (ImportError, AttributeError):
            mean_type = 0

        metadata = StatisticMetaData(
            has_mean=False,
            mean_type=mean_type,
            has_sum=True,
            name=f"金制空气 ({self.home_name}) 当月累计用电",
            source="recorder",
            statistic_id=target_stat_id,
            unit_of_measurement="kWh",
            unit_class="energy",
        )

        try:
            async_import_statistics(self.hass, metadata, stats_to_import)
            _LOGGER.info(
                "成功为家庭 %s 导入 %04d年%02d月共 %d 条每日电量数据至长期统计库 (%s)",
                self.home_id,
                year,
                month,
                len(stats_to_import),
                target_stat_id,
            )
        except Exception as err:
            _LOGGER.warning("导入长期统计失败: %s", err)

