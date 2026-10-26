"""Tests for the bundled brand images."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from custom_components.hsy.const import DOMAIN


async def test_has_branding(hass: HomeAssistant) -> None:
    """The integration ships its own brand images."""
    integration = await async_get_integration(hass, DOMAIN)
    assert integration.has_branding
