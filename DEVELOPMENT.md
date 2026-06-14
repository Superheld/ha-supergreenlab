# Development

Internals, architecture and contributor notes for the SuperGreenLab Controller
integration. End-user docs live in [README.md](README.md).

## How it talks to the controller

The controller exposes its whole key/value store over a tiny HTTP server. The
integration uses the same local API the official app uses:

```
GET  http://<ip>/i?k=KEY          -> integer value (plain text)
POST http://<ip>/i?k=KEY&v=123    -> set integer
GET  http://<ip>/s?k=KEY          -> string value (plain text)
POST http://<ip>/s?k=KEY&v=...    -> set string (url-encoded)
GET  http://<ip>/fs/config.json   -> gzipped key manifest (auto-decompressed)
```

Auth is HTTP Basic and only enforced when `HTTPD_AUTH` is set on the device; by
default the API is open on the LAN.

## Device & entity model

- **One HA device: the controller.** A *box* is not a device — it's a logical
  slot (0..2) on the controller into which hardware is wired. The firmware has
  no "box" object; a box is just the set of flat keys prefixed `BOX_N_` plus
  pointer fields (`LED_x_BOX`, `BOX_x_*_SOURCE`) that map hardware to a box.
  Box membership therefore shows only as an entity name prefix; users group
  boxes spatially with HA Areas.
- **Declarative catalog.** Every entity is declared once in `catalog.py`
  (`EntityDef`): platform, templated key(s), scope, scaling, option map,
  category and polling speed. The platform modules expand the catalog over the
  detected instances — nothing device-specific is hand-wired per entity.
- **Two coordinators.** Live readings poll fast (30 s, adjustable); config
  values poll slow (180 s) and update optimistically on write. This keeps load
  off the single-threaded ESP32 webserver (a full poll is ~dozens of requests).
- **Structural vs operational config.** Structural choices (which boxes are
  enabled, which LED channel belongs to which box) live in the **options flow**
  because they decide which entities exist. Operational config (sources,
  schedules, fan curves) are entities. The controller is always the source of
  truth; the options flow writes to it and the entry reloads to re-discover.

### Entities

| Platform | Examples | Keys |
|---|---|---|
| light | brightness per LED channel | `LED_n_DIM` |
| sensor | temp / humi / VPD / CO₂, fan duty, light output | `BOX_x_TEMP/HUMI/VPD/CO2`, `BOX_x_BLOWER_DUTY/FAN_DUTY/TIMER_OUTPUT` |
| binary_sensor | light on, valve open, sensor present | `BOX_x_TIMER_OUTPUT`, `VALVE_OPEN`, `*_PRESENT` |
| time | light on / off | `BOX_x_ON_HOUR`+`ON_MIN`, `OFF_HOUR`+`OFF_MIN` |
| number | fan curve, watering, season, Emerson, calibration, valve, status LED | many |
| select | LED spectrum, timer mode, sensor & fan sources, motor source | `LED_n_TYPE`, `BOX_x_TIMER_TYPE`, `*_SOURCE` |
| switch | LED fade, Emerson, fast PWM, motor curve | `LED_n_FADE`, `BOX_x_TIMER_EMERSON_POWER`, `LEDS_FASTMODE`, `MOTORS_CURVE` |
| button | restart controller | `REBOOT` |

Diagnostics: `STATE`, `N_RESTARTS`, `*_PRESENT`.

### Decoded firmware semantics (`sources.py`)

`sources.py` is generated from SuperGreenOS `config.controller.json`. The
device's served `config.json` omits these mappings, so they are baked in (they
are firmware-version stable):

- **Sensor / reference sources** are integer-encoded into named indirection
  lists; e.g. `BOX_x_TEMP` reads from the `temp_sensor` list indexed by
  `BOX_x_TEMP_SOURCE` (`1` = SHT21 port 1, `16` = SCD30 port 1, `0` = off).
- **VPD** is stored as deci-pascals × 10 → divide the raw value by 100 for kPa.
- **LED output** = `LED_x_DUTY × LED_x_DIM / 100`. The mixer overwrites
  `LED_x_DUTY` from the schedule every 2 s, so `LED_x_DIM` is the user-facing
  brightness knob. An unassigned channel (`LED_x_BOX = -1`) is inert.
- Small enums: `STATE` (0 first-run / 1 idle / 2 running), `TIMER_TYPE`
  (manual / on-off / season), `VALVE_MODE`, `LED_TYPE` (spectrum).

## Repository layout

```
custom_components/supergreenlab/
  __init__.py        setup / unload, platform fan-out
  api.py             async HTTP client
  coordinator.py     device detection + fast/slow coordinators
  config_flow.py     setup + options (device layout, polling)
  catalog.py         the single declarative entity registry
  sources.py         generated enum / source maps
  entity.py          base entities + device info
  sensor.py binary_sensor.py number.py select.py switch.py time.py light.py button.py
```

## Testing

Tests use `pytest-homeassistant-custom-component` with a dict-backed fake
controller (`tests/conftest.py`), so no hardware is needed.

```bash
pip install -r requirements_test.txt
pytest -q
```

Covered: config flow, setup / entity creation / single-device model, control
writes (light, time, select), options layout + settings, and catalog / source
decoding invariants.

> Note: the suite needs the Python version Home Assistant targets (3.13). It
> runs in CI; local runs on a newer Python may fail to install HA.

## CI

`.github/workflows/ci.yml` runs on every push / PR:

- **ruff** — lint
- **hassfest** — Home Assistant manifest validation
- **HACS** — repository validation (`brands` ignored; only needed for the HACS
  default store)
- **pytest** — the test suite on Python 3.13

## Release workflow

Branch per change (never commit straight to `main`), fast-forward merge, then
tag a release so HACS shows the update:

```bash
git checkout -b feature/x
# … changes …
git checkout main && git merge --ff-only feature/x && git push origin main
gh release create vX.Y.Z --title vX.Y.Z --notes "…"
```

Bump `version` in `manifest.json` to match the tag.

## Contributing

Issues and PRs welcome. Keep the catalog the single source of entity
definitions; if you add device keys, prefer extending `catalog.py` over new
bespoke platform code.
