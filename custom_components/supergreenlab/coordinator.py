"""Device discovery and polling coordinators for SuperGreenLab controllers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SuperGreenAPI, SuperGreenApiError, SuperGreenAuthError
from .const import (
    CONF_FAST_INTERVAL,
    DOMAIN,
    FAST_SCAN_INTERVAL,
    KEY_BOX_ENABLED,
    KEY_CLIENT_ID,
    KEY_DEVICE_NAME,
    KEY_LED_BOX,
    MAX_BOXES,
    MAX_LED_CHANNELS,
    SLOW_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class SGLDevice:
    """The detected layout of a controller: which boxes and LEDs are live."""

    client_id: str
    name: str
    boxes: list[int] = field(default_factory=list)
    led_to_box: dict[int, int] = field(default_factory=dict)

    def leds_for_box(self, box: int) -> list[int]:
        """Return the LED channels assigned to a given box."""
        return [led for led, b in self.led_to_box.items() if b == box]


@dataclass
class RuntimeData:
    """Everything a config entry needs at runtime."""

    api: SuperGreenAPI
    device: SGLDevice
    fast: SuperGreenDataUpdateCoordinator
    slow: SuperGreenDataUpdateCoordinator


type SuperGreenConfigEntry = ConfigEntry[RuntimeData]


async def async_detect_device(api: SuperGreenAPI) -> SGLDevice:
    """Probe the controller to learn which boxes and LED channels are active."""
    client_id = await api.get_str(KEY_CLIENT_ID)
    if not client_id:
        raise SuperGreenApiError("Controller did not report a client id")
    name = await api.get_str(KEY_DEVICE_NAME) or "SuperGreenController"

    boxes: list[int] = []
    for box in range(MAX_BOXES):
        if await api.get_int(KEY_BOX_ENABLED.format(box=box)) == 1:
            boxes.append(box)

    led_to_box: dict[int, int] = {}
    for led in range(MAX_LED_CHANNELS):
        led_box = await api.get_int(KEY_LED_BOX.format(led=led))
        if led_box is not None and led_box in boxes:
            led_to_box[led] = led_box

    return SGLDevice(client_id=client_id, name=name, boxes=boxes, led_to_box=led_to_box)


class SuperGreenDataUpdateCoordinator(DataUpdateCoordinator[dict[str, int | None]]):
    """Polls a fixed set of integer keys on an interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: SuperGreenAPI,
        device: SGLDevice,
        keys: list[str],
        interval: timedelta,
        label: str,
    ) -> None:
        """Initialise a coordinator for a set of keys."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {label}",
            update_interval=interval,
        )
        self.api = api
        self.device = device
        self._keys = keys

    async def _async_update_data(self) -> dict[str, int | None]:
        """Read every key sequentially (the ESP32 httpd is tiny)."""
        data: dict[str, int | None] = dict(self.data or {})
        try:
            for key in self._keys:
                data[key] = await self.api.get_int(key)
        except SuperGreenAuthError as err:
            # Credentials became invalid (e.g. the device's auth token changed);
            # trigger the reauth flow instead of just marking entities offline.
            raise ConfigEntryAuthFailed(str(err)) from err
        except SuperGreenApiError as err:
            raise UpdateFailed(str(err)) from err
        return data

    async def async_set_int(self, key: str, value: int) -> None:
        """Write a key and optimistically update the cached value."""
        try:
            await self.api.set_int(key, value)
        except SuperGreenApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
                translation_placeholders={"key": key, "error": str(err)},
            ) from err
        data = dict(self.data or {})
        data[key] = value
        self.async_set_updated_data(data)


def build_coordinators(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api: SuperGreenAPI,
    device: SGLDevice,
) -> tuple[SuperGreenDataUpdateCoordinator, SuperGreenDataUpdateCoordinator]:
    """Create the fast (live) and slow (config) coordinators from the catalog."""
    # Imported here to avoid a circular import at module load.
    from .catalog import ALL_DEFS, expand

    fast_keys: set[str] = set()
    slow_keys: set[str] = set()
    for d, ph in expand(ALL_DEFS, device):
        target = fast_keys if d.fast else slow_keys
        target.add(d.key.format(**ph))
        if d.key2 is not None:
            target.add(d.key2.format(**ph))

    # LED dim levels back the light entities and should stay fresh.
    for led in device.led_to_box:
        fast_keys.add(f"LED_{led}_DIM")

    # The per-box "sunglasses" timestamp backs the work-light switch; poll it
    # fast so the switch reflects the ~20 min window decaying back to off.
    for box in device.boxes:
        fast_keys.add(f"BOX_{box}_LED_DIM")

    # The simulated-season timestamp backs the read-only "Season date" sensor;
    # it advances slowly, so the config (slow) coordinator is enough.
    for box in device.boxes:
        slow_keys.add(f"BOX_{box}_SIMULATED_TIME")

    fast_seconds = entry.options.get(
        CONF_FAST_INTERVAL, int(FAST_SCAN_INTERVAL.total_seconds())
    )
    fast = SuperGreenDataUpdateCoordinator(
        hass, entry, api, device, sorted(fast_keys),
        timedelta(seconds=fast_seconds), "live"
    )
    slow = SuperGreenDataUpdateCoordinator(
        hass, entry, api, device, sorted(slow_keys), SLOW_SCAN_INTERVAL, "config"
    )
    return fast, slow
