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

### Configuration (device page → Configuration)

Everything the controller itself stores is mirrored as a config entity — the
device stays the single source of truth, nothing is duplicated in the
integration options.

| Platform | Entity | Firmware key |
|---|---|---|
| select | LED → box assignment | `LED_n_BOX` (reloads to add/remove the light) |
| select | Timer mode, sensor sources, fan sources | `BOX_x_TIMER_TYPE`, `*_SOURCE` (decoded to readable options) |
| switch | Box enabled, LED fast PWM, motor curve | `BOX_x_ENABLED`, `LEDS_FASTMODE`, `MOTORS_CURVE` |
| number | Schedule, ventilation curve, watering, season, calibration, motors, valve | `BOX_x_ON_HOUR` … and many more |

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

The goal is to get the `supergreenlab` folder into your HA config directory so
the final path is:

```
config/custom_components/supergreenlab/manifest.json
```

Pick whichever transfer method fits your setup, then restart Home Assistant.

### HA OS / Supervised — via Samba (easiest)

1. Install the **Samba share** app: *Settings → Apps* (formerly "Add-ons") →
   App Store → **Samba share** → install, set a username/password, start.
2. On your computer, open the network share `\\homeassistant\config`
   (Windows) or `smb://homeassistant.local` → `config` (macOS Finder →
   *Go → Connect to Server*).
3. Unpack the release archive locally — you get `custom_components/supergreenlab/`.
4. In the `config` share, create a `custom_components` folder if it doesn't
   exist, and copy the **`supergreenlab`** folder into it.
5. Restart Home Assistant: *Settings → System → ⟳ (top right) → Restart*.

### HA OS / Supervised — via SSH terminal

Install the **Advanced SSH & Web Terminal** app. Put the archive in the
`share` share, then:

```bash
cd /config && mkdir -p custom_components
tar xzf /share/supergreenlab-ha-*.tar.gz -C /config
ls custom_components/supergreenlab/manifest.json   # sanity check
```

Restart Home Assistant afterwards.

### HACS (custom repository)

Add this repository as a **custom repository** in HACS (category:
*Integration*), install it, then restart Home Assistant.

### HA Container / Core (manual)

Copy `custom_components/supergreenlab` into the `config/custom_components/`
directory of your installation and restart Home Assistant.

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
