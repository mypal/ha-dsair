"""Platform for DS-AIR of Daikin

https://www.daikin-china.com.cn/newha/products/4/19/DS-AIR/
"""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from .const import (
    CONF_GW,
    DEFAULT_GW,
    DOMAIN,
    MANUFACTURER,
    get_default_gateway_name,
    get_gateway_name,
    is_legacy_gateway_title,
)
from .descriptions import SENSOR_DESCRIPTORS
from .ds_air_service import Config, Service
from .ds_air_service.dao import migrate_legacy_sensor_links, migrate_legacy_unique_id

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.CLIMATE,
    Platform.SENSOR,
]


def _gateway_name(hass: HomeAssistant, entry: ConfigEntry) -> str:
    return get_gateway_name(hass.config.language, entry.data[CONF_HOST], entry.title)


def _migrate_entity_registry_unique_ids(
    hass: HomeAssistant, entry: ConfigEntry, gateway_id: str
) -> None:
    entity_registry = er.async_get(hass)
    sensor_keys = SENSOR_DESCRIPTORS.keys()

    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        new_unique_id = migrate_legacy_unique_id(
            entity_entry.unique_id, gateway_id, sensor_keys
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
    sensor_keys = SENSOR_DESCRIPTORS.keys()

    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        new_identifiers: set[tuple[str, str]] = set()
        changed = False
        has_conflict = False

        for domain, identifier in device_entry.identifiers:
            if domain != DOMAIN:
                new_identifiers.add((domain, identifier))
                continue

            new_identifier = migrate_legacy_unique_id(identifier, gateway_id, sensor_keys)
            if new_identifier is None:
                new_identifiers.add((domain, identifier))
                continue

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
                has_conflict = True
                break

            new_identifiers.add((domain, new_identifier))
            changed = True

        if changed and not has_conflict:
            device_registry.async_update_device(
                device_entry.id, new_identifiers=new_identifiers
            )


def _migrate_options_unique_ids(options: dict, gateway_id: str) -> tuple[dict, bool]:
    links = options.get("link")
    if not isinstance(links, list):
        return options, False

    changed = False
    migrated_links: list[dict] = []
    for link in links:
        if not isinstance(link, dict):
            migrated_links.append(link)
            continue

        migrated_link = dict(link)
        climate_id = migrated_link.get("climate")
        if isinstance(climate_id, str):
            migrated_climate_id = migrate_legacy_unique_id(climate_id, gateway_id)
            if migrated_climate_id is not None:
                migrated_link["climate"] = migrated_climate_id
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
    minor_version = getattr(entry, "minor_version", 1)
    _LOGGER.debug(
        "Migrating DS-AIR config entry from version %s.%s",
        entry.version,
        minor_version,
    )

    if entry.version > 1:
        return False

    gateway_id = entry.entry_id
    _migrate_entity_registry_unique_ids(hass, entry, gateway_id)
    _migrate_device_registry_identifiers(hass, entry, gateway_id)

    update: dict = {"version": 1}
    if minor_version < 2:
        update["minor_version"] = 2
    options, options_changed = _migrate_options_unique_ids(
        dict(entry.options), gateway_id
    )
    if options_changed:
        update["options"] = options
    if entry.data.get(CONF_HOST) and is_legacy_gateway_title(entry.title):
        update["title"] = get_default_gateway_name(
            hass.config.language, entry.data[CONF_HOST]
        )

    hass.config_entries.async_update_entry(entry, **update)
    _LOGGER.debug("Migration to DS-AIR config entry version 1.2 successful")

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    gw = entry.data[CONF_GW]
    scan_interval = entry.data[CONF_SCAN_INTERVAL]

    _LOGGER.debug("%s:%s %s %s", host, port, gw, scan_interval)

    config = Config()
    config.gateway_id = entry.entry_id
    config.is_c611 = gw == DEFAULT_GW

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer=MANUFACTURER,
        model=gw,
        name=_gateway_name(hass, entry),
    )

    service = Service()
    hass.data[DOMAIN][entry.entry_id] = service
    await hass.async_add_executor_job(service.init, host, port, scan_interval, config)
    _migrate_legacy_sensor_links(hass, entry, service)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
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
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    # reference: https://developers.home-assistant.io/docs/device_registry_index/#removing-devices
    return True
