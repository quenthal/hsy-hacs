# HSY for Home Assistant

Custom integration for [HSY](https://www.hsy.fi/) (Helsinki Region Environmental
Services) customers. It reads your water and waste data from HSY eRaportti and
can submit your water meter reading to HSY automatically once a month.

*Suomeksi alla.*

## Features

- Water meter reading, last reported reading and reading dates
- Water usage and costs for the current year (with yearly history as attributes)
- Waste collected and waste costs for the current year, in total and per fraction
- Next collection date for every waste container (mixed, bio, cardboard, …)
- Optional monthly automatic submission of the water meter reading, with:
  - a number entity for the reading to submit
  - "reading submitted this month" binary sensor and submission result sensor
  - protection against submitting a reading lower than the previous one
  - no hourly retries after HSY has refused a reading; a new reading is tried again

Dates are exposed as timestamps (12:00 local time), so the frontend shows them
relative, e.g. "in 3 days".

## Installation

1. In HACS, add this repository as a custom repository (category *Integration*).
2. Install **HSY** and restart Home Assistant.
3. Go to *Settings → Devices & services → Add integration → HSY*.

## Configuration

1. **Service numbers**: the water and waste service numbers shown in HSY eRaportti.
2. **Meter reading submission (optional)**: the API key for HSY's reading
   service. Customer, contract and meter numbers are prefilled from eRaportti.
   Leave everything empty to use only the sensors. You can change this later
   with *Reconfigure*.

Options: update interval (default 24 h) and the automatic submission schedule
(off by default; days 1–6 of the month, 8–23 o'clock). The automatic submission
sends the value of the *Meter reading to submit* entity, so update it e.g. from
an automation or manually before the window.

## Privacy

Service numbers, API key and customer details are stored only in your Home
Assistant configuration and are redacted from diagnostics.

---

## Suomeksi

HSY:n eRaportin vesi- ja jätetiedot Home Assistantiin: vesimittarin lukema,
vedenkulutus ja -kustannukset, kerätyt jätteet ja jätekustannukset sekä
jäteastioiden seuraavat noudot. Valinnaisesti integraatio lähettää
vesimittarin lukeman HSY:lle automaattisesti kerran kuussa. Lähetettävä
lukema syötetään *Lähetettävä lukema* -entiteettiin.

Asennus HACS:n custom repositoryna, minkä jälkeen *Asetukset → Laitteet ja
palvelut → Lisää integraatio → HSY*.

## Disclaimer

This is an unofficial integration and is not affiliated with HSY.
