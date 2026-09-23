"""Shared KlimaLogg entity helpers."""

from homeassistant.helpers.entity import Entity

from .const import DOMAIN


def enabled_channels(data):
    """Return channel numbers that have temperature or humidity enabled."""
    channels = []
    for sensor in range(9):
        if data.get(f"sensor_{sensor}temp", False) or data.get(
            f"sensor_{sensor}humid", False
        ):
            channels.append(f"{sensor}")
    return channels


class KlimaLoggEntity(Entity):
    """Base for entities that read the KlimaLogg driver."""

    _attr_should_poll = True

    def __init__(self, kldr, sensor=None):
        """Initialize the entity."""
        self._kldr = kldr
        self._sensornum = sensor

    @property
    def device_info(self):
        """Link this entity to the KlimaLogg console."""
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

    def battery_is_low(self):
        """Return True when the channel battery is low, or None if unknown."""
        alarm = self._current_values().get("AlarmData")
        if not alarm or self._sensornum is None:
            return None
        if self._sensornum == "0":
            return bool(alarm[1] & 0x80)
        return bool(alarm[0] & (1 << (int(self._sensornum) - 1)))

    def sensor_name(self):
        """Return the console name for this channel."""
        if self._sensornum == "0":
            return "Indoor"
        text = self._kldr._service.station_config.values.get(
            f"SensorText{self._sensornum}", ""
        )
        return text.capitalize() or f"Channel {self._sensornum}"
