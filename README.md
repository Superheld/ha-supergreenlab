# SuperGreenLab Controller for Home Assistant

Control and monitor a [SuperGreenController](https://github.com/supergreenlab/SuperGreenOS)
(running SuperGreenOS) from Home Assistant — fully local, over your LAN.
No cloud account, no MQTT broker, no firmware changes.

## What you get

For each grow box configured on your controller:

- 💡 **Lights** — brightness per LED channel
- 🌡️ **Climate** — temperature, humidity, VPD and CO₂ sensors
- 🌀 **Ventilation** — exhaust / intake fan speeds and curve limits
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
- **Make a fan follow temperature, time, humidity, …:** use the box's
  **Intake/Exhaust fan mode** control (Manual / Timer / Temperature / Humidity /
  VPD / CO₂). It sets the reference and a sensible range in one step; fine-tune
  the range and min/max afterwards. (A raw *source* select is available
  disabled-by-default for power users.)

## Troubleshooting

- **Integration not listed** after install → restart Home Assistant.
- **“Failed to connect”** → check the IP and that Home Assistant can reach the
  controller on your network.
- **Anything else** → *Settings → System → Logs* (filter `supergreenlab`), or
  open an [issue](https://github.com/Superheld/ha-supergreenlab/issues).

## Bundled Lovelace card

The integration ships a custom **`sgl-fan-card`** and auto-loads it — no separate
HACS plugin and no manual dashboard resource needed. It's a *mode-aware* card for
one fan/blower: it shows the mode plus only the settings relevant to that mode
(Manual → speed; Timer → speed range; Temperature/Humidity/VPD/CO₂ → reference
range + speed range).

Add it from the card picker (**Add card → SuperGreenLab Fan Card**) and pick the
fan's **Mode** entity in the editor — that's it. The reference and speed entities
are derived automatically from the mode entity.

Minimal YAML (just the mode entity; replace with your controller's name):

```yaml
type: custom:sgl-fan-card
mode: select.supergreencontroller_box_0_intake_fan_mode
```

You can still override any derived entity or the title explicitly:

```yaml
type: custom:sgl-fan-card
title: Intake fan
mode: select.supergreencontroller_box_0_intake_fan_mode
speed_min: number.supergreencontroller_box_0_intake_fan_speed_min
```

## Example dashboard

[`dashboards/example-box.yaml`](dashboards/example-box.yaml) is a ready-to-paste
Lovelace view for one box, built from native cards. It bundles each dependent
group into one card — e.g. a fan's **mode + reference range + speed range**
together — so you don't have to assemble the entities by hand. Adjust the entity
IDs to your device name/box.

---

Building on or contributing to this integration? See
[DEVELOPMENT.md](DEVELOPMENT.md).
