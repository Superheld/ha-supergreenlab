# SuperGreenLab Controller — Home Assistant Integration

A local-polling Home Assistant integration for the
[SuperGreenController](https://github.com/supergreenlab/SuperGreenOS) running
SuperGreenOS. It talks to the controller's built-in HTTP key/value API on your
LAN — no cloud, no MQTT broker, no firmware changes required.

## What it does

On setup the integration probes the controller, detects which grow boxes are
enabled and which LED channels are assigned to them, and creates entities
accordingly. The whole entity set is defined declaratively in `catalog.py`.

Two coordinators poll the device: **live** readings (temperature, humidity,
fan speeds, …) every 30 s by default, and **config** values every 180 s
(they also update instantly when you change them from HA). The live interval is
adjustable via the integration's options.

### Controls & sensors (dashboard)

| Platform | Entity | Firmware key | Notes |
|---|---|---|---|
| light | Light 0..n | `LED_n_DIM` | per assigned LED channel, brightness 0–100 |
| sensor | Temperature / Humidity / VPD / CO2 | `BOX_x_TEMP/HUMI/VPD/CO2` | VPD in kPa (raw ÷ 100) |
| sensor | Exhaust / Intake fan, Light output | `BOX_x_BLOWER_DUTY` / `FAN_DUTY` / `TIMER_OUTPUT` | actual %, read-only |
| binary_sensor | Light on | `BOX_x_TIMER_OUTPUT` | on when schedule output > 0 |
| time | Light on / off time | `BOX_x_ON_HOUR`+`ON_MIN`, `OFF_HOUR`+`OFF_MIN` | hour & minute merged into one HH:MM control |

### Device layout (integration options)

The structural choices — **which boxes are enabled** and **which LED channel
belongs to which box** — live in the integration's options, not as entities:
they decide which entities exist, are rarely changed, and would otherwise
clutter the device with controls for boxes/channels you don't use.

*Settings → Devices & Services → SuperGreenLab Controller → Configure →
**Device layout*** lets you toggle boxes and assign each LED channel. The chosen
layout is written to the controller (the single source of truth) and the entities
are rebuilt afterwards.

### Configuration (device page → Configuration)

Operational settings the controller stores are mirrored as config entities —
the device stays the source of truth, nothing is duplicated.

| Platform | Entity | Firmware key |
|---|---|---|
| select | Timer mode, sensor sources, fan sources | `BOX_x_TIMER_TYPE`, `*_SOURCE` (decoded to readable options) |
| switch | LED fast PWM, motor curve | `LEDS_FASTMODE`, `MOTORS_CURVE` |
| number | Ventilation curve, watering, season, calibration, motors, valve | many |

Disabled-by-default entities exist for less common keys (per-port leaf offsets,
load-cell calibration, valve, motors) — enable them in the entity settings when
you need them.

Diagnostics: `STATE`, `N_RESTARTS`, sensor `*_PRESENT` flags.

> **Light model:** brightness sets the per-channel intensity (`LED_n_DIM`),
> exactly like the SuperGreenLab app's dimmer. Actual output also depends on the
> box's on/off schedule. To gang several channels into one slider, create a
> native **Light Group** helper in Home Assistant.

> **Sensor sources:** each box selects which physical sensor feeds it. The
> `*_SOURCE` selects show decoded names like "SHT21 temperature on port #1". The
> integer encoding is baked from the firmware config (`sources.py`).

## Installation

### HACS (recommended)

Easiest to install *and* to keep updated — new releases show up in HACS with a
one-click update.

> Requires [HACS](https://hacs.xyz). If you don't have it yet, install HACS
> first by following its own documentation.

Then add this integration:

1. Open **HACS** → top-right **⋮ → Custom repositories**.
2. Repository: `https://github.com/Superheld/ha-supergreenlab` — Type:
   **Integration** → **Add**.
3. Search for **SuperGreenLab Controller** in HACS → open → **Download**.
4. **Restart Home Assistant** when prompted.

### Manual / git (no HACS)

Get the `supergreenlab` folder into your config directory so the final path is
`config/custom_components/supergreenlab/manifest.json`, then restart HA.

On HA OS / Supervised, the simplest no-copy way is the **Terminal & SSH** app:

```bash
cd /tmp && rm -rf sgl && git clone https://github.com/Superheld/ha-supergreenlab.git sgl
mkdir -p /config/custom_components
cp -r /tmp/sgl/custom_components/supergreenlab /config/custom_components/
ls /config/custom_components/supergreenlab/manifest.json   # sanity check
```

To update later, re-run the same block and restart. On HA Container / Core,
copy the `custom_components/supergreenlab` folder into your `config/custom_components/`
directory instead.

## Setup

1. **Settings → Devices & Services → Add Integration → SuperGreenLab Controller**
2. Enter the controller's IP address (e.g. `192.168.1.2`).
3. Username/password are only needed if you set an `HTTPD_AUTH` token on the
   device. By default the API is open on the local network and you can leave
   them blank.

The controller's chip MAC (`BROKER_CLIENTID`) is used as the unique device id,
so a changing DHCP address won't create duplicates — just re-run setup with the
new IP.

## Troubleshooting

- **Integration doesn't appear** in the Add Integration list → the folder is in
  the wrong place (must be exactly `config/custom_components/supergreenlab/manifest.json`)
  or Home Assistant wasn't restarted.
- **"Failed to connect"** → check that the Home Assistant host can reach the
  controller's IP (same network), and that the IP is correct.
- **Other errors** → check *Settings → System → Logs* for entries from
  `supergreenlab`.

## How it talks to the controller

```
GET  http://<ip>/i?k=KEY          -> integer value
POST http://<ip>/i?k=KEY&v=123    -> set integer
GET  http://<ip>/s?k=KEY          -> string value
GET  http://<ip>/fs/config.json   -> gzipped key manifest
```

This is the same local API the official app uses.
