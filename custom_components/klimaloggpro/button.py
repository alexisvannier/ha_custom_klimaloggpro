"""Buttons that read or clear KlimaLogg history."""

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .entity import KlimaLoggEntity
from .history import async_clear_history, async_reread_history


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add history buttons on the KlimaLogg device."""
    kldr = hass.data[DOMAIN]["kldr"]
    async_add_entities(
        [
            RereadHistoryButton(kldr),
            ClearHistoryButton(kldr),
        ]
    )


class _HistoryButton(KlimaLoggEntity, ButtonEntity):
    """A configuration button stored on the KlimaLogg device."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True

    def __init__(self, kldr):
        super().__init__(kldr)
        self._device_id = kldr.get_transceiver_id()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "manufacturer": "TFA",
            "name": "KlimaLogg Pro",
        }


class RereadHistoryButton(_HistoryButton):
    """Read the station logger and fill Home Assistant statistics."""

    _attr_translation_key = "reread_history"

    @property
    def unique_id(self):
        return f"{self._device_id}_reread_history"

    async def async_press(self) -> None:
        task = self.hass.async_create_task(async_reread_history(self.hass))
        self.hass.data[DOMAIN]["history_import"] = task


class ClearHistoryButton(_HistoryButton):
    """Delete Home Assistant history for this station."""

    _attr_translation_key = "clear_history"

    @property
    def available(self) -> bool:
        return True

    @property
    def unique_id(self):
        return f"{self._device_id}_clear_history"

    async def async_press(self) -> None:
        await async_clear_history(self.hass, self._device_id)
