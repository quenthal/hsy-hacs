"""Client for the HSY eRaportti and meter reading APIs."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime
import logging
from typing import Any

import aiohttp

from .const import (
    REPORT_BASE_URL,
    REPORT_LANGUAGE,
    REQUEST_TIMEOUT,
    SUBMIT_URL,
    WASTE_FRACTIONS,
)

_LOGGER = logging.getLogger(__name__)

_HEADERS = {"Accept": "application/json", "User-Agent": "home-assistant-hsy"}
_SUBMITTER = "Home Assistant HSY integration"


class HSYError(Exception):
    """Base error."""


class HSYConnectionError(HSYError):
    """Network error or timeout."""


class HSYApiError(HSYError):
    """Unexpected response from HSY."""


class HSYNoDataError(HSYError):
    """The service numbers returned no water meter or waste containers."""


@dataclass
class WasteFraction:
    """One waste fraction (container type) of the collection point."""

    key: str
    name: str
    next_collection: date | None = None
    interval: str | None = None
    container_size: str | None = None
    collected: float | None = None
    costs: float | None = None


@dataclass
class HSYData:
    """Parsed eRaportti data."""

    meter_reading: int | None = None
    meter_number: str | None = None
    meter_model: str | None = None
    meter_read_on: date | None = None
    meter_installed_on: date | None = None
    customer_number: str | None = None
    contract_number: str | None = None
    water_usage: float | None = None
    water_usage_history: dict[str, float | None] = field(default_factory=dict)
    water_costs: float | None = None
    water_costs_history: dict[str, float | None] = field(default_factory=dict)
    last_reported_reading: int | None = None
    reported_readings: dict[str, float | None] = field(default_factory=dict)
    waste_collected: float | None = None
    waste_collected_history: dict[str, float | None] = field(default_factory=dict)
    waste_costs: float | None = None
    waste_costs_history: dict[str, float | None] = field(default_factory=dict)
    fractions: dict[str, WasteFraction] = field(default_factory=dict)
    updated_at: datetime | None = None


@dataclass
class SubmitResult:
    """Outcome of a reading submission that HSY answered."""

    success: bool
    message: str | None = None


def to_number(value: Any) -> float | None:
    """Parse '123', '123,5' or '123 m³' to a number."""
    try:
        return float(str(value).split()[0].replace(",", "."))
    except (ValueError, IndexError, AttributeError):
        return None


def to_int(value: Any) -> int | None:
    """Parse a meter reading to an integer."""
    number = to_number(value)
    return None if number is None else int(number)


def parse_fi_date(value: Any) -> date | None:
    """Parse Finnish dates '10.08.2025' and '04.06.26'."""
    if not isinstance(value, str):
        return None
    for fmt in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_created(value: Any) -> datetime | None:
    """Parse eRaportti 'created', e.g. '2026-05-30 13:43:58 +0300'."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S %z")
    except ValueError:
        return None


def fraction_key(name: str) -> str:
    """Return a stable key for a waste fraction name."""
    if name in WASTE_FRACTIONS:
        return WASTE_FRACTIONS[name]
    key = "".join(c if c.isalnum() else "_" for c in name.lower())
    return key.translate(str.maketrans("äöå", "aoa")).strip("_")


def _first_dataset(payload: dict[str, Any]) -> dict[str, Any] | None:
    datas = payload.get("datas") or []
    return datas[0] if datas else None


def _history(dataset: dict[str, Any]) -> dict[str, float | None]:
    return {
        str(row.get("dataset")): to_number(row.get("totalValue"))
        for row in dataset.get("data") or []
    }


def _latest(dataset: dict[str, Any] | None) -> dict[str, Any] | None:
    if not dataset or not dataset.get("data"):
        return None
    return dataset["data"][-1]


