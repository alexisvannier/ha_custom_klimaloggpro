"""Platform for sensor integration."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.helpers.entity import EntityCategory

from kloggpro.klimalogg import SensorLimits

from .const import DOMAIN
from .entity import KlimaLoggEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add sensors for passed config_entry in HA."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    kldr = hass.data[DOMAIN]["kldr"]
    sensorlist_temp = []
    sensorlist_humid = []
    for sensor in range(9):
        if data.get(f"sensor_{sensor}temp", False):
            sensorlist_temp.append(f"{sensor}")
        if data.get(f"sensor_{sensor}humid", False):
            sensorlist_humid.append(f"{sensor}")

    _LOGGER.info(
        "Temp. sensor %s and Humid. sensor %s to configure",
        sensorlist_temp,
        sensorlist_humid,
    )
    new_devices = [SignalStrengthSensor(kldr)]
    for sensor in sensorlist_temp:
        new_devices.append(TemperatureSensor(kldr, sensor))
    for sensor in sensorlist_humid:
        new_devices.append(HumiditySensor(kldr, sensor))
    async_add_entities(new_devices)


class SensorBase(KlimaLoggEntity, SensorEntity):
    """Base representation of KlimaLoggPro sensors."""

    _attr_state_class = SensorStateClass.MEASUREMENT


class TemperatureSensor(SensorBase):
    """Temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    @property
    def unique_id(self):
        """Return Unique ID string."""
        return f"{self._kldr.get_transceiver_id()}_temp{self._sensornum}"

    @property
    def extra_state_attributes(self):
        """Return min/max readings for this channel."""
        values = self._current_values()
        number = self._sensornum
        attr = {}
        if f"Temp{number}Max" in values:
            attr["max_temp"] = values[f"Temp{number}Max"]
        if f"Temp{number}Min" in values:
            attr["min_temp"] = values[f"Temp{number}Min"]
        if f"Temp{number}MaxDT" in values:
            attr["max_temp_dt"] = values[f"Temp{number}MaxDT"]
        if f"Temp{number}MinDT" in values:
            attr["min_temp_dt"] = values[f"Temp{number}MinDT"]
        return attr

    @property
    def native_value(self):
        """Return the temperature in °C, or None when the sensor is absent."""
        value = self._current_values().get(f"Temp{self._sensornum}")
        if value in (None, SensorLimits.temperature_NP, SensorLimits.temperature_OFL):
            return None
        return value

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.sensor_name()} Temperature {self._sensornum}"


class HumiditySensor(SensorBase):
    """Humidity sensor."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 0

    @property
    def unique_id(self):
        """Return Unique ID string."""
        return f"{self._kldr.get_transceiver_id()}_humidity{self._sensornum}"

    @property
    def extra_state_attributes(self):
        """Return min/max readings for this channel."""
        values = self._current_values()
        number = self._sensornum
        attr = {}
        if f"Humidity{number}Max" in values:
            attr["max_humidity"] = values[f"Humidity{number}Max"]
        if f"Humidity{number}Min" in values:
            attr["min_humidity"] = values[f"Humidity{number}Min"]
        if f"Humidity{number}MaxDT" in values:
            attr["max_humidity_dt"] = values[f"Humidity{number}MaxDT"]
        if f"Humidity{number}MinDT" in values:
            attr["min_humidity_dt"] = values[f"Humidity{number}MinDT"]
        return attr

    @property
    def native_value(self):
        """Return the humidity in percent, or None when the sensor is absent."""
        value = self._current_values().get(f"Humidity{self._sensornum}")
        if value in (None, SensorLimits.humidity_NP, SensorLimits.humidity_OFL):
            return None
        return value

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.sensor_name()} Humidity {self._sensornum}"


class SignalStrengthSensor(SensorBase):
    """Link quality between the console and the USB transceiver."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 0

    @property
    def unique_id(self):
        """Return Unique ID string."""
        return f"{self._kldr.get_transceiver_id()}_signal"

    @property
    def native_value(self):
        """Return the link quality reported by the console."""
        return self._current_values().get("SignalQuality")

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Signal strength"
