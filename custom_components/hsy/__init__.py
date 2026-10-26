"""The HSY integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HSYApiClient
from .const import CONF_WASTE_SERVICE_NUMBER, CONF_WATER_SERVICE_NUMBER, SUBMIT_KEYS
from .coordinator import HSYCoordinator
from .submit import HSYSubmitManager

PLATFORMS = [Platform.BINARY_SENSOR, Platform.NUMBER, Platform.SENSOR]


@dataclass
class HSYRuntimeData:
    """Runtime data of a config entry."""

    coordinator: HSYCoordinator
    submit: HSYSubmitManager | None


type HSYConfigEntry = ConfigEntry[HSYRuntimeData]


def has_submit_credentials(data: dict) -> bool:
    """Return True when all reading submission settings are present."""
    return all(data.get(key) for key in SUBMIT_KEYS)


async def async_setup_entry(hass: HomeAssistant, entry: HSYConfigEntry) -> bool:
    """Set up HSY from a config entry."""
    client = HSYApiClient(
        async_get_clientsession(hass),
        entry.data[CONF_WATER_SERVICE_NUMBER],
        entry.data[CONF_WASTE_SERVICE_NUMBER],
    )
    coordinator = HSYCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    submit = None
    if has_submit_credentials(entry.data):
        submit = HSYSubmitManager(hass, entry, client, coordinator)
        await submit.async_load()
        entry.async_on_unload(submit.async_start())

    entry.runtime_data = HSYRuntimeData(coordinator=coordinator, submit=submit)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HSYConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: HSYConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
