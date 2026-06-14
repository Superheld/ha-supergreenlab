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

Everything lives on a single Home Assistant **device** (the controller). A
*box* is a logical slot on the controller, shown as a name prefix (“Box 0 …”).

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

> 💡 Tip: add a box's entities to a Home Assistant **Area** to group them by
> physical space.

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
the inputs that mode needs: in **On/Off** a **Light phase** picker (*Vegetative /
Bloom / Auto*, the app's grow-phase presets — choosing one fills sensible on/off
times; editing a time by hand switches it to *Custom*) plus the on/off times; in
**Season** the season settings. Per-channel brightness isn't here — those are
the box's `light` entities (use them on the device page or a plain entities card).

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
