import logging
from typing import Any
from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfElectricCurrent, UnitOfEnergy, UnitOfPower, UnitOfTemperature, UnitOfTime
from .entity import BaseSensor, BaseSwitch

from .coordinator import EcoflowCoordinatorDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator: EcoflowCoordinatorDataUpdateCoordinator = hass.data[DOMAIN]["coordinator"]
    _LOGGER.info("Init sensors")
    entities = []

    for device in coordinator.data:
        entities.extend(device._sensors())
    async_add_entities(entities)

class RemainSensorEntity(BaseSensor):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_value = 0

    def set_entity_value(self, value):
        self._attr_native_value = round(value)

class WattsSensorEntity(BaseSensor):
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_value = 0

    def set_entity_value(self, value):
        self._attr_native_value = round(value)

    def value(self, value):
        super().value(round(value, 2))


class LevelSensorEntity(BaseSensor):
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT


class InfoSensor(BaseSensor):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

class AmpSensorEntity(BaseSensor):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_value = 0

class TempSensorEntity(BaseSensor):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_value = 0