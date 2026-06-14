"""Timezone conversion for the firmware's schedule times.

The firmware never sets a timezone (it only runs SNTP), so it evaluates the
schedule keys (``BOX_x_ON_HOUR`` / ``OFF_HOUR`` …) in **UTC**. We present and
accept those as the user's *local* time of day instead, so the on/off times in
Home Assistant match the wall clock.

Caveat: the firmware hour is DST-blind. We convert using today's date, so the
mapping is correct now but a fixed stored UTC hour will appear shifted by one
hour after a DST transition until it is re-written. Only a firmware-side TZ fix
tracks DST automatically (see FIRMWARE_REVIEW.md).
"""

from __future__ import annotations

import homeassistant.util.dt as dt_util


def device_to_local_hm(hour: int, minute: int) -> tuple[int, int]:
    """Convert a UTC time-of-day from the device to HA's local time-of-day."""
    utc = dt_util.utcnow().replace(hour=hour, minute=minute, second=0, microsecond=0)
    local = dt_util.as_local(utc)
    return local.hour, local.minute


def local_to_device_hm(hour: int, minute: int) -> tuple[int, int]:
    """Convert a local time-of-day to the UTC time-of-day the device stores."""
    local = dt_util.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    utc = dt_util.as_utc(local)
    return utc.hour, utc.minute
