from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    MAJOR_VERSION,
    PERCENTAGE,
    UnitOfTemperature,
)

FROZEN = MAJOR_VERSION >= 2024


@dataclass(frozen=FROZEN, kw_only=True)
class DsSensorEntityDescription(SensorEntityDescription):
    has_entity_name: bool = True
    state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT
    value_fn: Callable[[Any], Any] | None = lambda x: x


VOC_OPTIONS = ["优", "低", "中", "高"]


SENSOR_DESCRIPTORS = {
    "temp": DsSensorEntityDescription(
        key="temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda x: x / 10,
    ),
    "humidity": DsSensorEntityDescription(
        key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        value_fn=lambda x: x / 10,
    ),
    "pm25": DsSensorEntityDescription(
        key="pm25",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
    ),
    "co2": DsSensorEntityDescription(
        key="co2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
    ),
    "tvoc": DsSensorEntityDescription(
        key="tvoc",
        name="TVOC",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        suggested_display_precision=0,
        value_fn=lambda x: x * 10,
    ),
    "voc": DsSensorEntityDescription(
        key="voc",
        device_class=SensorDeviceClass.ENUM,
        state_class=None,
        options=VOC_OPTIONS,
        # EnumSensor.Voc，不可用/未知等级映射为 None
        value_fn=lambda x: s if (s := str(x)) in VOC_OPTIONS else None,
    ),
    "hcho": DsSensorEntityDescription(
        key="hcho",
        name="HCHO",
        native_unit_of_measurement=CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
        value_fn=lambda x: x / 100,
    ),
}