def parse_report(
    description: dict[str, Any],
    water_usage: dict[str, Any],
    water_costs: dict[str, Any],
    waste_collected: dict[str, Any],
    waste_costs: dict[str, Any],
) -> HSYData:
    """Combine the five eRaportti responses into HSYData."""
    data = HSYData()

    water = description.get("waterCustomerDetails") or {}
    data.customer_number = water.get("customerNumber")
    data.contract_number = water.get("waterContractNumber")
    meters = water.get("waterMeters") or []
    if meters:
        meter = meters[0]
        data.meter_reading = to_int(meter.get("lastReading"))
        data.meter_number = meter.get("meternumber")
        data.meter_model = meter.get("model")
        data.meter_read_on = parse_fi_date(meter.get("lastReadingDate"))
        data.meter_installed_on = parse_fi_date(meter.get("installDate"))

    waste = description.get("wasteCustomerDetails") or {}
    points = waste.get("collectionPoints") or []
    for point in points:
        for container in point.get("containers") or []:
            name = container.get("wasteType")
            if not name:
                continue
            key = fraction_key(name)
            data.fractions.setdefault(
                key,
                WasteFraction(
                    key=key,
                    name=name,
                    next_collection=parse_fi_date(container.get("nextCollectionDate")),
                    interval=container.get("collectionInterval"),
                    container_size=container.get("containerSize"),
                ),
            )

    if not meters and not data.fractions:
        raise HSYNoDataError

    if dataset := _first_dataset(water_usage):
        if latest := _latest(dataset):
            data.water_usage = to_number(latest.get("totalValue"))
        data.water_usage_history = _history(dataset)
    datas = water_usage.get("datas") or []
    readings = next((d for d in datas if d.get("type") == "WATER_METER_READINGS"), None)
    if readings and readings.get("data"):
        group = next(
            (
                g
                for g in readings["data"][0].get("dataGroups") or []
                if g.get("type") == "WATER_USAGE_READINGS"
            ),
            None,
        )
        if group and group.get("values"):
            data.reported_readings = {
                str(v.get("label")): to_number(v.get("value")) for v in group["values"]
            }
            data.last_reported_reading = to_int(group["values"][-1].get("value"))

    if dataset := _first_dataset(water_costs):
        if latest := _latest(dataset):
            data.water_costs = to_number(latest.get("totalValue"))
        data.water_costs_history = _history(dataset)

    for payload, attr in ((waste_collected, "collected"), (waste_costs, "costs")):
        dataset = _first_dataset(payload)
        if not dataset:
            continue
        latest = _latest(dataset)
        setattr(
            data,
            f"waste_{attr}",
            to_number(latest.get("totalValue")) if latest else None,
        )
        setattr(data, f"waste_{attr}_history", _history(dataset))
        groups = (latest or {}).get("dataGroups") or []
        for fraction in data.fractions.values():
            group = next((g for g in groups if g.get("label") == fraction.name), None)
            setattr(
                fraction,
                attr,
                to_number(group.get("totalValue")) if group else 0.0,
            )

    data.updated_at = parse_created(
        (description.get("queryParameters") or {}).get("created")
    )
    return data


class HSYApiClient:
    """Fetch eRaportti data and submit meter readings."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        water_service_number: str,
        waste_service_number: str,
    ) -> None:
        """Initialize the client."""
        self._session = session
        water = water_service_number.strip()
        waste = waste_service_number.strip()
        lang = REPORT_LANGUAGE
        base = REPORT_BASE_URL
        self._urls = {
            "description": f"{base}/stats/description/both/{waste}/{water}/{lang}",
            "water_usage": f"{base}/stats/consumption/water/{water}/WATER_USAGE/{lang}",
            "water_costs": f"{base}/stats/consumption/water/{water}/WATER_COSTS/{lang}",
            "waste_collected": (
                f"{base}/stats/consumption/waste/{waste}/WASTE_COLLECTED/{lang}"
            ),
            "waste_costs": f"{base}/stats/consumption/waste/{waste}/WASTE_COSTS/{lang}",
        }

    async def _get(self, key: str) -> dict[str, Any]:
        try:
            async with self._session.get(
                self._urls[key],
                headers=_HEADERS,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                if resp.status >= 400:
                    raise HSYApiError(f"{key}: HTTP {resp.status}")
                payload = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise HSYConnectionError(f"{key}: {type(err).__name__}") from err
        except ValueError as err:
            raise HSYApiError(f"{key}: invalid JSON") from err
        if not isinstance(payload, dict):
            raise HSYApiError(f"{key}: unexpected payload")
        return payload

    async def async_get_data(self) -> HSYData:
        """Fetch and parse all eRaportti data."""
        keys = list(self._urls)
        payloads = await asyncio.gather(*(self._get(key) for key in keys))
        try:
            return parse_report(**dict(zip(keys, payloads, strict=True)))
        except (KeyError, IndexError, TypeError, AttributeError) as err:
            raise HSYApiError(f"unexpected data: {type(err).__name__}") from err

    async def async_submit_reading(
        self,
        *,
        api_key: str,
        customer_number: str,
        contract_number: str,
        meter_number: str,
        reading: int,
        reading_date: date,
        dry_run: bool = False,
    ) -> SubmitResult:
        """Submit one meter reading. Raises HSYConnectionError/HSYApiError."""
        payload = {
            "id": f"ha-hsy-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "apiKey": api_key,
            "customerNumber": str(customer_number),
            "contractNumber": str(contract_number),
            "readingDate": reading_date.strftime("%d.%m.%Y"),
            "submitterInformation": _SUBMITTER,
            "dryRun": dry_run,
            "readingList": [
                {"meterNumber": str(meter_number), "reading": str(reading)}
            ],
        }
        try:
            async with self._session.post(
                SUBMIT_URL,
                json=payload,
                headers={"Content-Type": "application/json;charset=UTF-8"},
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                result = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise HSYConnectionError(type(err).__name__) from err
        except ValueError as err:
            raise HSYApiError("invalid JSON") from err
        if not isinstance(result, dict):
            raise HSYApiError("unexpected payload")
        if result.get("success"):
            return SubmitResult(success=True)
        errors = result.get("errorList")
        return SubmitResult(
            success=False,
            message=result.get("message") or (str(errors) if errors else None),
        )
