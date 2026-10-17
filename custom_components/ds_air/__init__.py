"""Platform for DS-AIR of Daikin

https://www.daikin-china.com.cn/newha/products/4/19/DS-AIR/
"""

import logging
from datetime import datetime
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_ENTRY_TYPE,
    CONF_GW,
    C611,
    D611,
    F611,
    DEFAULT_GW,
    DOMAIN,
    ENTRY_TYPE_POWER,
    MANUFACTURER,
    SERVICE_GET_POWER_DATA,
)
from .coordinator import DsAirPowerCoordinator
from .descriptions import SENSOR_DESCRIPTORS
from .ds_air_service import Config, Service
from .ds_air_service.dao import migrate_legacy_sensor_links, migrate_legacy_unique_id

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.FAN,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.WATER_HEATER,
]


def _migrate_entity_registry_unique_ids(
    hass: HomeAssistant, entry: ConfigEntry, gateway_id: str
) -> None:
    entity_registry = er.async_get(hass)

    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        if not isinstance(entity_entry.unique_id, str):
            continue

        new_unique_id = migrate_legacy_unique_id(
            entity_entry.unique_id, gateway_id, SENSOR_DESCRIPTORS
        )
        if new_unique_id is None:
            continue

        conflict_entity_id = entity_registry.async_get_entity_id(
            entity_entry.domain, entity_entry.platform, new_unique_id
        )
        if conflict_entity_id and conflict_entity_id != entity_entry.entity_id:
            _LOGGER.warning(
                "Unable to migrate entity %s unique_id to %s: already used by %s",
                entity_entry.entity_id,
                new_unique_id,
                conflict_entity_id,
            )
            continue

        entity_registry.async_update_entity(
            entity_entry.entity_id, new_unique_id=new_unique_id
        )


def _migrate_device_registry_identifiers(
    hass: HomeAssistant, entry: ConfigEntry, gateway_id: str
) -> None:
    device_registry = dr.async_get(hass)

    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        identifiers = set(device_entry.identifiers)
        new_identifiers = set()

        for domain, identifier in identifiers:
            if domain != DOMAIN:
                new_identifiers.add((domain, identifier))
                continue

            new_identifier = migrate_legacy_unique_id(
                identifier, gateway_id, SENSOR_DESCRIPTORS
            )
            if new_identifier is not None:
                conflict_device = device_registry.async_get_device(
                    identifiers={(domain, new_identifier)}
                )
                if conflict_device and conflict_device.id != device_entry.id:
                    _LOGGER.warning(
                        "Unable to migrate device %s identifier to %s: already used by %s",
                        device_entry.id,
                        new_identifier,
                        conflict_device.id,
                    )
                    new_identifier = None
            new_identifiers.add((domain, new_identifier or identifier))

        if new_identifiers != identifiers:
            device_registry.async_update_device(
                device_entry.id, new_identifiers=new_identifiers
            )


def _migrate_options_unique_ids(options: dict, gateway_id: str) -> tuple[dict, bool]:
    links = options.get("link")
    if not isinstance(links, list):
        return options, False

    changed = False
    migrated_links = []
    for link in links:
        if not isinstance(link, dict):
            migrated_links.append(link)
            continue

        migrated_link = dict(link)
        climate_id = migrated_link.get("climate")
        if isinstance(climate_id, str):
            new_climate_id = migrate_legacy_unique_id(climate_id, gateway_id)
            if new_climate_id is not None:
                migrated_link["climate"] = new_climate_id
                changed = True
        migrated_links.append(migrated_link)

    if not changed:
        return options, False
    return {**options, "link": migrated_links}, True


