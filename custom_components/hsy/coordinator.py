"""Data update coordinator for HSY."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HSYApiClient, HSYData, HSYError
from .const import CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL, DOMAIN

if TYPE_CHECKING:
    from . import HSYConfigEntry

_LOGGER = logging.getLogger(__name__)


class HSYCoordinator(DataUpdateCoordinator[HSYData]):
    """Poll eRaportti."""

    config_entry: HSYConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: HSYConfigEntry, client: HSYApiClient
    ) -> None:
        """Initialize the coordinator."""
        hours = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(hours=hours),
        )
        self.client = client

    async def _async_update_data(self) -> HSYData:
        try:
            return await self.client.async_get_data()
        except HSYError as err:
            raise UpdateFailed(f"Error fetching eRaportti: {err}") from err
