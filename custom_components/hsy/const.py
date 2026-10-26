"""Constants for the HSY integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "hsy"

REPORT_BASE_URL: Final = "https://raportit.hsy.fi/report/ajax-open"
SUBMIT_URL: Final = "https://lukemat.hsy.fi/vesimittari/rest/v1/reading/store/"
# eRaportti returns waste fraction names in the requested language; parsing
# relies on the Finnish names, translations are handled by Home Assistant.
REPORT_LANGUAGE: Final = "fi"

CONF_WATER_SERVICE_NUMBER: Final = "water_service_number"
CONF_WASTE_SERVICE_NUMBER: Final = "waste_service_number"
CONF_API_KEY: Final = "api_key"
CONF_CUSTOMER_NUMBER: Final = "customer_number"
CONF_CONTRACT_NUMBER: Final = "contract_number"
CONF_METER_NUMBER: Final = "meter_number"
SUBMIT_KEYS: Final = (
    CONF_API_KEY,
    CONF_CUSTOMER_NUMBER,
    CONF_CONTRACT_NUMBER,
    CONF_METER_NUMBER,
)

CONF_UPDATE_INTERVAL: Final = "update_interval_hours"
CONF_AUTO_SUBMIT: Final = "auto_submit"
CONF_AUTO_DAYS: Final = "auto_submit_days"
CONF_AUTO_HOUR_START: Final = "auto_submit_hour_start"
CONF_AUTO_HOUR_END: Final = "auto_submit_hour_end"
CONF_READING_SOURCE: Final = "reading_source"

DEFAULT_UPDATE_INTERVAL: Final = 24
DEFAULT_AUTO_SUBMIT: Final = False
DEFAULT_AUTO_DAYS: Final = [1, 2, 3, 4, 5, 6]
DEFAULT_AUTO_HOUR_START: Final = 8
DEFAULT_AUTO_HOUR_END: Final = 23

REQUEST_TIMEOUT: Final = 30
SUBMIT_ATTEMPTS: Final = 3
SUBMIT_RETRY_DELAY: Final = timedelta(seconds=60)

STORAGE_VERSION: Final = 1

SERVICE_SUBMIT_READING: Final = "submit_reading"
ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"
ATTR_READING: Final = "reading"
ATTR_DRY_RUN: Final = "dry_run"

# Dates from eRaportti are shown as timestamps at this local hour, so that
# the frontend renders them relative ("in 3 days").
DATE_HOUR: Final = 12

# Known waste fractions: eRaportti name -> stable key used in unique ids.
WASTE_FRACTIONS: Final = {
    "Sekajäte": "mixed",
    "Biojäte": "bio",
    "Kartonki": "cardboard",
    "Lasi": "glass",
    "Metalli": "metal",
    "Muovi": "plastic",
    "Paperi": "paper",
}
