"""Offers Daikin air quality data."""
from homeassistant.components.air_quality import AirQualityEntity


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Air Quality."""
    async_add_entities(
        [DemoAirQuality("Home", 14, 23, 100), DemoAirQuality("Office", 4, 16, None)]
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Demo config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class DemoAirQuality(AirQualityEntity):
    """Representation of Air Quality data."""

    def __init__(self, name, pm_2_5, pm_10, n2o):
        """Initialize the Demo Air Quality."""
        self._name = name
        self._pm_2_5 = pm_2_5
        self._pm_10 = pm_10
        self._n2o = n2o

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Demo Air Quality {self._name}"

    @property
    def should_poll(self):
        """No polling needed for Demo Air Quality."""
        return False

    @property
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        return self._pm_2_5

    @property
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        return self._pm_10

    @property
    def nitrogen_oxide(self):
        """Return the nitrogen oxide (N2O) level."""
        return self._n2o

    @property
    def attribution(self):
        """Return the attribution."""
        return "Powered by Home Assistant"
