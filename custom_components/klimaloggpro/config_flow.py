"""Config flow for klimaloggpro integration."""
from datetime import datetime
import logging

import voluptuous as vol

from homeassistant import config_entries, core, exceptions

from . import async_restart_driver
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("name", default="Klimalogg"): str, 
        vol.Optional("sensor_0temp", default=True): bool, 
        vol.Optional("sensor_0humid", default=True): bool, 
        vol.Optional("sensor_1temp"): bool, 
        vol.Optional("sensor_1humid"): bool, 
        vol.Optional("sensor_2temp"): bool,
        vol.Optional("sensor_2humid"): bool,
        vol.Optional("sensor_3temp"): bool,
        vol.Optional("sensor_3humid"): bool,
        vol.Optional("sensor_4temp"): bool,
        vol.Optional("sensor_4humid"): bool,
        vol.Optional("sensor_5temp"): bool,
        vol.Optional("sensor_5humid"): bool,
        vol.Optional("sensor_6temp"): bool,
        vol.Optional("sensor_6humid"): bool,
        vol.Optional("sensor_7temp"): bool,
        vol.Optional("sensor_7humid"): bool,
        vol.Optional("sensor_8temp"): bool,
        vol.Optional("sensor_8humid"): bool,
    }
)

async def validate_input(hass: core.HomeAssistant, data: dict):
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # TODO validate the data can be used to set up a connection.

    # If your PyPI package is not built with async, pass your methods
    # to the executor:
    # await hass.async_add_executor_job(
    #     your_validate_func, data["username"], data["password"]
    # )

    # hub = PlaceholderHub(data["host"])

    #if not await hub.authenticate(data["username"], data["password"]):
    #    raise InvalidAuth
    if len(data["name"]) < 3:
        raise CannotConnect
    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth

    # Return info that you want to store in the config entry.
    return {"title": data["name"]}


def _status_placeholders(hass: core.HomeAssistant) -> dict[str, str]:
    """Describe the USB dongle for the configuration page."""
    unknown = "—"
    lang = (hass.config.language or "en")[:2]
    present_label = {"fr": "détecté", "de": "erkannt", "en": "detected"}
    absent_label = {"fr": "absent", "de": "nicht erkannt", "en": "not detected"}
    yes_label = {"fr": "oui", "de": "ja", "en": "yes"}
    no_label = {"fr": "non", "de": "nein", "en": "no"}

    def word(table: dict[str, str]) -> str:
        return table.get(lang, table["en"])

    kldr = hass.data.get(DOMAIN, {}).get("kldr")
    if kldr is None or kldr._service is None:
        return {
            "usb": word(absent_label),
            "paired": word(no_label),
            "serial": unknown,
            "device_id": unknown,
            "last_contact": unknown,
        }

    try:
        present = bool(kldr.transceiver_is_present())
    except Exception:  # pylint: disable=broad-except
        present = False
    try:
        paired = bool(kldr.transceiver_is_paired())
    except Exception:  # pylint: disable=broad-except
        paired = False
    try:
        serial = kldr.get_transceiver_serial() or unknown
    except Exception:  # pylint: disable=broad-except
        serial = unknown
    try:
        device_id = kldr.get_transceiver_id()
        device_id = f"{device_id:04X}" if isinstance(device_id, int) else unknown
    except Exception:  # pylint: disable=broad-except
        device_id = unknown
    try:
        last_seen = kldr.get_last_contact()
        last_contact = (
            datetime.fromtimestamp(last_seen).strftime("%Y-%m-%d %H:%M:%S")
            if last_seen
            else unknown
        )
    except Exception:  # pylint: disable=broad-except
        last_contact = unknown

    return {
        "usb": word(present_label) if present else word(absent_label),
        "paired": word(yes_label) if paired else word(no_label),
        "serial": str(serial),
        "device_id": str(device_id),
        "last_contact": last_contact,
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for klimaloggpro."""

    VERSION = 1

    @staticmethod
    @core.callback
    def async_get_options_flow(config_entry):
        """USB check and pairing restart on the integration configuration page."""
        return KlimaLoggOptionsFlow()

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=info["title"], data=user_input)
            # TODO Add some real-world Exceptions...?
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class KlimaLoggOptionsFlow(config_entries.OptionsFlow):
    """Show the USB dongle status and restart pairing."""

    async def async_step_init(self, user_input=None):
        """Show the current USB status and the restart action."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["restart_pairing"],
            description_placeholders=_status_placeholders(self.hass),
        )

    async def async_step_restart_pairing(self, user_input=None):
        """Reopen the USB dongle and start pairing again."""
        if user_input is not None:
            return await self.async_step_init()
        try:
            await async_restart_driver(self.hass)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("USB pairing restart failed")
            return self.async_show_form(
                step_id="restart_pairing",
                data_schema=vol.Schema({}),
                errors={"base": "cannot_connect"},
                description_placeholders=_status_placeholders(self.hass),
            )
        return self.async_abort(
            reason="pairing_restarted",
            description_placeholders=_status_placeholders(self.hass),
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
