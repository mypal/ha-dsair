from homeassistant.const import TEMP_CELSIUS, PERCENTAGE, CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, \
    CONCENTRATION_PARTS_PER_MILLION, CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER
from homeassistant.components.sensor import SensorDeviceClass

from .ds_air_service.ctrl_enum import EnumSensor

DOMAIN = "ds_air"
CONF_GW = "gw"
DEFAULT_HOST = "192.168.1."
DEFAULT_PORT = 8008
DEFAULT_GW = "DTA117C611"
GW_LIST = ["DTA117C611", "DTA117B611"]
SENSOR_TYPES = {
    "temp": [TEMP_CELSIUS, None, SensorDeviceClass.TEMPERATURE, 10],
    "humidity": [PERCENTAGE, None, SensorDeviceClass.HUMIDITY, 10],
    "pm25": [CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, None, SensorDeviceClass.PM25, 1],
    "co2": [CONCENTRATION_PARTS_PER_MILLION, None, SensorDeviceClass.CO2, 1],
    "tvoc": [CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER, None, SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS, 100],
    "voc": [None, None, SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS, EnumSensor.Voc],
    "hcho": [CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER, None, None, 100],
}
