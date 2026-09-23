"""Read the station history and store it in Home Assistant statistics."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
import time

from homeassistant.components.persistent_notification import async_create
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models.statistics import StatisticMeanType
from homeassistant.components.recorder.statistics import (
    async_import_statistics,
    get_last_statistics,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from kloggpro.klimalogg import SensorLimits, get_datum_diff

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

LOOKBACK = timedelta(days=7)
STALL_SECONDS = 180
POLL_SECONDS = 5
MAX_READ_SECONDS = 30 * 60
_RECORDER = "recorder"


def _message(hass: HomeAssistant, french: str, english: str) -> str:
    if (hass.config.language or "").startswith("fr"):
        return french
    return english


def _notify(hass: HomeAssistant, message: str) -> None:
    async_create(
        hass,
        message,
        title="KlimaLogg Pro",
        notification_id="klimaloggpro_history",
    )


def _hour_start(timestamp: int) -> datetime:
    moment = datetime.fromtimestamp(timestamp, timezone.utc)
    return moment.replace(minute=0, second=0, microsecond=0)


def _as_utc(value) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    return None


def _configured_channels(hass: HomeAssistant) -> list[tuple[str, str]]:
    """Return (kind, channel) pairs enabled in the config entries."""
    channels = []
    for entry_id, data in hass.data.get(DOMAIN, {}).items():
        if entry_id in ("kldr", "history_import", "history_cancel"):
            continue
        if not isinstance(data, dict):
            continue
        for number in range(9):
            channel = str(number)
            if data.get(f"sensor_{number}temp"):
                channels.append(("temp", channel))
            if data.get(f"sensor_{number}humid"):
                channels.append(("humid", channel))
    return channels


def _entity_id(hass: HomeAssistant, unique_id: str) -> str | None:
    registry = er.async_get(hass)
    return registry.async_get_entity_id("sensor", DOMAIN, unique_id)


def _history_entity_ids(hass: HomeAssistant) -> dict[tuple[str, str], str]:
    found = {}
    kldr = hass.data.get(DOMAIN, {}).get("kldr")
    if kldr is None or kldr._service is None:
        return found
    device_key = kldr.get_transceiver_id()
    for kind, channel in _configured_channels(hass):
        suffix = "temp" if kind == "temp" else "humidity"
        entity_id = _entity_id(hass, f"{device_key}_{suffix}{channel}")
        if entity_id:
            found[(kind, channel)] = entity_id
    return found


def _device_entity_ids(hass: HomeAssistant, device_key) -> list[str]:
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, device_key)})
    if device is None:
        return []
    return [
        entry.entity_id
        for entry in er.async_get(hass).async_entries_for_device(device.id)
        if entry.domain in ("sensor", "binary_sensor")
    ]


async def _last_statistic_start(hass: HomeAssistant, entity_id: str) -> datetime | None:
    def _read():
        return get_last_statistics(hass, 1, entity_id, True, {"mean"})

    rows = await get_instance(hass).async_add_executor_job(_read)
    stats = (rows or {}).get(entity_id) or []
    if not stats:
        return None
    return _as_utc(stats[0].get("start"))


async def _collect_records(hass: HomeAssistant, kldr, since_ts: int) -> list[dict]:
    """Ask the station for history records newer than since_ts."""
    collected = []
    deadline = time.monotonic() + MAX_READ_SECONDS
    while time.monotonic() < deadline and not hass.data[DOMAIN].get("history_cancel"):
        kldr.start_caching_history(since_ts=since_ts)
        last_count = -1
        last_change = time.monotonic()
        remaining = None
        count = 0
        while time.monotonic() < deadline and not hass.data[DOMAIN].get("history_cancel"):
            await asyncio.sleep(POLL_SECONDS)
            count = kldr.get_cached_history_count() or 0
            remaining = kldr.get_uncached_history_count()
            if count != last_count:
                last_count = count
                last_change = time.monotonic()
                _LOGGER.info(
                    "History read: %s records cached, %s still on the station",
                    count,
                    remaining,
                )
            if remaining == 0 and count > 0:
                break
            if count >= kldr.batch_size:
                break
            if time.monotonic() - last_change >= STALL_SECONDS:
                break
        kldr.stop_caching_history()
        batch = list(kldr.get_history_cache_records() or [])
        kldr.clear_history_cache()
        if not batch:
            break
        collected.extend(batch)
        last_dt = batch[-1].get("dateTime")
        if count < kldr.batch_size or remaining in (0, None) or last_dt is None:
            break
        since_ts = int(last_dt) + 1
    return collected


def _measurement(kind: str, value):
    if kind == "temp":
        return get_datum_diff(
            value, SensorLimits.temperature_NP, SensorLimits.temperature_OFL
        )
    return get_datum_diff(value, SensorLimits.humidity_NP, SensorLimits.humidity_OFL)


def _hourly_statistics(records, kind: str, channel: str, cutoff: datetime | None):
    buckets: dict[datetime, list[float]] = {}
    current_hour = _hour_start(int(time.time()))
    field = f"Temp{channel}" if kind == "temp" else f"Humidity{channel}"
    for record in records:
        timestamp = record.get("dateTime")
        if not isinstance(timestamp, (int, float)):
            continue
        value = _measurement(kind, record.get(field))
        if value is None:
            continue
        hour = _hour_start(int(timestamp))
        if hour >= current_hour:
            continue
        if cutoff is not None and hour <= cutoff:
            continue
        buckets.setdefault(hour, []).append(float(value))
    return [
        {
            "start": hour,
            "mean": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
        }
        for hour, values in sorted(buckets.items())
    ]


async def async_reread_history(hass: HomeAssistant) -> None:
    """Read the station logger and import hourly statistics."""
    if hass.data[DOMAIN].get("history_import_running"):
        _notify(
            hass,
            _message(
                hass,
                "Une lecture de l'historique est déjà en cours.",
                "A history read is already running.",
            ),
        )
        return

    kldr = hass.data.get(DOMAIN, {}).get("kldr")
    if kldr is None or kldr._service is None:
        _notify(
            hass,
            _message(
                hass,
                "Le dongle USB n'est pas ouvert.",
                "The USB dongle is not open.",
            ),
        )
        return

    entities = _history_entity_ids(hass)
    if not entities:
        _notify(
            hass,
            _message(
                hass,
                "Aucun capteur de température ou d'humidité n'est configuré.",
                "No temperature or humidity sensor is configured.",
            ),
        )
        return

    hass.data[DOMAIN]["history_import_running"] = True
    hass.data[DOMAIN]["history_cancel"] = False
    try:
        cutoffs = {}
        oldest = None
        missing = False
        for entity_id in entities.values():
            last_start = await _last_statistic_start(hass, entity_id)
            cutoffs[entity_id] = last_start
            if last_start is None:
                missing = True
            elif oldest is None or last_start < oldest:
                oldest = last_start
        if missing or oldest is None:
            since_ts = int((datetime.now(timezone.utc) - LOOKBACK).timestamp())
        else:
            since_ts = int(oldest.timestamp())

        _notify(
            hass,
            _message(
                hass,
                "Lecture de l'historique de la station. Maintenez le bouton USB jusqu'à ce que « USB » reste affiché. Les mesures sont enregistrées par heure.",
                "Reading the station history. Hold the USB button until USB stays on the display. Readings are stored as hourly statistics.",
            ),
        )
        records = await _collect_records(hass, kldr, since_ts)
        if hass.data[DOMAIN].get("history_cancel"):
            return
        if not records:
            _notify(
                hass,
                _message(
                    hass,
                    "Aucune mesure lue. Maintenez le bouton USB de la station jusqu'à ce que « USB » reste affiché, puis relancez.",
                    "No records were read. Hold the station USB button until USB stays on the display, then try again.",
                ),
            )
            return
        imported = 0
        for (kind, channel), entity_id in entities.items():
            stats = _hourly_statistics(records, kind, channel, cutoffs.get(entity_id))
            if not stats:
                continue
            unit = UnitOfTemperature.CELSIUS if kind == "temp" else PERCENTAGE
            unit_class = "temperature" if kind == "temp" else None
            try:
                async_import_statistics(
                    hass,
                    {
                        "mean_type": StatisticMeanType.ARITHMETIC,
                        "has_sum": False,
                        "name": None,
                        "source": _RECORDER,
                        "statistic_id": entity_id,
                        "unit_class": unit_class,
                        "unit_of_measurement": unit,
                    },
                    stats,
                )
            except Exception:
                _LOGGER.exception("Could not import statistics for %s", entity_id)
                continue
            imported += len(stats)
        _notify(
            hass,
            _message(
                hass,
                f"{len(records)} mesures lues sur la station, {imported} statistiques horaires ajoutées. L'heure en cours reste alimentée par les capteurs en direct.",
                f"Read {len(records)} station records and added {imported} hourly statistics. The current hour still comes from the live sensors.",
            ),
        )
    except Exception:
        _LOGGER.exception("History import failed")
        _notify(
            hass,
            _message(
                hass,
                "La lecture de l'historique a échoué. Vérifiez que « USB » reste affiché sur la station.",
                "The history read failed. Check that USB stays on the station display.",
            ),
        )
    finally:
        hass.data[DOMAIN]["history_import_running"] = False
        if kldr._service is not None:
            kldr.stop_caching_history()


async def async_clear_history(hass: HomeAssistant, device_key) -> None:
    """Remove Home Assistant history for this station. The station memory stays."""
    hass.data[DOMAIN]["history_cancel"] = True
    task = hass.data[DOMAIN].get("history_import")
    if task is not None and not task.done():
        try:
            await asyncio.wait_for(asyncio.shield(task), 15)
        except (asyncio.TimeoutError, Exception):
            _LOGGER.debug("History read did not stop before the purge", exc_info=True)

    kldr = hass.data.get(DOMAIN, {}).get("kldr")
    if kldr is not None and kldr._service is not None:
        kldr.stop_caching_history()
        kldr.clear_history_cache()

    entity_ids = _device_entity_ids(hass, device_key)
    if not entity_ids:
        _notify(
            hass,
            _message(
                hass,
                "Aucun historique Home Assistant à vider.",
                "There is no Home Assistant history to clear.",
            ),
        )
        return

    await hass.services.async_call(
        _RECORDER,
        "purge_entities",
        {"entity_id": entity_ids, "keep_days": 0},
        blocking=True,
    )
    await hass.services.async_call(
        _RECORDER,
        "clear_statistics",
        {"statistic_ids": entity_ids},
        blocking=True,
    )
    _notify(
        hass,
        _message(
            hass,
            "L'historique Home Assistant de la station a été vidé. La mémoire de la station est inchangée : « Relire l'historique » peut la rapatrier.",
            "Home Assistant history for this station was cleared. The station memory is unchanged, so Reread history can import it again.",
        ),
    )
