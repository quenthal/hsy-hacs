"""Tests for eRaportti parsing."""

from __future__ import annotations

from datetime import date

import pytest

from custom_components.hsy.api import (
    HSYNoDataError,
    fraction_key,
    parse_fi_date,
    parse_report,
    to_number,
)

from .conftest import URLS, load_fixture


def _report(**overrides):
    return parse_report(**{key: overrides.get(key, load_fixture(key)) for key in URLS})


def test_parse_report() -> None:
    """All fields are parsed from the fixtures."""
    data = _report()
    assert data.meter_reading == 1234
    assert data.meter_number == "40000004"
    assert data.meter_read_on == date(2026, 10, 1)
    assert data.meter_installed_on == date(2019, 3, 15)
    assert data.customer_number == "1000001"
    assert data.contract_number == "300000003"
    assert data.water_usage == 80
    assert data.water_usage_history == {"2025": 95, "2026*": 80}
    assert data.water_costs == 352
    assert data.water_costs_history["2025"] == 410.5
    assert data.last_reported_reading == 1234
    assert data.reported_readings["2026-09-01"] == 1212
    assert data.waste_collected == 350
    assert data.waste_costs == 285
    assert set(data.fractions) == {"mixed", "bio"}
    bio = data.fractions["bio"]
    assert bio.name == "Biojäte"
    assert bio.next_collection == date(2026, 10, 30)
    assert bio.interval == "joka 2. vko"
    assert bio.container_size == "140 l"
    assert bio.collected == 100
    assert bio.costs == 75
    assert data.updated_at is not None
    assert data.updated_at.isoformat() == "2026-10-20T06:15:00+03:00"


def test_parse_report_without_data() -> None:
    """Service numbers without meters or containers raise."""
    with pytest.raises(HSYNoDataError):
        _report(description={"queryParameters": {}})


def test_missing_fraction_in_statistics() -> None:
    """A fraction without statistics reports zero."""
    collected = load_fixture("waste_collected")
    for row in collected["datas"][0]["data"]:
        row["dataGroups"] = row["dataGroups"][:1]
    data = _report(waste_collected=collected)
    assert data.fractions["bio"].collected == 0
    assert data.fractions["mixed"].collected == 250


@pytest.mark.parametrize(
    ("value", "expected"),
    [("123", 123), ("123,5", 123.5), ("1234 m³", 1234), ("", None), (None, None)],
)
def test_to_number(value, expected) -> None:
    """Numbers are parsed leniently."""
    assert to_number(value) == expected


def test_helpers() -> None:
    """Dates and fraction keys."""
    assert parse_fi_date("04.06.26") == date(2026, 6, 4)
    assert parse_fi_date("04.06.2026") == date(2026, 6, 4)
    assert parse_fi_date("bad") is None
    assert fraction_key("Sekajäte") == "mixed"
    assert fraction_key("Pienmetalli ja lasi") == "pienmetalli_ja_lasi"
