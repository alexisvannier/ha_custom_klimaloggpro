"""Platform for sensor integration."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature

from kloggpro.klimalogg import SensorLimits

from .const import DOMAIN

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
    new_devices = []
    for sensor in sensorlist_temp:
        new_devices.append(TemperatureSensor(kldr, sensor))
    for sensor in sensorlist_humid:
        new_devices.append(HumiditySensor(kldr, sensor))
    if new_devices:
        async_add_entities(new_devices)


class SensorBase(SensorEntity):
    """Base representation of KlimaLoggPro sensors."""

    _attr_should_poll = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, kldr, sensor):
        """Initialize sensor."""
        self._kldr = kldr
        self._sensornum = sensor

    @property
    def device_info(self):
        """Return information to link this entity with the correct device."""
        return {
            "identifiers": {(DOMAIN, self._kldr.get_transceiver_id())},
            "manufacturer": "TFA",
            "name": "KlimaLogg Pro",
        }

    @property
    def available(self) -> bool:
        """Return True if the USB transceiver is open."""
        return (
            self._kldr._service is not None
            and self._kldr.transceiver_is_present()
        )

    def _current_values(self):
        if self._kldr._service is None:
            return {}
        return self._kldr._service.current.values

    def _battery_status(self):
        alarm = self._current_values().get("AlarmData")
        if not alarm:
            return None
        if self._sensornum == "0":
            low = alarm[1] & 0x80
        else:
            low = alarm[0] & (1 << (int(self._sensornum) - 1))
        return "Low" if low else "OK"

    def _sensor_name(self):
        if self._sensornum == "0":
            return "Indoor"
        text = self._kldr._service.station_config.values.get(
            f"SensorText{self._sensornum}", ""
        )
        return text.capitalize() or f"Channel {self._sensornum}"


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
        """Return the state attributes of the device."""
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
        if "SignalQuality" in values:
            attr["signal_strength"] = values["SignalQuality"]
        battery = self._battery_status()
        if battery is not None:
            attr["battery_status"] = battery
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
        return f"{self._sensor_name()} Temperature {self._sensornum}"


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
        """Return the state attributes of the device."""
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
        if "SignalQuality" in values:
            attr["signal_strength"] = values["SignalQuality"]
        battery = self._battery_status()
        if battery is not None:
            attr["battery_status"] = battery
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
        return f"{self._sensor_name()} Humidity {self._sensornum}"
