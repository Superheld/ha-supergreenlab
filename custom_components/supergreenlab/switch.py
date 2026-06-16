"""Switch platform for SuperGreenLab controllers."""

from __future__ import annotations

import time
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .catalog import SWITCHES, expand
from .coordinator import SuperGreenConfigEntry, SuperGreenDataUpdateCoordinator
from .entity import SGLCatalogEntity, SuperGreenEntity

# "Sunglasses" mode dims the box's lights for this many seconds after activation
# (matches the firmware's window in led.c).
_SUNGLASSES_DURATION = 1200


# Serialize writes to the single-threaded controller; reads are coordinator-driven.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SuperGreenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up catalogued switches plus the per-box sunglasses switch."""
    rt = entry.runtime_data
    entities: list[SwitchEntity] = [
        SuperGreenSwitch(rt.fast if d.fast else rt.slow, rt.device, d, ph)
        for d, ph in expand(SWITCHES, rt.device)
    ]
    entities.extend(SuperGreenSunglassesSwitch(rt.fast, box) for box in rt.device.boxes)
    async_add_entities(entities)


class SuperGreenSwitch(SGLCatalogEntity, SwitchEntity):
    """A catalogued boolean key (0/1)."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    @property
    def is_on(self) -> bool | None:
        """Return True when the raw value is 1."""
        raw = self._raw
        return None if raw is None else raw == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set the key to 1."""
        await self._write(1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Set the key to 0."""
        await self._write(0)


class SuperGreenSunglassesSwitch(SuperGreenEntity, SwitchEntity):
    """Box "sunglasses" work-light: dims the lights for ~20 min when on.

    The firmware stores ``BOX_x_LED_DIM`` as a unix timestamp and dims the box's
    lights while it is less than 20 min old. We expose that as a switch: turning
    it on stamps the current time, turning it off clears it, and the state
    reflects whether the window is still active (so it self-clears after ~20 min
    on the next poll). Handy as an automation target/condition.
    """

    _attr_icon = "mdi:sunglasses"

    def __init__(
        self, coordinator: SuperGreenDataUpdateCoordinator, box: int
    ) -> None:
        """Bind to a box's sunglasses timestamp key."""
        super().__init__(coordinator, box=box)
        self._box = box
        self._key = f"BOX_{box}_LED_DIM"
        self._attr_name = "Sunglasses mode"
        self._attr_unique_id = self._unique_id(f"BOX_{box}_SUNGLASSES")

    @property
    def is_on(self) -> bool | None:
        """Return True while the dim window is still active."""
        data = self.coordinator.data
        ts = data.get(self._key) if data else None
        if ts is None:
            return None
        return (time.time() - ts) < _SUNGLASSES_DURATION

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Activate the dim window by stamping the current time."""
        await self.coordinator.async_set_int(self._key, int(time.time()))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Cancel the dim window."""
        await self.coordinator.async_set_int(self._key, 0)
