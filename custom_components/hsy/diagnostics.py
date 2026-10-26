"""Diagnostics for HSY."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import HSYConfigEntry
from .const import (
    CONF_API_KEY,
    CONF_CONTRACT_NUMBER,
    CONF_CUSTOMER_NUMBER,
    CONF_METER_NUMBER,
    CONF_WASTE_SERVICE_NUMBER,
    CONF_WATER_SERVICE_NUMBER,
)

TO_REDACT = {
    CONF_API_KEY,
    CONF_CONTRACT_NUMBER,
    CONF_CUSTOMER_NUMBER,
    CONF_METER_NUMBER,
    CONF_WASTE_SERVICE_NUMBER,
    CONF_WATER_SERVICE_NUMBER,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HSYConfigEntry
) -> dict[str, Any]:
    """Return diagnostics with identifiers redacted."""
    runtime = entry.runtime_data
    data = runtime.coordinator.data
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "data": async_redact_data(asdict(data), TO_REDACT) if data else None,
        "submit_state": runtime.submit.state if runtime.submit else None,
    }
