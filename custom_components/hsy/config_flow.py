"""Config flow for HSY."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
import voluptuous as vol

from . import HSYConfigEntry
from .api import HSYApiClient, HSYConnectionError, HSYData, HSYError, HSYNoDataError
from .const import (
    CONF_API_KEY,
    CONF_AUTO_DAYS,
    CONF_AUTO_HOUR_END,
    CONF_AUTO_HOUR_START,
    CONF_AUTO_SUBMIT,
    CONF_CONTRACT_NUMBER,
    CONF_CUSTOMER_NUMBER,
    CONF_METER_NUMBER,
    CONF_READING_SOURCE,
    CONF_UPDATE_INTERVAL,
    CONF_WASTE_SERVICE_NUMBER,
    CONF_WATER_SERVICE_NUMBER,
    DEFAULT_AUTO_DAYS,
    DEFAULT_AUTO_HOUR_END,
    DEFAULT_AUTO_HOUR_START,
    DEFAULT_AUTO_SUBMIT,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    SUBMIT_KEYS,
)

_LOGGER = logging.getLogger(__name__)

_TEXT = TextSelector()
_PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


def _submit_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_API_KEY): _PASSWORD,
            **{
                vol.Optional(key, description={"suggested_value": defaults.get(key)}): (
                    _TEXT
                )
                for key in (
                    CONF_CUSTOMER_NUMBER,
                    CONF_CONTRACT_NUMBER,
                    CONF_METER_NUMBER,
                )
            },
        }
    )


def _clean_submit(user_input: dict[str, Any]) -> dict[str, str] | None:
    """Return the submission settings, {} when skipped, None when incomplete."""
    values = {key: str(user_input.get(key) or "").strip() for key in SUBMIT_KEYS}
    if not any(values.values()):
        return {}
    if not all(values.values()):
        return None
    return values


class HSYConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HSY."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._report: dict[str, str] = {}
        self._data: HSYData | None = None

    async def _async_validate(
        self, water: str, waste: str
    ) -> tuple[HSYData | None, str | None]:
        client = HSYApiClient(async_get_clientsession(self.hass), water, waste)
        try:
            return await client.async_get_data(), None
        except HSYConnectionError:
            return None, "cannot_connect"
        except HSYNoDataError:
            return None, "invalid_service_numbers"
        except HSYError:
            _LOGGER.exception("Unexpected eRaportti response")
            return None, "unknown"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the eRaportti service numbers."""
        errors: dict[str, str] = {}
        if user_input is not None:
            water = user_input[CONF_WATER_SERVICE_NUMBER].strip()
            waste = user_input[CONF_WASTE_SERVICE_NUMBER].strip()
            await self.async_set_unique_id(f"{water}_{waste}")
            self._abort_if_unique_id_configured()
            data, error = await self._async_validate(water, waste)
            if error:
                errors["base"] = error
            else:
                self._report = {
                    CONF_WATER_SERVICE_NUMBER: water,
                    CONF_WASTE_SERVICE_NUMBER: waste,
                }
                self._data = data
                return await self.async_step_submit()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_WATER_SERVICE_NUMBER): _TEXT,
                        vol.Required(CONF_WASTE_SERVICE_NUMBER): _TEXT,
                    }
                ),
                user_input,
            ),
            errors=errors,
        )

    def _defaults(self, data: HSYData | None) -> dict[str, Any]:
        if data is None:
            return {}
        return {
            CONF_CUSTOMER_NUMBER: data.customer_number,
            CONF_CONTRACT_NUMBER: data.contract_number,
            CONF_METER_NUMBER: data.meter_number,
        }

    async def async_step_submit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the optional reading submission settings."""
        errors: dict[str, str] = {}
        if user_input is not None:
            submit = _clean_submit(user_input)
            if submit is None:
                errors["base"] = "incomplete_submit"
            else:
                return self.async_create_entry(
                    title="HSY", data={**self._report, **submit}
                )
        return self.async_show_form(
            step_id="submit",
            data_schema=_submit_schema(self._defaults(self._data)),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the reading submission settings."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            submit = _clean_submit(user_input)
            if submit is None:
                errors["base"] = "incomplete_submit"
            else:
                cleared = {key: "" for key in SUBMIT_KEYS}
                return self.async_update_reload_and_abort(
                    entry, data_updates={**cleared, **submit}
                )
        coordinator = getattr(entry, "runtime_data", None)
        data = coordinator.coordinator.data if coordinator else None
        defaults = {
            **self._defaults(data),
            **{k: v for k, v in entry.data.items() if v},
        }
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_submit_schema(defaults),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: HSYConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return HSYOptionsFlow()


class HSYOptionsFlow(OptionsFlow):
    """Polling interval and automatic submission schedule."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_AUTO_DAYS] = sorted(
                int(d) for d in user_input[CONF_AUTO_DAYS]
            )
            user_input[CONF_UPDATE_INTERVAL] = int(user_input[CONF_UPDATE_INTERVAL])
            user_input[CONF_AUTO_HOUR_START] = int(user_input[CONF_AUTO_HOUR_START])
            user_input[CONF_AUTO_HOUR_END] = int(user_input[CONF_AUTO_HOUR_END])
            if user_input[CONF_AUTO_HOUR_START] >= user_input[CONF_AUTO_HOUR_END]:
                errors["base"] = "invalid_hours"
            elif user_input[CONF_AUTO_SUBMIT] and not user_input[CONF_AUTO_DAYS]:
                errors["base"] = "no_days"
            else:
                return self.async_create_entry(data=user_input)

        options = {
            CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
            CONF_AUTO_SUBMIT: DEFAULT_AUTO_SUBMIT,
            CONF_AUTO_DAYS: DEFAULT_AUTO_DAYS,
            CONF_AUTO_HOUR_START: DEFAULT_AUTO_HOUR_START,
            CONF_AUTO_HOUR_END: DEFAULT_AUTO_HOUR_END,
            **self.config_entry.options,
            **(user_input or {}),
        }
        options[CONF_AUTO_DAYS] = [str(d) for d in options[CONF_AUTO_DAYS]]
        schema = vol.Schema(
            {
                vol.Required(CONF_UPDATE_INTERVAL): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=168,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="h",
                    )
                ),
                vol.Optional(CONF_READING_SOURCE): EntitySelector(
                    EntitySelectorConfig(domain=["sensor", "number", "input_number"])
                ),
                vol.Required(CONF_AUTO_SUBMIT): BooleanSelector(),
                vol.Required(CONF_AUTO_DAYS): SelectSelector(
                    SelectSelectorConfig(
                        options=[str(d) for d in range(1, 29)],
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_AUTO_HOUR_START): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=23, step=1, mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_AUTO_HOUR_END): NumberSelector(
                    NumberSelectorConfig(
                        min=1, max=24, step=1, mode=NumberSelectorMode.BOX
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, options),
            errors=errors,
        )
