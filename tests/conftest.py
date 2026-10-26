"""Fixtures for HSY tests. All data is invented."""

from __future__ import annotations

from collections.abc import Generator
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.hsy.const import (
    CONF_API_KEY,
    CONF_CONTRACT_NUMBER,
    CONF_CUSTOMER_NUMBER,
    CONF_METER_NUMBER,
    CONF_WASTE_SERVICE_NUMBER,
    CONF_WATER_SERVICE_NUMBER,
    DOMAIN,
    REPORT_BASE_URL,
    SUBMIT_URL,
)

WATER = "1234567"
WASTE = "XX000000001"
FIXTURES = Path(__file__).parent / "fixtures"

REPORT_DATA = {CONF_WATER_SERVICE_NUMBER: WATER, CONF_WASTE_SERVICE_NUMBER: WASTE}
SUBMIT_DATA = {
    CONF_API_KEY: "test-api-key",
    CONF_CUSTOMER_NUMBER: "1000001",
    CONF_CONTRACT_NUMBER: "300000003",
    CONF_METER_NUMBER: "40000004",
}

URLS = {
    "description": f"{REPORT_BASE_URL}/stats/description/both/{WASTE}/{WATER}/fi",
    "water_usage": f"{REPORT_BASE_URL}/stats/consumption/water/{WATER}/WATER_USAGE/fi",
    "water_costs": f"{REPORT_BASE_URL}/stats/consumption/water/{WATER}/WATER_COSTS/fi",
    "waste_collected": (
        f"{REPORT_BASE_URL}/stats/consumption/waste/{WASTE}/WASTE_COLLECTED/fi"
    ),
    "waste_costs": f"{REPORT_BASE_URL}/stats/consumption/waste/{WASTE}/WASTE_COSTS/fi",
}


def load_fixture(name: str) -> dict[str, Any]:
    """Load an API fixture."""
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def mock_report(aioclient_mock: AiohttpClientMocker, **overrides: Any) -> None:
    """Mock the eRaportti endpoints."""
    for key, url in URLS.items():
        aioclient_mock.get(url, json=overrides.get(key, load_fixture(key)))


def mock_submit(aioclient_mock: AiohttpClientMocker, **kwargs: Any) -> None:
    """Mock the reading submission endpoint."""
    aioclient_mock.post(SUBMIT_URL, **kwargs)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations."""


@pytest.fixture(autouse=True)
def no_retry_delay() -> Generator[None]:
    """Do not wait between submission retries."""
    with patch("custom_components.hsy.submit.SUBMIT_RETRY_DELAY") as delay:
        delay.total_seconds.return_value = 0
        yield


@pytest.fixture
def report_entry() -> MockConfigEntry:
    """Config entry without submission settings."""
    return MockConfigEntry(
        domain=DOMAIN, title="HSY", data=REPORT_DATA, unique_id=f"{WATER}_{WASTE}"
    )


@pytest.fixture
def submit_entry() -> MockConfigEntry:
    """Config entry with submission settings and automatic submission."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="HSY",
        data={**REPORT_DATA, **SUBMIT_DATA},
        options={"auto_submit": True},
        unique_id=f"{WATER}_{WASTE}",
    )
