"""Number entity for the meter reading to submit."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfVolume
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
    """Set up the reading input."""
    if submit := entry.runtime_data.submit:
        async_add_entities([HSYReadingInput(submit)])


class HSYReadingInput(HSYSubmitEntity, NumberEntity):
    """Meter reading that the automatic submission sends."""

    _attr_translation_key = "reading_input"
    _attr_native_min_value = 0
    _attr_native_max_value = 999999
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS

    def __init__(self, manager: HSYSubmitManager) -> None:
        """Initialize the number."""
        super().__init__(manager, "reading_input")

    @property
    def native_value(self) -> float:
        """Return the stored reading."""
        return self.manager.reading_input

    async def async_set_native_value(self, value: float) -> None:
        """Store a new reading."""
        await self.manager.async_set_reading_input(int(value))