def _migrate_legacy_sensor_links(
    hass: HomeAssistant, entry: ConfigEntry, service: Service
) -> None:
    links = entry.options.get("link")
    if not isinstance(links, list):
        return

    migrated_links, changed = migrate_legacy_sensor_links(links, service.get_aircons())
    if changed:
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, "link": migrated_links}
        )


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entries to gateway-scoped unique IDs."""
    if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_POWER or CONF_HOST not in entry.data:
        return True

    if entry.version > 2:
        return False
    if entry.version == 2:
        return True

    gateway_id = entry.entry_id
    _migrate_entity_registry_unique_ids(hass, entry, gateway_id)
    _migrate_device_registry_identifiers(hass, entry, gateway_id)

    options, options_changed = _migrate_options_unique_ids(
        dict(entry.options), gateway_id
    )
    update = {"version": 2}
    if options_changed:
        update["options"] = options

    hass.config_entries.async_update_entry(entry, **update)
    return True


GET_POWER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional("year"): cv.positive_int,
        vol.Optional("month"): vol.All(cv.positive_int, vol.Range(min=1, max=12)),
        vol.Optional("home_id"): cv.positive_int,
        vol.Optional("import_to_statistics", default=True): cv.boolean,
    }
)


def _async_register_services(hass: HomeAssistant) -> None:
    """Register ds_air integration services."""
    if hass.services.has_service(DOMAIN, SERVICE_GET_POWER_DATA):
        return

    async def _async_handle_get_power_data(call: ServiceCall) -> ServiceResponse:
        now = datetime.now()
        year = call.data.get("year", now.year)
        month = call.data.get("month", now.month)
        home_id = call.data.get("home_id")
        import_to_stats = call.data.get("import_to_statistics", True)

        coordinators: list[DsAirPowerCoordinator] = [
            coord
            for coord in hass.data.get(DOMAIN, {}).values()
            if isinstance(coord, DsAirPowerCoordinator)
        ]

        if not coordinators:
            raise HomeAssistantError("未找到任何已配置的大金电量统计集成条目")

        target_coordinator: DsAirPowerCoordinator | None = None
        if home_id is not None:
            for coord in coordinators:
                if coord.home_id == home_id:
                    target_coordinator = coord
                    break
            if target_coordinator is None:
                raise HomeAssistantError(f"未找到 home_id={home_id} 的电量统计配置")
        else:
            if len(coordinators) == 1:
                target_coordinator = coordinators[0]
            else:
                available_ids = [c.home_id for c in coordinators]
                raise HomeAssistantError(
                    f"当前配置了多个家庭电量统计 ({available_ids})，请在调用服务时指定 home_id"
                )

        try:
            power_data = await hass.async_add_executor_job(
                target_coordinator.fetch_historical_power, year, month
            )
        except Exception as err:
            raise HomeAssistantError(f"获取历史电量数据失败: {err}") from err

        imported = False
        if import_to_stats:
            try:
                await target_coordinator.async_import_month_statistics(
                    year, month, power_data, statistic_id=target_coordinator.month_statistic_id
                )
                imported = bool(target_coordinator.month_statistic_id)
            except Exception as err:
                _LOGGER.warning("服务导入长期统计失败: %s", err)

        return {
            "home_id": power_data.get("home_id"),
            "home_name": power_data.get("home_name"),
            "year": power_data.get("year"),
            "month": power_data.get("month"),
            "total": power_data.get("total"),
            "price": power_data.get("price"),
            "estimated_cost": power_data.get("estimated_cost"),
            "yesterday_used": power_data.get("yesterday_used"),
            "consumptions": power_data.get("consumptions", []),
            "daily_details": power_data.get("daily_details", []),
            "imported_to_statistics": imported,
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_POWER_DATA,
        _async_handle_get_power_data,
        schema=GET_POWER_DATA_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the DS-AIR component."""
    hass.data.setdefault(DOMAIN, {})
    _async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    _async_register_services(hass)

    # 电量统计条目设置
    if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_POWER or CONF_HOST not in entry.data:
        coordinator = DsAirPowerCoordinator(hass, entry)
        hass.data[DOMAIN][entry.entry_id] = coordinator

        coordinator.start_scheduler()
        await coordinator.async_config_entry_first_refresh()

        await hass.config_entries.async_forward_entry_setups(
            entry, [Platform.SENSOR]
        )
        entry.async_on_unload(entry.add_update_listener(update_listener))
        return True

    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    gw = entry.data[CONF_GW]
    scan_interval = entry.data[CONF_SCAN_INTERVAL]

    _LOGGER.debug("%s:%s %s %s", host, port, gw, scan_interval)

    config = Config()
    config.gateway_id = entry.entry_id
    config.is_c611 = gw == C611
    config.is_d611 = gw == D611
    config.is_f611 = gw == F611

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer=MANUFACTURER,
        model=gw,
        name=entry.title,
    )

    service = Service()
    hass.data[DOMAIN][entry.entry_id] = service
    try:
        await hass.async_add_executor_job(
            service.init, host, port, scan_interval, config
        )
    except TimeoutError as exc:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        raise ConfigEntryNotReady(str(exc)) from exc
    _migrate_legacy_sensor_links(hass, entry, service)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # 电量统计条目卸载
    if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_POWER or CONF_HOST not in entry.data:
        coordinator: DsAirPowerCoordinator = hass.data[DOMAIN].pop(
            entry.entry_id, None
        )
        if coordinator:
            coordinator.stop_scheduler()

        unload_ok = await hass.config_entries.async_unload_platforms(
            entry, [Platform.SENSOR]
        )
        return unload_ok

    service: Service = hass.data[DOMAIN].pop(entry.entry_id)

    if service.state_change_listener is not None:
        service.state_change_listener()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    service.destroy()

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    # reference: https://developers.home-assistant.io/docs/device_registry_index/#removing-devices
    return True
