"""Platform for DS-AIR of Daikin

https://www.daikin-china.com.cn/newha/products/4/19/DS-AIR/
"""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import (
    CONF_CLOUD_HOME_ID,
    CONF_CLOUD_PASSWORD,
    CONF_CLOUD_USERNAME,
    CONF_CONNECTION_TYPE,
    CONNECTION_CLOUD,
    CONF_GW,
    C611,
    D611,
    DEFAULT_GW,
    DOMAIN,
    MANUFACTURER,
    SMART_MESH,
)
from .descriptions import SENSOR_DESCRIPTORS
from .ds_air_service import Config, Service
from .ds_air_service.dao import migrate_legacy_sensor_links, migrate_legacy_unique_id

_LOGGER = logging.getLogger(__name__)

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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    cloud_only = entry.data.get(CONF_CONNECTION_TYPE) == CONNECTION_CLOUD
    if not cloud_only and any(
        key in entry.options
        for key in ("cloud_enable", CONF_CLOUD_USERNAME, CONF_CLOUD_PASSWORD)
    ):
        # Hybrid local+cloud binding is no longer supported.  Remove legacy
        # credentials instead of leaving a password stored in local options.
        local_options = {
            key: value
            for key, value in entry.options.items()
            if key not in ("cloud_enable", CONF_CLOUD_USERNAME, CONF_CLOUD_PASSWORD)
        }
        hass.config_entries.async_update_entry(entry, options=local_options)
    host = entry.data.get(CONF_HOST, "cloud")
    port = entry.data.get(CONF_PORT, 0)
    gw = entry.data.get(CONF_GW, SMART_MESH if cloud_only else DEFAULT_GW)
    scan_interval = entry.data.get(CONF_SCAN_INTERVAL, 5)

    _LOGGER.debug("%s:%s %s %s", host, port, gw, scan_interval)

    config = Config()
    config.gateway_id = entry.entry_id
    config.is_c611 = gw == C611
    config.is_d611 = gw == D611
    config.is_mesh = gw == SMART_MESH

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
    cloud_client = None
    try:
        if cloud_only:
            from .ds_air_cloud import DaikinCloudClient

            cloud_client = DaikinCloudClient(
                entry.data.get(CONF_CLOUD_USERNAME),
                entry.data.get(CONF_CLOUD_PASSWORD),
            )
            if not await hass.async_add_executor_job(cloud_client.login):
                raise ConfigEntryNotReady("Unable to authenticate with Daikin Cloud")
            _, devices = await hass.async_add_executor_job(cloud_client.discover)
            home_id = entry.data.get(CONF_CLOUD_HOME_ID)
            if home_id:
                devices = [d for d in devices if int(d.get("homeId", 0)) == int(home_id)]
            if not devices:
                raise ConfigEntryNotReady("No Daikin Cloud RA devices found")
            service.init_cloud(cloud_client, devices, config)
            macs = [device.mac for device in service.get_aircons()]
            connected = await hass.async_add_executor_job(
                cloud_client.start_mqtt,
                int(home_id or devices[0]["homeId"]),
                service.handle_cloud_message,
                macs,
            )
            if not connected:
                raise ConfigEntryNotReady("Unable to connect to Daikin Cloud MQTT")
        else:
            await hass.async_add_executor_job(
                service.init, host, port, scan_interval, config
            )
    except (TimeoutError, ConfigEntryNotReady) as exc:
        if cloud_client is not None:
            cloud_client.close()
        hass.data[DOMAIN].pop(entry.entry_id, None)
        raise ConfigEntryNotReady(str(exc)) from exc
    _migrate_legacy_sensor_links(hass, entry, service)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    service: Service = hass.data[DOMAIN].pop(entry.entry_id)

    if getattr(service, "_cloud_client", None) is not None:
        service._cloud_client.close()

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
