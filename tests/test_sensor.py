"""Tests for HSY entities."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from .conftest import URLS, mock_report


def _entity_id(
    hass: HomeAssistant, entry: MockConfigEntry, key: str, domain: str
) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        domain, "hsy", f"{entry.entry_id}_{key}"
    )
    assert entity_id, key
    return entity_id


async def test_report_sensors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    report_entry: MockConfigEntry,
) -> None:
    """Sensors are created from eRaportti data; no submission entities."""
    await hass.config.async_set_time_zone("Europe/Helsinki")
    mock_report(aioclient_mock)
    report_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(report_entry.entry_id)
    await hass.async_block_till_done()
    assert report_entry.state is ConfigEntryState.LOADED

    def state(key: str, domain: str = "sensor"):
        return hass.states.get(_entity_id(hass, report_entry, key, domain))

    assert state("meter_reading").state == "1234"
    assert state("meter_reading").attributes["unit_of_measurement"] == "m³"
    assert state("water_costs").state == "352.0"
    assert state("water_usage").attributes["history"] == {"2025": 95, "2026*": 80}
    assert (
        state("bio_next_collection").state == "2026-10-30T10:00:00+00:00"
    )  # EET, 12:00 local
    assert state("bio_next_collection").attributes["interval"] == "joka 2. vko"
    assert state("mixed_collected").state == "250.0"
    assert state("bio_costs").attributes["history"] == {"2025": 90, "2026": 75}
    assert state("meter_read_on").state == "2026-10-01T09:00:00+00:00"

    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id(
            "number", "hsy", f"{report_entry.entry_id}_reading_input"
        )
        is None
    )

    assert await hass.config_entries.async_unload(report_entry.entry_id)


async def test_setup_retry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    report_entry: MockConfigEntry,
) -> None:
    """Setup is retried when eRaportti is unreachable."""
    aioclient_mock.get(URLS["description"], exc=TimeoutError())
    report_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(report_entry.entry_id)
    assert report_entry.state is ConfigEntryState.SETUP_RETRY


async def test_submit_entities(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    submit_entry: MockConfigEntry,
) -> None:
    """Submission entities exist and the reading input is stored."""
    mock_report(aioclient_mock)
    submit_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(submit_entry.entry_id)
    await hass.async_block_till_done()

    number = _entity_id(hass, submit_entry, "reading_input", "number")
    await hass.services.async_call(
        "number", "set_value", {"entity_id": number, "value": 1250}, blocking=True
    )
    assert hass.states.get(number).state == "1250"
    assert submit_entry.runtime_data.submit.reading_input == 1250
    assert (
        hass.states.get(
            _entity_id(hass, submit_entry, "reported_this_month", "binary_sensor")
        ).state
        == "off"
    )
    assert (
        hass.states.get(
            _entity_id(hass, submit_entry, "last_submit_result", "sensor")
        ).state
        == "unknown"
    )
