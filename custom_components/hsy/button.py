"""Buttons for submitting the meter reading."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HSYConfigEntry
from .entity import HSYSubmitEntity
from .services import raise_for_status
from .submit import HSYSubmitManager

BUTTONS = (
    ButtonEntityDescription(key="submit", translation_key="submit"),
    ButtonEntityDescription(key="submit_dry_run", translation_key="submit_dry_run"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HSYConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the submission buttons."""
    if submit := entry.runtime_data.submit:
        async_add_entities(HSYSubmitButton(submit, d) for d in BUTTONS)


class HSYSubmitButton(HSYSubmitEntity, ButtonEntity):
    """Submit the reading now, for real or as a dry run."""

    def __init__(
        self, manager: HSYSubmitManager, description: ButtonEntityDescription
    ) -> None:
        """Initialize the button."""
        super().__init__(manager, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Submit the stored reading."""
        dry_run = self.entity_description.key == "submit_dry_run"
        status = await self.manager.async_submit(dry_run=dry_run)
        raise_for_status(self.manager, status)
