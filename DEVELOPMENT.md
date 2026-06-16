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

- **Controller device + per-box sub-devices.** The controller is the parent HA
  device; each *enabled* box is a sub-device (`box_device_info`, linked via
  `via_device`, identifier `<client_id>_box_<n>`). So HA groups a box's entities
  natively, box entities carry short names ("Temperature", "Fan mode" — the box
  device supplies the "Box N" context), and entity ids stay clean
  (`sensor.box_0_temperature`, no controller-name prefix). `entity.py` assigns
  the device: `_box_for()` maps an instance to its box (`box` placeholder, or the
  LED's box for `led_box` scope), else the controller. The firmware itself has no
  "box" object — a box is just flat `BOX_N_*` keys plus pointer fields
  (`LED_x_BOX`, `BOX_x_*_SOURCE`). Controller-wide entities (state, restart,
  valve, motors, status LED) stay on the controller device. Assign each box
  device to its own Area for room grouping.
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

### What actually binds to a box

A box is a logical control group, **not** a hardware container — only some
hardware is "in" a box. Four distinct relationships:

| Binding | Hardware / keys | Notes |
|---|---|---|
| **Wired to the box by index** | Fan (`BOX_x_FAN_*`), Blower (`BOX_x_BLOWER_*`), watering logic (`BOX_x_WATERING_*`), plus the light/climate *logic* (schedule, `TIMER_TYPE`, season, Emerson) | No assignment key exists — the fan/blower *is* the box's. Fixed per slot. |
| **Assigned to a box (flexible)** | LED channels via `LED_x_BOX` (-1 = none, 0..2) | The only hardware you map into a box. A box's light = the channels pointing at it (this is the options-flow LED assignment). |
| **Global, referenced by pointer** | Sensors: SHT21 / SCD30 / HX711 on i2c ports; a box selects one per metric via `BOX_x_{TEMP,HUMI,VPD,CO2,WEIGHT}_SOURCE` | Sensors are device-wide. A box doesn't own one — two boxes can read the same sensor. Calibration/offset lives on the sensor. |
| **Global, unrelated to box** | Motors (`MOTOR_x_*`, follow a *source* that may be a box value), Valve (`VALVE_*`), status LED, WiFi/OTA/broker/auth, `STATE`, and the all-device flags `LEDS_FASTMODE` / `MOTORS_CURVE` | Float alongside the boxes. |

### Entities

| Platform | Examples | Keys |
|---|---|---|
| light | brightness per LED channel | `LED_n_DIM` |
| sensor | temp / humi / VPD / CO₂, fan duty, light output, **season date** (synthetic) | `BOX_x_TEMP/HUMI/VPD/CO2`, `BOX_x_BLOWER_DUTY/FAN_DUTY/TIMER_OUTPUT`, `BOX_x_SIMULATED_TIME` |
| binary_sensor | light on, valve open, sensor present | `BOX_x_TIMER_OUTPUT`, `VALVE_OPEN`, `*_PRESENT` |
| time | light on / off | `BOX_x_ON_HOUR`+`ON_MIN`, `OFF_HOUR`+`OFF_MIN` |
| number | fan curve, watering, season, Emerson, calibration, valve, status LED | many |
| select | LED spectrum, timer mode, sensor & fan sources, motor source | `LED_n_TYPE`, `BOX_x_TIMER_TYPE`, `*_SOURCE` |
| switch | LED fade, Emerson, fast PWM, motor curve; **sunglasses** (synthetic) | `LED_n_FADE`, `BOX_x_TIMER_EMERSON_POWER`, `LEDS_FASTMODE`, `MOTORS_CURVE`, `BOX_x_LED_DIM` |
| button | restart controller | `REBOOT` |

The **sunglasses** switch (`SuperGreenSunglassesSwitch` in `switch.py`) is
synthetic: `BOX_x_LED_DIM` is a unix timestamp, so on=stamp now, off=0, and
`is_on = now - ts < 1200` (it self-clears after ~20 min on the next poll). The
key is polled fast (added in `build_coordinators`). Useful as an automation
target/condition for a "working in the box" mode.

Diagnostics: `STATE`, `N_RESTARTS`, `*_PRESENT`.

## Firmware reference (what we learned from SuperGreenOS)

The firmware is a flat key/value store with no real object model — "box",
"fan", etc. are naming conventions over flat `BOX_N_*` / `LED_x_*` keys plus
pointer fields. Everything below was reverse-engineered from the SuperGreenOS
source and is baked into `sources.py` (the device's served `config.json` omits
the encodings; they are firmware-version stable).

### Lighting

- **LED output** = `LED_x_DUTY × LED_x_DIM / 100`. The **mixer** task overwrites
  `LED_x_DUTY` from the box timer output every 2 s, so `LED_x_DIM` (0–100) is the
  user-facing brightness knob; `LED_x_DUTY` is computed, not user-set.
- An **unassigned** channel (`LED_x_BOX = -1`) is inert: its duty is forced to 0
  and the mixer ignores it.
- `LED_x_TYPE` is the spectrum (0 Full / 1 UV-A / 2 Deep blue / 3 Deep red /
  4 Far red); it selects which timer drives the channel in the mixer.
- **`BOX_x_LED_DIM` is *not* a master brightness** — despite the name it's a unix
  timestamp for the app's "Sunglasses" mode. While `now - BOX_x_LED_DIM < 1200`
  (~20 min after pressing), channels with `LED_x_FADE` dim to ≤15 % (others to 0)
  so you can work in the box without being blinded (`led.c`). Per-channel
  brightness is `LED_x_DIM`.

### Light schedule & grow phases

The controller's light schedule is just **four numbers** per box —
`BOX_x_{ON,OFF}_{HOUR,MIN}` — plus `TIMER_TYPE` (0 Manual / 1 On-Off / 2 Season).
That's all it stores.

The app's familiar **Vegetative / Bloom / Auto** phases are *not* a controller
concept. They are presets the app keeps on its own side (`box.settings`,
`SuperGreenApp2/.../box_settings.dart`); picking one simply writes the matching
times to those four keys (and, for Bloom, logs a cloud journal entry). Defaults:

| Phase | on | off | light hours |
|---|---|---|---|
| Vegetative | 03:00 | 21:00 | 18 |
| Bloom | 06:00 | 18:00 | 12 |
| Auto | 02:00 | 22:00 | 20 |

We once mirrored this with a synthetic **"Light phase"** select (derive-from-
times + write-times). It was **removed** (v0.11.0): it's not a real device
concept, doesn't sync with the app's own phase (below), and named-the-same-thing
caused more confusion than the one-click convenience was worth. The light card
now just shows the raw on/off times; users pick times directly.

**One-way by nature:** because the phase label lives only in the app (and its
cloud), changing the schedule from anywhere else (HA, a second phone) updates the
device's *times* but the app keeps showing its last-set phase — e.g. it stays on
"Auto" after we set Bloom. There is no device key to sync the label back, so this
is not fixable locally (only via the SGL cloud, which we deliberately avoid). The
actual schedule on the device is correct regardless; only the app's cosmetic
label and its journal history lag.

### Ventilation — Fan vs Blower

Two distinct units per box: **Fan** (`BOX_x_FAN_*`, circulates air *inside* the
box) and **Blower** (`BOX_x_BLOWER_*`, exhausts air *out*). (Not "intake/exhaust
fan".) Each is an auto-curve driven by a reference:

- `*_REF_SOURCE` — what it follows (see source lists below): a temperature,
  humidity, VPD, CO₂ reading, a box timer output, or 0 = manual.
- `*_REF_MIN` / `*_REF_MAX` — the reference range over which it ramps. **One
  shared pair per unit** — its meaning changes with the source (°C in temp mode,
  % in humidity mode, …). There are no per-metric fields, so switching mode must
  rewrite these to sensible presets.
- `*_MIN` / `*_MAX` — the output duty range (%). `output = MIN + (MAX-MIN) ×
  (ref-REF_MIN)/(REF_MAX-REF_MIN)`, clamped. `*_DUTY` is the computed result
  (read-only). Source 0 ⇒ refOutput defaults to mid/0 ⇒ effectively `MIN`.

### Season

`TIMER_TYPE = 2` (Season) makes the box light follow a simulated sun curve
instead of a fixed schedule. It compresses a real outdoor season into the grow:

- `START_MONTH` / `START_DAY` — the calendar date the simulated season starts at.
- `DURATION_DAYS` — length of the simulated season (e.g. 215).
- `SIM_DURATION_DAYS` — how many *real* days to compress that into (e.g. 75).
- `STARTED_AT` — unix timestamp anchor; set to *now* to (re)start the season.
- The firmware advances `BOX_x_SIMULATED_TIME` proportionally to real time
  elapsed, then derives `timer_output` from a cosine of the year + day position.
- Exposed as: the four numbers + a **"Start season"** button (writes
  `STARTED_AT = now`), and a read-only **"Season date"** timestamp sensor
  (`SuperGreenSeasonDateSensor` in `sensor.py`, from `BOX_x_SIMULATED_TIME`,
  polled slow) so you can see how far the season has progressed.
- Note: `BOX_x_SIMULATED_TIME` is HTTP-readable even though it has no `keys.h`
  macro (it's still a generated KV with HTTP enabled).

### Sensors & VPD

- Per-box `BOX_x_{TEMP,HUMI,VPD,CO2,WEIGHT}` are read-only, fed via indirection
  from the source selected by `BOX_x_*_SOURCE`.
- **VPD** is stored as pascals/10 → divide the raw value by **100** for kPa.

### Encoded source lists

`*_SOURCE` keys index a named indirection list; the integer is `not` 0..n — it
encodes both the metric and the port. Lists (full maps in `sources.py`):
`temp_sensor`, `humi_sensor`, `vpd_sensor`, `co2_sensor`, `weight_sensor`,
`fan_ref`, `blower_ref`, `motor_input`, `valve_ref`, `valve_ref_on`. `0` is
always off/manual. Example (`temp_sensor`): `1–3` = SHT21 ports, `16–18` = SCD30
ports.

**Present-only filtering:** these lists enumerate every metric × port, which
floods the dropdowns. `SuperGreenSelect.options` (in `select.py`) filters sensor
entries to the firmware's `{SHT21,SCD30,HX711}_n_PRESENT` flags (parsed from the
"… on port #N" labels, `#N → PRESENT_{N-1}`). Non-sensor entries (off, box timer
outputs, motor controls) always stay; it falls back to all sensors if presence
detection reports none, and always keeps the current selection so the state
stays valid. The `*_PRESENT` keys are polled by the slow coordinator (the same
one the source selects use).

### Small enums

`STATE` (0 first-run / 1 idle / 2 running), `TIMER_TYPE` (0 Manual / 1 On-Off /
2 Season), `VALVE_MODE` (0 disabled / 1 keep-between / 2 keep-out),
`LED_BOX` (-1 unassigned / 0..2 box), `LED_TYPE` (spectrum, above).

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

**Python** (the integration):

```bash
pip install -r requirements_test.txt
pytest -q
```

Covered: config flow, setup / entity creation / single-device model, control
writes (light, time, select, number, button), the present-only source filter +
its fallback, the light-phase select (write + derivation), the fan/blower mode
presets, options layout + settings, and catalog / source decoding invariants.

> Note: the suite needs the Python version Home Assistant targets (3.13). It
> runs in CI; local runs on a newer Python may fail to install HA.

**JavaScript** (the bundled cards' resolution logic):

```bash
node --test
```

The card module is loaded by HA as an ES module, so the three resolver functions
(`resolveConfig` / `resolveLightConfig` / `resolveBoxConfig`) are `export`ed and
tested in isolation (`tests/cards.test.js`) with a fake `hass`. The root
`package.json` only marks the `.js` as ESM for node — it is not an npm package.
Tests cover device/kind/box matching, the blower vs fan distinction, phase +
schedule resolution, spectrum-by-LED-index correlation, and that a box card
never mixes in another box's entities. The card classes touch browser globals at
import, so the test stubs `HTMLElement` / `customElements` / `window` first.

Add tests with every change — Python for entity logic, node for card resolution.

## CI

`.github/workflows/ci.yml` runs on every push / PR:

- **ruff** — lint
- **hassfest** — Home Assistant manifest validation
- **HACS** — repository validation (`brands` ignored; only needed for the HACS
  default store). **Gated to the `main` branch and PRs**: HACS validates the repo
  as a "version", and a feature branch isn't a valid one — running it on every
  branch push failed spuriously (`structure for refs/heads/… is not compliant`).
- **pytest** — the Python suite on Python 3.13
- **cards** — `node --test` for the card resolution logic

## Release workflow

Work flows **feature → `dev` → `main`**. Never commit straight to `dev`/`main`;
use a feature branch and fast-forward merge. The `version` in `manifest.json` is
set **at release time**, not during feature work.

Stable release:

```bash
git checkout -b feature/x dev
# … changes … (do NOT touch manifest version)
git checkout dev && git merge --ff-only feature/x && git push origin dev
# bump manifest.json version to X.Y.Z ("Release vX.Y.Z" commit), then:
git checkout main && git merge --ff-only dev && git push origin main
gh release create vX.Y.Z --target main --title vX.Y.Z --notes "…"
```

### Beta / test channel (HACS)

HACS can't install an arbitrary branch for an integration that has releases, so
the test channel is **pre-release tags** cut from `dev`:

```bash
# manifest.json version = X.Y.Zb1, "Pre-release vX.Y.Zb1" commit on dev, push
gh release create vX.Y.Zb1 --target dev --prerelease --title vX.Y.Zb1 --notes "…"
```

Testers enable it in HACS: the integration → ⋮ → **Redownload** → toggle **Show
beta versions** → pick the beta → restart HA. Keep this out of the user-facing
README (testers only). Stable releases supersede the beta automatically.

## Bundled Lovelace cards (`sgl-cards.js`)

The integration serves `sgl-cards.js` and auto-registers it
(`async_register_static_paths` + `add_extra_js_url`), so no separate HACS plugin
or manual dashboard resource is needed. Notes:

- `frontend`/`http` are declared as **`after_dependencies`** (not
  `dependencies`) — `dependencies` would force the `frontend` component to set up
  in tests, where its compiled `hass_frontend` assets are missing. Registration
  is wrapped in try/except so it can never break setup.
- The extra-JS URL is **cache-busted** with the integration version
  (`?v=<version>`); without it browsers serve a stale card after an update.
- Cards render a native HA **`entities` card** via `loadCardHelpers()` and just
  choose which rows to show — so controls look/behave natively.
- They are **mode-aware**: `sgl-fan-card` switches rows on the fan/blower mode;
  `sgl-light-card` is the **scheduler** (like the app's schedule screen) — it
  shows only the timer mode + the inputs that mode needs (On/Off → on/off times;
  Season → season date + season settings). Per-channel brightness and "light on"
  are deliberately *not* in it.
- **Direction:** the same mode-aware behaviour is now achievable *natively* with a
  **Sections view + per-card `visibility` conditions** (see
  `dashboards/example-box-sections.yaml`) — no custom JS, fits the modern design,
  and uses explicit ids so it can't mis-resolve. That's the recommended path; the
  custom cards may be retired in favour of it.
- `sgl-box-card` is the per-box **hardware setup** card (lean on purpose): two
  `{type: "section"}` groups — *Climate sensors* (the `*_SOURCE` selects) and
  *Light spectrum* (`LED_x_TYPE`). No live values / fan modes / schedule. Anchors
  on any box entity (`entity:`, or `mode:` as alias). Spectrum selects carry no
  box token (named `Light {led} spectrum`), so it correlates them to the box via
  the LED index in the box's `light` entity ids.
- **Entity resolution** is the tricky part. From the anchor `mode` entity the
  card finds siblings by **shared `device_id`** (via `hass.entities`), the fan
  *kind* (`fan`/`blower`, plus legacy `intake`/`exhaust`), a **soft** box-index
  filter (prefer the matching box, fall back to ignoring it), and a role suffix
  that accepts current **and** legacy names (`speed_min`|`fan_min`,
  `reference_from`|`ref_min`, …). Resolve runs every render (entities can appear
  later). Don't match by entity-id prefix — ids diverge (see gotchas).

## Building the firmware (Docker, no hardware)

To build SuperGreenOS (e.g. to develop the upstream `GET /all` bulk endpoint —
see PR [supergreenlab/SuperGreenOS#10](https://github.com/supergreenlab/SuperGreenOS/pull/10)):

1. Codegen: `npm i -g ejs-cli` then `./update_templates.sh config.controller.json`
   (turns `.template` files into `.c/.h`). Works on modern Node.
2. Build: `docker run --rm -e BATCH_BUILD=1 -v "$PWD":/project -w /project
   espressif/idf:release-v3.3 sh -c 'rm -rf build && make'`

Gotchas: use the **`release-v3.3`** image (the `v3.3.1` tag and the README's
pinned commit both miss `MQTT_EVENT_ANY`; `release-v3.3` adds `MQTT_EVENT_DELETED`
which needs a `default:` case in the mqtt event switch). Build **serially** (`-j`
corrupts `component_project_vars.mk`). The image is amd64 → emulated/slow on
Apple Silicon.

**OTA deploy** (instead of serial flashing): the firmware OTA is plain HTTP — it
fetches `<basedir>/last_timestamp` then `<basedir>/<ts>/firmware.bin`, unsigned.
You can host your own and repoint the `OTA_*` keys. But there's **no auto
rollback** (a bootloader feature OTA can't deliver), so a bad-but-valid build
boot-loops with no recovery unless you have serial access. The controller is a
plain ESP32 (no native USB).

## Gotchas & lessons learned

- **Renames don't change entity ids.** Changing an entity's name (or
  `has_entity_name` output) leaves the existing `entity_id` as first registered.
  Upgraded installs therefore carry legacy ids; resolve by device + role, not by
  id string.
- **`enabled_default` changes don't re-enable existing entities.** Flipping a key
  from disabled- to enabled-by-default only affects *new* registrations; existing
  installs keep the entity disabled until the user enables it (then it takes
  ~30 s for HA to reload it). Deleting + re-adding the integration is the clean
  reset.
- **Entity-id prefixes can diverge** within one install (e.g. an area/rename
  giving a `kuche_` prefix on one entity, `box` vs `box_0`, …). Anything that
  assumes a shared prefix breaks — match by `device_id`.
- **Frontend cards need cache-busting** and `after_dependencies`, not
  `dependencies` (see cards section).
- **The firmware code can be newer than its documented esp-idf pin** — don't
  trust the README's pinned commit for building.
- **Sensors aren't on the port matching the box number.** A box reading its
  temperature from SHT21 port #2 is normal. So the fan/blower **mode** select
  must point its `*_REF_SOURCE` at the sensor the box already uses
  (`BOX_x_TEMP_SOURCE` etc., translated by label into the `fan_ref`/`blower_ref`
  encoding), **not** a hardcoded `offset + box`. The old hardcoding silently
  pointed the unit at an absent sensor → reference read ~0 → output clamped to
  `*_MIN` (e.g. a blower stuck at 10%). See `_resolve_source` in `select.py`.
- **The schedule runs in UTC** (the firmware sets no timezone). The `time`
  entities and the light-phase select convert device-UTC ↔ HA-local (`tz.py`);
  the conversion uses today's date, so it's DST-correct now but a fixed stored
  hour drifts 1h across a DST change until re-written. See FIRMWARE_REVIEW.md #6.
- **Boxes are fixed hardware slots, baked in at firmware build time.** The box
  count is decided by the code generator, not at runtime: `_box_conf` in
  `config_gen/config/SuperGreenOS/Controllers/<variant>/box.cue` is a fixed list
  and `array_len: len(_box_conf)`. The **Controller** variant has 3 entries, the
  **Solo** variant has 1. The generated `keys.h` then `#define`s `BOX_0_*`..
  `BOX_2_*` individually — there is no `BOX_3`, no dynamic allocation. All start
  `enabled = 0`; you *enable/disable* a slot (`BOX_x_ENABLED`), never create one.
  So box structure belongs in the options flow as a fixed 0..`MAX_BOXES` set
  (we use `MAX_BOXES = 3`), not a dynamic add/remove list, and the only
  per-box structural choices that exist are: enable, LED-channel assignment, and
  the sensor/motor **sources**. (Open: moving the source selects into the options
  flow was attempted and didn't work cleanly yet — to be revisited; current state
  keeps them as on-page selects.)

## Contributing

Issues and PRs welcome. Keep the catalog the single source of entity
definitions; if you add device keys, prefer extending `catalog.py` over new
bespoke platform code.
