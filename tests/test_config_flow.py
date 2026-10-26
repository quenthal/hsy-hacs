"""Tests for the HSY config flow."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.hsy.const import DOMAIN

from .conftest import REPORT_DATA, SUBMIT_DATA, URLS, mock_report


@pytest.fixture(autouse=True)
def no_setup():
    """Do not set up the entry after the flow."""
    with patch("custom_components.hsy.async_setup_entry", return_value=True):
        yield


async def test_full_flow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Service numbers, then submission settings with prefilled numbers."""
    mock_report(aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], REPORT_DATA
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "submit"
    suggested = {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description
    }
    assert suggested["meter_number"] == SUBMIT_DATA["meter_number"]
    assert suggested["customer_number"] == SUBMIT_DATA["customer_number"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], SUBMIT_DATA
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {**REPORT_DATA, **SUBMIT_DATA}


async def test_skip_submit(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Leaving submission empty creates a report-only entry."""
    mock_report(aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=REPORT_DATA
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == REPORT_DATA


async def test_incomplete_submit(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Partially filled submission settings are rejected."""
    mock_report(aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=REPORT_DATA
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": "x"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "incomplete_submit"}


async def test_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Connection errors are shown."""
    aioclient_mock.get(URLS["description"], exc=TimeoutError())
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=REPORT_DATA
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_invalid_numbers(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Empty eRaportti data means wrong service numbers."""
    mock_report(aioclient_mock, description={"queryParameters": {}})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=REPORT_DATA
    )
    assert result["errors"] == {"base": "invalid_service_numbers"}


async def test_already_configured(
    hass: HomeAssistant, report_entry: MockConfigEntry
) -> None:
    """The same service numbers cannot be added twice."""
    report_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=REPORT_DATA
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure(hass: HomeAssistant, submit_entry: MockConfigEntry) -> None:
    """Submission settings can be cleared."""
    submit_entry.add_to_hass(hass)
    result = await submit_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert submit_entry.data["api_key"] == ""
    assert (
        submit_entry.data["water_service_number"] == REPORT_DATA["water_service_number"]
    )


async def test_options(hass: HomeAssistant, report_entry: MockConfigEntry) -> None:
    """Options are validated and stored as numbers."""
    report_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(report_entry.entry_id)
    options = {
        "update_interval_hours": 12,
        "auto_submit": True,
        "auto_submit_days": ["2", "1"],
        "auto_submit_hour_start": 20,
        "auto_submit_hour_end": 10,
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], options
    )
    assert result["errors"] == {"base": "invalid_hours"}
    options["auto_submit_hour_end"] = 22
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], options
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert report_entry.options["auto_submit_days"] == [1, 2]
    assert report_entry.options["update_interval_hours"] == 12
