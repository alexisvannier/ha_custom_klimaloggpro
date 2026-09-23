"""Battery status for each configured KlimaLogg channel."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .entity import KlimaLoggEntity, enabled_channels


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add one battery binary sensor per configured channel."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    kldr = hass.data[DOMAIN]["kldr"]
    async_add_entities(
        BatteryBinarySensor(kldr, channel) for channel in enabled_channels(data)
    )


class BatteryBinarySensor(KlimaLoggEntity, BinarySensorEntity):
    """On when the channel battery is low."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self):
        """Return Unique ID string."""
        return f"{self._kldr.get_transceiver_id()}_battery{self._sensornum}"

    @property
    def is_on(self):
        """Return True when the battery is low."""
        return self.battery_is_low()

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.sensor_name()} Battery {self._sensornum}"
