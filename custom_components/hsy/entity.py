"""Base entities for HSY."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HSYConfigEntry
from .const import DOMAIN
from .coordinator import HSYCoordinator
from .submit import HSYSubmitManager


def device_info(entry: HSYConfigEntry) -> DeviceInfo:
    """Return the service device shared by all entities."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="HSY",
        manufacturer="HSY",
        model="eRaportti",
        entry_type=DeviceEntryType.SERVICE,
    )


class HSYEntity(CoordinatorEntity[HSYCoordinator]):
    """Entity backed by eRaportti data."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HSYCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = device_info(entry)


class HSYSubmitEntity(Entity):
    """Entity backed by the reading submission state."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: HSYSubmitManager, key: str) -> None:
        """Initialize the entity."""
        self.manager = manager
        self._attr_unique_id = f"{manager.entry.entry_id}_{key}"
        self._attr_device_info = device_info(manager.entry)

    async def async_added_to_hass(self) -> None:
        """Subscribe to submission state changes."""
        await super().async_added_to_hass()
        self.async_on_remove(self.manager.async_add_listener(self.async_write_ha_state))
