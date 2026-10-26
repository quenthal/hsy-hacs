<img src="custom_components/hsy/brand/icon.png" alt="HSY" width="96" align="right">

# HSY for Home Assistant

Custom integration for [HSY](https://www.hsy.fi/) (Helsinki Region Environmental
Services) customers. It reads your water and waste data from HSY eRaportti and
can submit your water meter reading to HSY automatically once a month.

> **Unofficial.** This is a community project with no affiliation, partnership
> or endorsement by HSY. Using the HSY name and logo does not imply any
> official relationship. HSY does not support this integration; please report
> issues here, not to HSY.

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

> **Epävirallinen.** Tämä on yhteisöprojekti, eikä sillä ole mitään virallista
> yhteyttä, yhteistyötä tai hyväksyntää HSY:n kanssa. HSY:n nimen ja logon
> käyttö ei tarkoita virallista suhdetta. HSY ei tue tätä integraatiota;
> ilmoita ongelmista tämän repon kautta, älä HSY:lle.

HSY:n eRaportin vesi- ja jätetiedot Home Assistantiin: vesimittarin lukema,
vedenkulutus ja -kustannukset, kerätyt jätteet ja jätekustannukset sekä
jäteastioiden seuraavat noudot. Valinnaisesti integraatio lähettää
vesimittarin lukeman HSY:lle automaattisesti kerran kuussa. Lähetettävä
lukema syötetään *Lähetettävä lukema* -entiteettiin.

Asennus HACS:n custom repositoryna, minkä jälkeen *Asetukset → Laitteet ja
palvelut → Lisää integraatio → HSY*.

## License

MIT, see [LICENSE](LICENSE). The license covers the code only, not the HSY name or logo.

## Disclaimer

This is an unofficial integration and is not affiliated with, endorsed by or
supported by HSY (Helsingin seudun ympäristöpalvelut -kuntayhtymä). The HSY
name and logo, including the integration icon, are trademarks of HSY and are
used only to identify the service the integration connects to. They do not
indicate any official relationship. If HSY asks, the icon will be removed.
