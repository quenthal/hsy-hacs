"""Tests for reading submission and the automatic submission."""

from __future__ import annotations

from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.hsy.const import SUBMIT_URL
from custom_components.hsy.submit import HSYSubmitManager, SubmitStatus

from .conftest import mock_report, mock_submit


@pytest.fixture
async def manager(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    submit_entry: MockConfigEntry,
) -> HSYSubmitManager:
    """Set up the entry and return its submission manager."""
    mock_report(aioclient_mock)
    submit_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(submit_entry.entry_id)
    await hass.async_block_till_done()
    return submit_entry.runtime_data.submit


def _in_window(day: int = 2, hour: int = 10) -> datetime:
    now = dt_util.now()
    return now.replace(day=day, hour=hour, minute=0, second=0, microsecond=0)


def _submit_calls(aioclient_mock: AiohttpClientMocker) -> list:
    return [c for c in aioclient_mock.mock_calls if str(c[1]) == SUBMIT_URL]


async def test_submit_ok(
    manager: HSYSubmitManager, aioclient_mock: AiohttpClientMocker
) -> None:
    """A successful submission marks the month as reported."""
    mock_submit(aioclient_mock, json={"success": True})
    assert await manager.async_submit(1250) is SubmitStatus.OK
    assert manager.reported_this_month()
    assert manager.state["last_submitted_reading"] == 1250
    payload = _submit_calls(aioclient_mock)[0][2]
    assert payload["readingList"] == [{"meterNumber": "40000004", "reading": "1250"}]
    assert payload["dryRun"] is False


async def test_dry_run_does_not_report(
    manager: HSYSubmitManager, aioclient_mock: AiohttpClientMocker
) -> None:
    """A dry run does not mark the month."""
    mock_submit(aioclient_mock, json={"success": True})
    assert await manager.async_submit(1250, dry_run=True) is SubmitStatus.DRY_RUN_OK
    assert not manager.reported_this_month()


async def test_reading_guards(
    manager: HSYSubmitManager, aioclient_mock: AiohttpClientMocker
) -> None:
    """Missing or decreasing readings are not sent."""
    assert await manager.async_submit(0) is SubmitStatus.INVALID_READING
    assert await manager.async_submit(1200) is SubmitStatus.READING_DECREASED
    assert not _submit_calls(aioclient_mock)
    assert manager.last_result["message"] == "1200 < 1234"


async def test_guard_uses_stored_reading(
    manager: HSYSubmitManager, aioclient_mock: AiohttpClientMocker
) -> None:
    """The guard works without eRaportti data, e.g. right after a restart."""
    manager.coordinator.data = None
    manager.state["last_submitted_reading"] = 1300
    assert await manager.async_submit(1290) is SubmitStatus.READING_DECREASED
    assert not _submit_calls(aioclient_mock)


async def test_rejection_message(
    manager: HSYSubmitManager, aioclient_mock: AiohttpClientMocker
) -> None:
    """An empty error list does not produce 'None'."""
    mock_submit(aioclient_mock, json={"success": False, "errorList": None})
    assert await manager.async_submit(1250) is SubmitStatus.REJECTED
    assert manager.last_result["message"] is None


async def test_connection_errors_are_retried(
    manager: HSYSubmitManager, aioclient_mock: AiohttpClientMocker
) -> None:
    """Connection errors are retried three times."""
    mock_submit(aioclient_mock, exc=TimeoutError())
    assert await manager.async_submit(1250) is SubmitStatus.FAILED
    assert len(_submit_calls(aioclient_mock)) == 3


async def test_auto_submit_schedule(
    manager: HSYSubmitManager, aioclient_mock: AiohttpClientMocker
) -> None:
    """Automatic submission respects the window and sends once a month."""
    mock_submit(aioclient_mock, json={"success": True})
    assert await manager.async_auto_submit(_in_window()) is None  # no reading yet
    await manager.async_set_reading_input(1250)
    assert await manager.async_auto_submit(_in_window(day=10)) is None
    assert await manager.async_auto_submit(_in_window(hour=7)) is None
    assert await manager.async_auto_submit(_in_window(hour=23)) is None
    assert not _submit_calls(aioclient_mock)

    assert await manager.async_auto_submit(_in_window()) is SubmitStatus.OK
    assert manager.auto_last_attempt is not None
    assert await manager.async_auto_submit(_in_window(hour=11)) is None
    assert len(_submit_calls(aioclient_mock)) == 1


async def test_auto_rejection_blocks_same_reading(
    manager: HSYSubmitManager, aioclient_mock: AiohttpClientMocker
) -> None:
    """A refused reading is not retried every hour; a new reading is."""
    mock_submit(aioclient_mock, json={"success": False, "message": "refused"})
    await manager.async_set_reading_input(1250)
    assert await manager.async_auto_submit(_in_window()) is SubmitStatus.REJECTED
    assert await manager.async_auto_submit(_in_window(hour=11)) is None
    assert len(_submit_calls(aioclient_mock)) == 1

    await manager.async_set_reading_input(1251)
    assert await manager.async_auto_submit(_in_window(hour=12)) is SubmitStatus.REJECTED
    assert len(_submit_calls(aioclient_mock)) == 2


async def test_auto_failure_is_retried(
    manager: HSYSubmitManager, aioclient_mock: AiohttpClientMocker
) -> None:
    """Connection failures do not block the next hourly attempt."""
    mock_submit(aioclient_mock, exc=TimeoutError())
    await manager.async_set_reading_input(1250)
    assert await manager.async_auto_submit(_in_window()) is SubmitStatus.FAILED
    assert await manager.async_auto_submit(_in_window(hour=11)) is SubmitStatus.FAILED


async def test_auto_disabled(
    hass: HomeAssistant,
    manager: HSYSubmitManager,
    submit_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Nothing is sent when automatic submission is off."""
    hass.config_entries.async_update_entry(submit_entry, options={"auto_submit": False})
    await hass.async_block_till_done()
    manager = submit_entry.runtime_data.submit
    await manager.async_set_reading_input(1250)
    assert await manager.async_auto_submit(_in_window()) is None


async def test_state_survives_reload(
    hass: HomeAssistant,
    manager: HSYSubmitManager,
    submit_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Submission state is restored from storage."""
    mock_submit(aioclient_mock, json={"success": True})
    await manager.async_set_reading_input(1250)
    await manager.async_submit()
    assert await hass.config_entries.async_reload(submit_entry.entry_id)
    await hass.async_block_till_done()
    restored = submit_entry.runtime_data.submit
    assert restored is not manager
    assert restored.reading_input == 1250
    assert restored.reported_this_month()
