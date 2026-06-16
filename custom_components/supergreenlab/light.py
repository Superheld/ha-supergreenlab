"""Light platform for SuperGreenLab controllers.

Each LED channel assigned to a box becomes a dimmable light. Brightness maps to
the firmware's ``LED_{n}_DIM`` key (0-100). Note the channel's *actual* output
also depends on the box timer/schedule; this entity controls the intensity
setpoint, mirroring the SuperGreenLab app's per-channel dimmer.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SuperGreenConfigEntry, SuperGreenDataUpdateCoordinator
from .entity import SuperGreenEntity

# Firmware dim range is 0-100; HA brightness is 0-255.
_DIM_MAX = 100


def _dim_to_brightness(dim: int) -> int:
    return round(dim * 255 / _DIM_MAX)


def _brightness_to_dim(brightness: int) -> int:
    return round(brightness * _DIM_MAX / 255)


# Serialize writes to the single-threaded controller; reads are coordinator-driven.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SuperGreenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one light per LED channel assigned to a box."""
    coordinator = entry.runtime_data.fast
    async_add_entities(
        SuperGreenLight(coordinator, led, box)
        for led, box in coordinator.device.led_to_box.items()
    )


class SuperGreenLight(SuperGreenEntity, LightEntity):
    """A dimmable LED channel."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_translation_key = "light"

    def __init__(
        self, coordinator: SuperGreenDataUpdateCoordinator, led: int, box: int
    ) -> None:
        """Bind to an LED channel's dim key."""
        super().__init__(coordinator, box=box)
        self._led = led
        self._key = f"LED_{led}_DIM"
        # Remember the last non-zero level so turn_on can restore it.
        self._last_dim = 100
        self._attr_translation_placeholders = {"led": str(led)}
        self._attr_unique_id = self._unique_id(self._key)

    @property
    def _dim(self) -> int | None:
        return self.coordinator.data.get(self._key)

    @property
    def is_on(self) -> bool | None:
        """Return True when the channel's dim level is above zero."""
        dim = self._dim
        if dim is None:
            return None
        return dim > 0

    @property
    def brightness(self) -> int | None:
        """Return the current brightness on HA's 0-255 scale."""
        dim = self._dim
        if dim is None:
            return None
        return _dim_to_brightness(dim)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set brightness, restoring the previous level if none is given."""
        if ATTR_BRIGHTNESS in kwargs:
            dim = _brightness_to_dim(kwargs[ATTR_BRIGHTNESS])
        else:
            current = self._dim or 0
            dim = current if current > 0 else self._last_dim
        if dim > 0:
            self._last_dim = dim
        await self.coordinator.async_set_int(self._key, dim)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Dim the channel to zero, remembering the previous level."""
        current = self._dim or 0
        if current > 0:
            self._last_dim = current
        await self.coordinator.async_set_int(self._key, 0)
