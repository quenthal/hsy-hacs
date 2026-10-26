"""Meter reading submission and the monthly automatic submission."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .api import HSYApiClient, HSYApiError, HSYConnectionError
from .const import (
    CONF_API_KEY,
    CONF_AUTO_DAYS,
    CONF_AUTO_HOUR_END,
    CONF_AUTO_HOUR_START,
    CONF_AUTO_SUBMIT,
    CONF_CONTRACT_NUMBER,
    CONF_CUSTOMER_NUMBER,
    CONF_METER_NUMBER,
    DEFAULT_AUTO_DAYS,
    DEFAULT_AUTO_HOUR_END,
    DEFAULT_AUTO_HOUR_START,
    DEFAULT_AUTO_SUBMIT,
    DOMAIN,
    STORAGE_VERSION,
    SUBMIT_ATTEMPTS,
    SUBMIT_RETRY_DELAY,
)

if TYPE_CHECKING:
    from . import HSYConfigEntry
    from .coordinator import HSYCoordinator

_LOGGER = logging.getLogger(__name__)


class SubmitStatus(StrEnum):
    """Result of the latest submission attempt."""

    OK = "ok"
    DRY_RUN_OK = "dry_run_ok"
    REJECTED = "rejected"
    FAILED = "failed"
    INVALID_READING = "invalid_reading"
    READING_DECREASED = "reading_decreased"


# Statuses after which the same reading is not retried automatically.
_NOT_RETRYABLE = {
    SubmitStatus.REJECTED,
    SubmitStatus.INVALID_READING,
    SubmitStatus.READING_DECREASED,
}


def _month(now: datetime) -> str:
    return now.strftime("%Y-%m")


class HSYSubmitManager:
    """Keep the reading to submit and submit it to HSY."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: HSYConfigEntry,
        client: HSYApiClient,
        coordinator: HSYCoordinator,
    ) -> None:
        """Initialize the manager."""
        self.hass = hass
        self.entry = entry
        self.client = client
        self.coordinator = coordinator
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self.state: dict[str, Any] = {}
        self._listeners: list[CALLBACK_TYPE] = []
        self._lock = asyncio.Lock()

    # ---- persistence and listeners --------------------------------------

    async def async_load(self) -> None:
        """Load persisted state."""
        self.state = await self._store.async_load() or {}

    async def _async_save(self) -> None:
        await self._store.async_save(self.state)
        for listener in list(self._listeners):
            listener()

    @callback
    def async_add_listener(self, listener: CALLBACK_TYPE) -> Callable[[], None]:
        """Call listener when the state changes."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def async_start(self) -> Callable[[], None]:
        """Start the hourly automatic submission check."""
        unsub_time = async_track_time_change(
            self.hass, self._async_auto_tick, minute=0, second=0
        )
        unsub_coord = self.coordinator.async_add_listener(self._handle_coordinator)

        def _stop() -> None:
            unsub_time()
            unsub_coord()

        return _stop

    @callback
    def _handle_coordinator(self) -> None:
        reading = self.coordinator.data.meter_reading if self.coordinator.data else None
        if reading and reading != self.state.get("last_meter_reading"):
            self.state["last_meter_reading"] = reading
            self.hass.async_create_task(self._async_save())

    # ---- state accessors ------------------------------------------------

    @property
    def reading_input(self) -> int:
        """Return the reading that will be submitted."""
        return int(self.state.get("reading_input", 0))

    def reported_this_month(self, now: datetime | None = None) -> bool:
        """Return True when a reading has been submitted this month."""
        return self.state.get("last_submit_month") == _month(now or dt_util.now())

    @property
    def last_result(self) -> dict[str, Any] | None:
        """Return the latest submission result."""
        return self.state.get("last_result")

    def _timestamp(self, key: str) -> datetime | None:
        value = self.state.get(key)
        return dt_util.parse_datetime(value) if value else None

    @property
    def last_submitted_at(self) -> datetime | None:
        """Return when a reading was last submitted successfully."""
        return self._timestamp("last_submitted_at")

    @property
    def auto_last_attempt(self) -> datetime | None:
        """Return when the automatic submission last tried."""
        return self._timestamp("auto_last_attempt")

    async def async_set_reading_input(self, value: int) -> None:
        """Set the reading that will be submitted."""
        self.state["reading_input"] = int(value)
        await self._async_save()

    # ---- submission -------------------------------------------------------

    def _highest_known_reading(self) -> int:
        data = self.coordinator.data
        candidates = [
            self.state.get("last_meter_reading"),
            self.state.get("last_submitted_reading"),
        ]
        if data:
            candidates += [data.meter_reading, data.last_reported_reading]
        return max((int(c) for c in candidates if c), default=0)

    async def async_submit(
        self, reading: int | None = None, *, dry_run: bool = False
    ) -> SubmitStatus:
        """Validate and submit a reading; the stored input is used by default."""
        async with self._lock:
            status, message = await self._async_submit(
                reading if reading is not None else self.reading_input, dry_run
            )
            now = dt_util.now()
            self.state["last_result"] = {
                "status": status.value,
                "message": message,
                "reading": reading if reading is not None else self.reading_input,
                "dry_run": dry_run,
                "time": now.isoformat(),
            }
            if status is SubmitStatus.OK:
                self.state["last_submit_month"] = _month(now)
                self.state["last_submitted_at"] = now.isoformat()
                self.state["last_submitted_reading"] = self.state["last_result"][
                    "reading"
                ]
            await self._async_save()
        _LOGGER.info("Meter reading submission: %s", status.value)
        if status is SubmitStatus.OK:
            await self.coordinator.async_request_refresh()
        return status

    async def _async_submit(
        self, reading: int, dry_run: bool
    ) -> tuple[SubmitStatus, str | None]:
        if reading <= 0:
            return SubmitStatus.INVALID_READING, None
        highest = self._highest_known_reading()
        if reading < highest:
            return SubmitStatus.READING_DECREASED, f"{reading} < {highest}"

        data = self.entry.data
        last_error = "unknown"
        for attempt in range(1, SUBMIT_ATTEMPTS + 1):
            try:
                result = await self.client.async_submit_reading(
                    api_key=data[CONF_API_KEY],
                    customer_number=data[CONF_CUSTOMER_NUMBER],
                    contract_number=data[CONF_CONTRACT_NUMBER],
                    meter_number=data[CONF_METER_NUMBER],
                    reading=reading,
                    reading_date=dt_util.now().date(),
                    dry_run=dry_run,
                )
            except HSYConnectionError as err:
                last_error = str(err)
                _LOGGER.warning(
                    "Submitting reading failed (attempt %d/%d): %s",
                    attempt,
                    SUBMIT_ATTEMPTS,
                    last_error,
                )
                if attempt < SUBMIT_ATTEMPTS:
                    await asyncio.sleep(SUBMIT_RETRY_DELAY.total_seconds())
                continue
            except HSYApiError as err:
                return SubmitStatus.FAILED, str(err)
            if result.success:
                return (SubmitStatus.DRY_RUN_OK if dry_run else SubmitStatus.OK), None
            return SubmitStatus.REJECTED, result.message
        return SubmitStatus.FAILED, last_error

    # ---- automatic monthly submission -------------------------------------

    async def _async_auto_tick(self, now: datetime) -> None:
        await self.async_auto_submit(now)

    async def async_auto_submit(self, now: datetime) -> SubmitStatus | None:
        """Submit the stored reading if the schedule allows; None if skipped."""
        options = self.entry.options
        if not options.get(CONF_AUTO_SUBMIT, DEFAULT_AUTO_SUBMIT):
            return None
        days = [int(d) for d in options.get(CONF_AUTO_DAYS, DEFAULT_AUTO_DAYS)]
        start = int(options.get(CONF_AUTO_HOUR_START, DEFAULT_AUTO_HOUR_START))
        end = int(options.get(CONF_AUTO_HOUR_END, DEFAULT_AUTO_HOUR_END))
        if now.day not in days or not start <= now.hour < end:
            return None
        if self.reported_this_month(now):
            return None
        reading = self.reading_input
        if reading <= 0:
            return None
        blocked = self.state.get("auto_blocked") or {}
        if blocked.get("month") == _month(now) and blocked.get("reading") == reading:
            return None  # already refused with this reading; wait for a new one

        self.state["auto_last_attempt"] = now.isoformat()
        status = await self.async_submit(reading)
        if status in _NOT_RETRYABLE:
            _LOGGER.warning(
                "Automatic submission refused (%s); not retried until the reading changes",
                status.value,
            )
            self.state["auto_blocked"] = {"month": _month(now), "reading": reading}
            await self._async_save()
        return status
