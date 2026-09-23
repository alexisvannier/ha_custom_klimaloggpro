"""The klimaloggpro integration."""
import asyncio
import logging
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP
)

from .const import DOMAIN

import kloggpro.klimalogg

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["sensor", "binary_sensor"]

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the klimaloggpro component."""
    hass.data.setdefault(DOMAIN, {}) 
                    # Needed to create the entry for this component inside the hass object, 
                    # without it, it is not possible to store data across this integration?
    return True


def _shutdown_driver_instance(kldr):
    """Release the USB interface. Safe to call more than once."""
    service = getattr(kldr, "_service", None)
    if service is None:
        return
    _LOGGER.info("KlimaLoggDriver will get shut down.")
    if service.child is not None:
        kldr.shutDown()
        return
    service.teardown()
    kldr._service = None


def _shutdown_driver(hass: HomeAssistant):
    """Release the USB interface stored on hass. Safe to call more than once."""
    kldr = hass.data.get(DOMAIN, {}).get("kldr")
    if kldr is None:
        return
    _shutdown_driver_instance(kldr)


async def async_restart_driver(hass: HomeAssistant):
    """Close the USB dongle and start pairing again on the same driver."""
    kldr = hass.data.get(DOMAIN, {}).get("kldr")
    if kldr is None:
        raise RuntimeError("KlimaLogg driver is not loaded")
    await hass.async_add_executor_job(_shutdown_driver_instance, kldr)
    try:
        kldr._startup_task = asyncio.get_running_loop().create_task(kldr.startUp())
        await kldr._startup_task
        kldr.clear_wait_at_start()
    except Exception:
        await hass.async_add_executor_job(_shutdown_driver_instance, kldr)
        raise
    _LOGGER.info("USB transceiver reopened, push 'USB' on the station")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up klimaloggpro from a config entry."""
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # KlimaLoggDriver schedules its startup task on the running loop.
    kldr = kloggpro.klimalogg.KlimaLoggDriver()
    await kldr._startup_task
    kldr.clear_wait_at_start()
    hass.data[DOMAIN]["kldr"] = kldr
    _LOGGER.info("Driver set up and started, push 'USB' Button on Logger now!")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _async_shutdown(_event):
        await hass.async_add_executor_job(_shutdown_driver, hass)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_shutdown)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    await hass.async_add_executor_job(_shutdown_driver, hass)
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        ),
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        hass.data[DOMAIN].pop("kldr", None)

    return unload_ok
