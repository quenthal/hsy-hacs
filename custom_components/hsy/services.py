"""Services for HSY."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DRY_RUN,
    ATTR_READING,
    DOMAIN,
    SERVICE_SUBMIT_READING,
)
from .submit import SUCCESS, SubmitStatus

if TYPE_CHECKING:
    from .submit import HSYSubmitManager

SUBMIT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(ATTR_READING): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional(ATTR_DRY_RUN, default=False): cv.boolean,
    }
)


def raise_for_status(manager: HSYSubmitManager, status: SubmitStatus) -> None:
    """Raise a translated error when a submission did not succeed."""
    if status in SUCCESS:
        return
    result = manager.last_result or {}
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key=f"submit_{status.value}",
        translation_placeholders={"message": result.get("message") or "-"},
    )


def _manager(hass: HomeAssistant, entry_id: str) -> HSYSubmitManager:
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="entry_not_found"
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="entry_not_loaded"
        )
    if (manager := entry.runtime_data.submit) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="submit_not_configured"
        )
    return manager


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the services."""

    async def _submit_reading(call: ServiceCall) -> ServiceResponse:
        manager = _manager(hass, call.data[ATTR_CONFIG_ENTRY_ID])
        status = await manager.async_submit(
            call.data.get(ATTR_READING), dry_run=call.data[ATTR_DRY_RUN]
        )
        raise_for_status(manager, status)
        result: dict[str, Any] = manager.last_result or {}
        return {
            "status": status.value,
            "reading": result.get("reading"),
            "dry_run": result.get("dry_run"),
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_SUBMIT_READING,
        _submit_reading,
        schema=SUBMIT_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
