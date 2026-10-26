"""Binary sensors for HSY."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HSYConfigEntry
from .entity import HSYSubmitEntity
from .submit import HSYSubmitManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HSYConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up HSY binary sensors."""
    if submit := entry.runtime_data.submit:
        async_add_entities([HSYReportedThisMonth(submit)])


class HSYReportedThisMonth(HSYSubmitEntity, BinarySensorEntity):
    """On when a reading has been submitted this month."""

    _attr_translation_key = "reported_this_month"

    def __init__(self, manager: HSYSubmitManager) -> None:
        """Initialize the binary sensor."""
        super().__init__(manager, "reported_this_month")

    @property
    def is_on(self) -> bool:
        """Return the state."""
        return self.manager.reported_this_month()
