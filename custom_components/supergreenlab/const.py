"""Constants for the SuperGreenLab Controller integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "supergreenlab"

MANUFACTURER = "SuperGreenLab"
MODEL = "SuperGreenController"

# The controller is a tiny ESP32 webserver; keep the polling gentle.
# Live readings refresh often; config values rarely change, so poll them slowly.
FAST_SCAN_INTERVAL = timedelta(seconds=30)
SLOW_SCAN_INTERVAL = timedelta(seconds=180)

CONF_HOST = "host"
CONF_FAST_INTERVAL = "fast_interval"

# Number of grow boxes and LED channels a controller can expose. These are the
# hard limits baked into the firmware; we probe each index to find what is
# actually wired up on a given device.
MAX_BOXES = 3
MAX_LED_CHANNELS = 6

# Key used as the stable unique id for the device (the chip MAC).
KEY_CLIENT_ID = "BROKER_CLIENTID"
KEY_DEVICE_NAME = "DEVICE_NAME"
KEY_WIFI_IP = "WIFI_IP"
KEY_STATE = "STATE"
KEY_N_RESTARTS = "N_RESTARTS"

# A box is exposed only when this key reads 1.
KEY_BOX_ENABLED = "BOX_{box}_ENABLED"

# LED channel -> box assignment (-1 means the channel is not assigned).
KEY_LED_BOX = "LED_{led}_BOX"
KEY_LED_DIM = "LED_{led}_DIM"

# VPD is stored as deci-Pascal/10 in the firmware (value = Pa / 10), so the
# kPa value humans expect is the raw reading divided by 100.
VPD_DIVISOR = 100.0
