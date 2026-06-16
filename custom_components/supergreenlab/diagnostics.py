"""Diagnostics for the SuperGreenLab Controller integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import SuperGreenConfigEntry

# Keys whose values must never appear in a shared diagnostics dump.
TO_REDACT = {
    "auth",
    "client_id",
    "HTTPD_AUTH",
    "SIGNING_KEY",
    "WIFI_SSID",
    "WIFI_PASSWORD",
    "WIFI_AP_SSID",
    "WIFI_AP_PASSWORD",
    "BROKER_URL",
    "BROKER_CLIENTID",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SuperGreenConfigEntry
) -> dict[str, Any]:
    """Return a redacted snapshot of the entry, device and polled values."""
    rt = entry.runtime_data
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "device": async_redact_data(
            {
                "name": rt.device.name,
                "client_id": rt.device.client_id,
                "boxes": rt.device.boxes,
                "led_to_box": rt.device.led_to_box,
            },
            TO_REDACT,
        ),
        "fast_data": async_redact_data(dict(rt.fast.data or {}), TO_REDACT),
        "slow_data": async_redact_data(dict(rt.slow.data or {}), TO_REDACT),
    }
