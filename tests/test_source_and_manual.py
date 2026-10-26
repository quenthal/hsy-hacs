"""Tests for the reading source, the buttons and the submit service."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.hsy.const import DOMAIN, SUBMIT_URL

from .conftest import REPORT_DATA, SUBMIT_DATA, WASTE, WATER, mock_report, mock_submit

SOURCE = "sensor.watermeter_validated"


def _entity_id(
    hass: HomeAssistant, entry: MockConfigEntry, key: str, domain: str
) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        domain, DOMAIN, f"{entry.entry_id}_{key}"
    )
    assert entity_id, key
    return entity_id


def _submit_calls(aioclient_mock: AiohttpClientMocker) -> list:
    return [c for c in aioclient_mock.mock_calls if str(c[1]) == SUBMIT_URL]


@pytest.fixture
def source_entry() -> MockConfigEntry:
    """Entry whose reading follows a source sensor."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="HSY",
        data={**REPORT_DATA, **SUBMIT_DATA},
        options={"reading_source": SOURCE},
        unique_id=f"{WATER}_{WASTE}",
    )


async def _setup(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, entry: MockConfigEntry
) -> None:
    mock_report(aioclient_mock)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_reading_follows_source(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    source_entry: MockConfigEntry,
) -> None:
    """The input shows the source value as an integer and cannot be set."""
    hass.states.async_set(SOURCE, "1240.731")
    await _setup(hass, aioclient_mock, source_entry)
    number = _entity_id(hass, source_entry, "reading_input", "number")
    assert hass.states.get(number).state == "1240"

    hass.states.async_set(SOURCE, "1241,2")
    await hass.async_block_till_done()
    assert hass.states.get(number).state == "1241"

    for bad in ("unavailable", "unknown", "garbage", "0"):
        hass.states.async_set(SOURCE, bad)
        await hass.async_block_till_done()
        assert hass.states.get(number).state == "1241"

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "number", "set_value", {"entity_id": number, "value": 5}, blocking=True
        )


async def test_source_appearing_later(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    source_entry: MockConfigEntry,
) -> None:
    """A source created after setup (e.g. at startup) is picked up."""
    await _setup(hass, aioclient_mock, source_entry)
    hass.states.async_set(SOURCE, "1250.0")
    await hass.async_block_till_done()
    assert source_entry.runtime_data.submit.reading_input == 1250


async def test_buttons(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    submit_entry: MockConfigEntry,
) -> None:
    """Buttons submit the stored reading; failures raise."""
    await _setup(hass, aioclient_mock, submit_entry)
    manager = submit_entry.runtime_data.submit
    await manager.async_set_reading_input(1250)

    mock_submit(aioclient_mock, json={"success": True})
    dry = _entity_id(hass, submit_entry, "submit_dry_run", "button")
    await hass.services.async_call("button", "press", {"entity_id": dry}, blocking=True)
    assert _submit_calls(aioclient_mock)[-1][2]["dryRun"] is True
    assert not manager.reported_this_month()

    submit = _entity_id(hass, submit_entry, "submit", "button")
    await hass.services.async_call(
        "button", "press", {"entity_id": submit}, blocking=True
    )
    assert _submit_calls(aioclient_mock)[-1][2]["dryRun"] is False
    assert manager.reported_this_month()

    aioclient_mock.clear_requests()
    mock_report(aioclient_mock)
    mock_submit(aioclient_mock, json={"success": False, "message": "refused"})
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            "button", "press", {"entity_id": submit}, blocking=True
        )
    assert err.value.translation_key == "submit_rejected"


async def test_submit_service(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    submit_entry: MockConfigEntry,
) -> None:
    """The service submits a given reading and returns the result."""
    await _setup(hass, aioclient_mock, submit_entry)
    mock_submit(aioclient_mock, json={"success": True})
    response = await hass.services.async_call(
        DOMAIN,
        "submit_reading",
        {"config_entry_id": submit_entry.entry_id, "reading": 1260, "dry_run": True},
        blocking=True,
        return_response=True,
    )
    assert response == {"status": "dry_run_ok", "reading": 1260, "dry_run": True}
    assert _submit_calls(aioclient_mock)[-1][2]["readingList"][0]["reading"] == "1260"

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            "submit_reading",
            {"config_entry_id": submit_entry.entry_id, "reading": 1000},
            blocking=True,
        )
    assert err.value.translation_key == "submit_reading_decreased"


async def test_submit_service_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    report_entry: MockConfigEntry,
) -> None:
    """Unknown entries and entries without submission are refused."""
    await _setup(hass, aioclient_mock, report_entry)
    for entry_id, key in (
        ("missing", "entry_not_found"),
        (report_entry.entry_id, "submit_not_configured"),
    ):
        with pytest.raises(ServiceValidationError) as err:
            await hass.services.async_call(
                DOMAIN, "submit_reading", {"config_entry_id": entry_id}, blocking=True
            )
        assert err.value.translation_key == key
