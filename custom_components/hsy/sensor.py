"""Sensors for HSY."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_EURO, EntityCategory, UnitOfMass, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import HSYConfigEntry
from .api import HSYData, WasteFraction
from .const import DATE_HOUR
from .coordinator import HSYCoordinator
from .entity import HSYEntity, HSYSubmitEntity
from .submit import HSYSubmitManager, SubmitStatus

type StateType = float | int | str | datetime | None


def _at_hour(value: date | None) -> datetime | None:
    """Return the date as a local timestamp at DATE_HOUR."""
    if value is None:
        return None
    return datetime.combine(value, time(DATE_HOUR), dt_util.get_default_time_zone())


# Long histories are shown as attributes but not written to the recorder.
_UNRECORDED = frozenset({"history", "readings"})


@dataclass(frozen=True, kw_only=True)
class HSYSensorDescription(SensorEntityDescription):
    """eRaportti sensor description."""

    value_fn: Callable[[HSYData], StateType]
    attrs_fn: Callable[[HSYData], dict[str, Any]] | None = None


@dataclass(frozen=True, kw_only=True)
class HSYFractionSensorDescription(SensorEntityDescription):
    """Per waste fraction sensor description."""

    value_fn: Callable[[WasteFraction], StateType]
    attrs_fn: Callable[[WasteFraction], dict[str, Any]] | None = None


SENSORS: tuple[HSYSensorDescription, ...] = (
    HSYSensorDescription(
        key="meter_reading",
        translation_key="meter_reading",
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        value_fn=lambda d: d.meter_reading,
        attrs_fn=lambda d: {"meter_number": d.meter_number, "model": d.meter_model},
    ),
    HSYSensorDescription(
        key="meter_read_on",
        translation_key="meter_read_on",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _at_hour(d.meter_read_on),
    ),
    HSYSensorDescription(
        key="meter_installed_on",
        translation_key="meter_installed_on",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _at_hour(d.meter_installed_on),
    ),
    HSYSensorDescription(
        key="last_reported_reading",
        translation_key="last_reported_reading",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        value_fn=lambda d: d.last_reported_reading,
        attrs_fn=lambda d: {"readings": d.reported_readings},
    ),
    HSYSensorDescription(
        key="water_usage",
        translation_key="water_usage",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        value_fn=lambda d: d.water_usage,
        attrs_fn=lambda d: {"history": d.water_usage_history},
    ),
    HSYSensorDescription(
        key="water_costs",
        translation_key="water_costs",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        value_fn=lambda d: d.water_costs,
        attrs_fn=lambda d: {"history": d.water_costs_history},
    ),
    HSYSensorDescription(
        key="waste_collected",
        translation_key="waste_collected",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        value_fn=lambda d: d.waste_collected,
        attrs_fn=lambda d: {"history": d.waste_collected_history},
    ),
    HSYSensorDescription(
        key="waste_costs",
        translation_key="waste_costs",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        value_fn=lambda d: d.waste_costs,
        attrs_fn=lambda d: {"history": d.waste_costs_history},
    ),
    HSYSensorDescription(
        key="data_updated",
        translation_key="data_updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.updated_at,
    ),
)

FRACTION_SENSORS: tuple[HSYFractionSensorDescription, ...] = (
    HSYFractionSensorDescription(
        key="next_collection",
        translation_key="next_collection",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda f: _at_hour(f.next_collection),
        attrs_fn=lambda f: {"interval": f.interval, "container_size": f.container_size},
    ),
    HSYFractionSensorDescription(
        key="collected",
        translation_key="fraction_collected",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        value_fn=lambda f: f.collected,
    ),
    HSYFractionSensorDescription(
        key="costs",
        translation_key="fraction_costs",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        value_fn=lambda f: f.costs,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HSYConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up HSY sensors."""
    coordinator = entry.runtime_data.coordinator
    entities: list[SensorEntity] = [
        HSYSensor(coordinator, description) for description in SENSORS
    ]
    entities += [
        HSYFractionSensor(coordinator, fraction, description)
        for fraction in coordinator.data.fractions.values()
        for description in FRACTION_SENSORS
    ]
    if submit := entry.runtime_data.submit:
        entities += [
            HSYLastSubmittedSensor(submit),
            HSYSubmitResultSensor(submit),
            HSYAutoAttemptSensor(submit),
        ]
    async_add_entities(entities)


class HSYSensor(HSYEntity, SensorEntity):
    """eRaportti sensor."""

    entity_description: HSYSensorDescription
    _unrecorded_attributes = _UNRECORDED

    def __init__(
        self, coordinator: HSYCoordinator, description: HSYSensorDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if attrs_fn := self.entity_description.attrs_fn:
            return attrs_fn(self.coordinator.data)
        return None


class HSYFractionSensor(HSYEntity, SensorEntity):
    """Sensor of one waste fraction."""

    entity_description: HSYFractionSensorDescription

    def __init__(
        self,
        coordinator: HSYCoordinator,
        fraction: WasteFraction,
        description: HSYFractionSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, f"{fraction.key}_{description.key}")
        self.entity_description = description
        self._fraction_key = fraction.key
        self._attr_translation_placeholders = {"fraction": fraction.name}

    @property
    def _fraction(self) -> WasteFraction | None:
        return self.coordinator.data.fractions.get(self._fraction_key)

    @property
    def available(self) -> bool:
        """Return False when the fraction disappeared from eRaportti."""
        return super().available and self._fraction is not None

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        fraction = self._fraction
        return self.entity_description.value_fn(fraction) if fraction else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        fraction = self._fraction
        if fraction and (attrs_fn := self.entity_description.attrs_fn):
            return attrs_fn(fraction)
        return None


class HSYLastSubmittedSensor(HSYSubmitEntity, SensorEntity):
    """When a reading was last submitted successfully."""

    _attr_translation_key = "last_submitted"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, manager: HSYSubmitManager) -> None:
        """Initialize the sensor."""
        super().__init__(manager, "last_submitted")

    @property
    def native_value(self) -> datetime | None:
        """Return the state."""
        return self.manager.last_submitted_at


class HSYSubmitResultSensor(HSYSubmitEntity, SensorEntity):
    """Result of the latest submission attempt."""

    _attr_translation_key = "last_submit_result"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [status.value for status in SubmitStatus]  # noqa: RUF012
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, manager: HSYSubmitManager) -> None:
        """Initialize the sensor."""
        super().__init__(manager, "last_submit_result")

    @property
    def native_value(self) -> str | None:
        """Return the state."""
        result = self.manager.last_result
        return result["status"] if result else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the details of the latest attempt."""
        result = self.manager.last_result
        if not result:
            return None
        return {k: result.get(k) for k in ("message", "reading", "dry_run", "time")}


class HSYAutoAttemptSensor(HSYSubmitEntity, SensorEntity):
    """When the automatic submission last tried."""

    _attr_translation_key = "auto_last_attempt"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, manager: HSYSubmitManager) -> None:
        """Initialize the sensor."""
        super().__init__(manager, "auto_last_attempt")

    @property
    def native_value(self) -> datetime | None:
        """Return the state."""
        return self.manager.auto_last_attempt
