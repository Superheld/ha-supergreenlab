# SuperGreenLab Controller for Home Assistant

Control and monitor a [SuperGreenController](https://github.com/supergreenlab/SuperGreenOS)
(running SuperGreenOS) from Home Assistant — fully local, over your LAN.
No cloud account, no MQTT broker, no firmware changes.

## What you get

For each grow box configured on your controller:

- 💡 **Lights** — brightness per LED channel
- 🌡️ **Climate** — temperature, humidity, VPD and CO₂ sensors
- 🌀 **Ventilation** — fan (in-box circulation) and blower (exhaust) speeds and
  curve limits
- ⏰ **Light schedule** — on/off times (as simple HH:MM controls)
- ⚙️ Plus watering, weight, LED spectrum, sensor sources and the controller's
  other settings, and a restart button

The controller is the parent Home Assistant **device**, and **each enabled box is
its own sub-device** under it ("Box 0", "Box 1", …). So a box's entities are
grouped together automatically, their names stay short ("Temperature", "Fan
mode"), and you can assign each box to its own **Area**. Controller-wide things
(restart, state, valve, motors) live on the controller device.

## Installation (HACS)

> Requires [HACS](https://hacs.xyz). If you don't have it yet, install HACS
> first by following its documentation.

1. Open **HACS** → top-right **⋮ → Custom repositories**.
2. Repository: `https://github.com/Superheld/ha-supergreenlab` — Type:
   **Integration** → **Add**.
3. Search for **SuperGreenLab Controller** → **Download**.
4. **Restart Home Assistant**.

<details>
<summary>Install without HACS</summary>

On Home Assistant OS / Supervised, use the **Terminal & SSH** app:

```bash
cd /tmp && rm -rf sgl && git clone https://github.com/Superheld/ha-supergreenlab.git sgl
mkdir -p /config/custom_components
cp -r /tmp/sgl/custom_components/supergreenlab /config/custom_components/
```

Then restart Home Assistant. To update later, run the same commands again.
On HA Container / Core, copy `custom_components/supergreenlab` into your
`config/custom_components/` folder instead.
</details>

## Setup

1. **Settings → Devices & Services → Add Integration → SuperGreenLab Controller**.
2. Enter the controller's IP address (e.g. `192.168.1.50`).
3. Leave username / password blank — they're only needed if you set an auth
   token on the device.

The controller's chip MAC is used as its unique id, so a changing DHCP address
won't create duplicates — just re-run setup with the new IP.

### Configure your boxes

Open **Configure** on the integration → **Device layout** to enable the boxes
you use and assign each LED channel to a box. Sensor sources, schedules, fan
curves and the rest appear as settings on the controller's device page
(under *Configuration*).

> 💡 Tip: assign each **box device** to a Home Assistant **Area** to place it in
> its physical room.

## What the entities do

Per box (the most-used ones; many advanced/diagnostic entities exist too but are
disabled by default — enable them from the device page if you need them):

**Lights**
- *Light 0/1/2 …* — brightness (0–100 %) of each LED channel assigned to the box.
- *Light on* — read-only: whether the box light is currently on.
- *Light output* — read-only: the % the schedule/season currently commands.

**Light schedule**
- *Timer mode* — the main light-driving switch: **Manual** (just the brightness,
  no schedule), **On/Off schedule** (on/off at fixed times), **Season** (day
  length follows a simulated, slowly-shifting season). **Season is a firmware
  feature the official app doesn't offer** — here you can pick it, set the season
  parameters below, and press *Start season* to begin.
- *Light on time / off time* — the actual schedule times (shown in your local
  time; see the sync note below).
- *Season start month / day*, *Season duration*, *Season sim days*, *Start season*
  (button) — the Season-mode parameters and the “start it now” trigger (see
  **Season mode** below).
- *Season date* — read-only: the simulated calendar date the box is currently at
  while a season runs (shows where the season has progressed to).

**Climate (read-only)**
- *Temperature, Humidity, VPD, CO₂* (and *Weight* if enabled) — the box's live
  readings, taken from the sensor each *…source* points at.

**Climate sources**
- *Temperature/Humidity/VPD/CO₂ source* — which physical sensor (at which port)
  feeds that reading for this box.

**Ventilation**
- *Fan mode / Blower mode* — what the unit follows: **Manual**, **Timer**
  (coupled to the light), or **Temperature / Humidity / VPD / CO₂** (auto-curve).
- *Fan/Blower speed min / max* — the duty range (% when the reference is at its
  low / high end).
- *Fan/Blower reference from / to* — the reference range the curve ramps over.
- *Fan / Blower* — read-only: the unit's current duty %.

**Other**
- *Sunglasses mode* (switch) — dims the box lights ~20 min for working inside;
  self-clears.

Device-wide diagnostics: *State*, *Restarts*, and *…present* flags (which i2c
sensors the controller detects).

## Season mode

**Season** is a firmware light mode the official app doesn't expose — so it's
little-known, but it's real and works. Instead of a fixed on/off schedule, the
light follows a **simulated, slowly-shifting season**: a soft daily sunrise →
midday → sunset curve whose day length drifts over your grow, like the sun does
across real months. It's compressed into your actual grow length.

Set it via the box's *Timer mode* → **Season**, then:

- *Season start month / day* — which calendar date the simulated season starts at
  (e.g. April 1).
- *Season duration* — how many days of season to simulate (e.g. 215 → spring into
  autumn).
- *Season sim days* — over how many **real** days to compress that (= your grow
  length, e.g. 75).
- *Start season* (button) — press to begin from now.
- *Season date* (read-only) — shows the simulated date the box is currently at, so
  you can watch the season progress.

Example: start *April 1*, duration *120*, sim days *60* → over 60 real days your
plants experience the April→August light progression, 2× compressed.

> Heads-up: like the on/off schedule, Season runs on the controller's clock,
> which has no timezone — its daily peak lands at solar noon in **UTC**, so it's
> shifted by your UTC offset until the firmware gains proper timezone support.

## App and Home Assistant don't sync live

Both the official app and this integration talk to the **same controller**
independently — there is no live link between them. What that means in practice:

- **No status sync.** The app's grow-phase label (*Vegetative/Bloom/Auto*) lives
  only inside the app (and its cloud); it isn't stored on the controller, so Home
  Assistant can't read or set it. Change the schedule from HA and the app keeps
  showing its last-set phase. (HA derives its own *Light phase* from the times.)
- **Changes propagate by polling, not live push — that works, it's just not
  instant.** A change made in HA reaches the controller right away; a change made
  elsewhere shows up in HA on its next config poll (up to a few minutes). Nothing
  is broken here, it just isn't real-time.
- **The app only *sets*, it doesn't show what's set.** The app's schedule screen
  lets you enter times but doesn't display the controller's currently-active
  schedule — so you can't read back the real values there. Home Assistant does
  show the live device values, so use HA to see what's actually set.
- **The hour can read differently in each.** The controller's firmware runs the
  schedule in **UTC** (it sets no timezone). HA converts that to your local time
  so the times match your wall clock; the app shows the raw number. So the same
  schedule can appear as e.g. *21:00* in the app and *23:00* in HA — HA's is the
  real switching time. The clean fix belongs in the firmware (see
  [DEVELOPMENT.md](DEVELOPMENT.md)); until then, set the schedule from **one**
  place to avoid confusion.

## Tips

- **Light brightness** sets each channel's intensity; the light's actual output
  still follows the box's on/off schedule.
- **Make a fan or blower follow temperature, time, humidity, …:** use the box's
  **Fan/Blower mode** control (Manual / Timer / Temperature / Humidity /
  VPD / CO₂). It sets the reference and a sensible range in one step; fine-tune
  the range and min/max afterwards. (A raw *source* select is available
  disabled-by-default for power users.)
- **Sensor source dropdowns** list only the sensors the controller detects as
  present at their ports — not every theoretical option. If detection finds none
  of a kind, all are shown so you can still set it up.
- **Sunglasses mode** (a switch per box) dims the box's lights for ~20 minutes so
  you can work inside without being blinded; it clears itself afterwards. Handy in
  automations — e.g. turn it on when a door sensor opens.

## Troubleshooting

- **Integration not listed** after install → restart Home Assistant.
- **“Failed to connect”** → check the IP and that Home Assistant can reach the
  controller on your network.
- **Anything else** → *Settings → System → Logs* (filter `supergreenlab`), or
  open an [issue](https://github.com/Superheld/ha-supergreenlab/issues).

## Bundled Lovelace cards

The integration ships for easy configuration custom *mode-aware* cards and auto-loads them — no separate
HACS plugin and no manual dashboard resource. Each card needs only one anchor
entity (its **mode**); the rest is resolved automatically from the same box. 

### `sgl-fan-card`

For a **fan or blower** — point it at the unit's mode select. Shows the mode plus
only the relevant settings (Manual → speed; Timer → just the speed range, since
the unit follows the light schedule automatically; Temperature/Humidity/VPD/CO₂ →
current reading + reference range + speed), and the current speed.

```yaml
# Fan (in-box circulation)
type: custom:sgl-fan-card
mode: select.supergreencontroller_box_0_fan_mode
```
```yaml
# Blower (exhaust) — same card, blower mode entity
type: custom:sgl-fan-card
mode: select.supergreencontroller_box_0_blower_mode
```

### `sgl-light-card`

The box's light **scheduler** (like the app's schedule screen) — point it at the
box **Timer mode** select. Shows the mode (Manual / On/Off / Season) and *only*
the inputs that mode needs: in **On/Off** the on/off times; in **Season** the
current season date plus the season parameters and the *Start season* button.
Per-channel brightness isn't here — those are the box's `light` entities (use
them on the device page or a plain entities card).

```yaml
type: custom:sgl-light-card
mode: select.supergreencontroller_box_0_timer_mode
```

### `sgl-box-card`

A box's **hardware setup** — the one-time wiring choices: which sensor source
feeds each metric (*Climate sensors*) and what spectrum each LED channel is
(*Light spectrum*). It deliberately leaves out live values, fan modes and the
schedule — those have their own cards. Unlike the other cards it's anchored with
`entity:` (any entity of the box, e.g. its timer mode select), not `mode:`.

```yaml
type: custom:sgl-box-card
entity: select.supergreencontroller_box_0_timer_mode
```

Any derived entity or the title can be overridden explicitly in the YAML.

## Example dashboard

[`dashboards/example-box.yaml`](dashboards/example-box.yaml) is a ready-to-paste
Lovelace view for one box, built from native cards. It bundles each dependent
group into one card — e.g. a fan's **mode + reference range + speed range**
together — so you don't have to assemble the entities by hand. Adjust the entity
IDs to your device name/box.

---

Building on or contributing to this integration? See
[DEVELOPMENT.md](DEVELOPMENT.md).
