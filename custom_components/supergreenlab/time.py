"""Time platform for SuperGreenLab controllers.

The firmware stores the light schedule as separate hour and minute keys
(``BOX_x_ON_HOUR`` / ``BOX_x_ON_MIN``). Each pair is merged into a single
HA time entity (HH:MM) for a much nicer UI than four number boxes.
"""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .catalog import TIMES, EntityDef, expand
from .coordinator import SGLDevice, SuperGreenConfigEntry, SuperGreenDataUpdateCoordinator
from .entity import SGLCatalogEntity
from .tz import device_to_local_hm, local_to_device_hm

# Serialize writes to the single-threaded controller; reads are coordinator-driven.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SuperGreenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up catalogued time entities (schedule on/off)."""
    rt = entry.runtime_data
    async_add_entities(
        SuperGreenTime(rt.fast if d.fast else rt.slow, rt.device, d, ph)
        for d, ph in expand(TIMES, rt.device)
    )


class SuperGreenTime(SGLCatalogEntity, TimeEntity):
    """An hour/minute key pair exposed as a single time-of-day value."""

    def __init__(
        self,
        coordinator: SuperGreenDataUpdateCoordinator,
        device: SGLDevice,
        definition: EntityDef,
        placeholders: dict[str, int],
    ) -> None:
        """Resolve both the hour and minute keys."""
        super().__init__(coordinator, device, definition, placeholders)
        # _key holds the hour key; key2 holds the minute key.
        self._minute_key = definition.key2.format(**placeholders)

    @property
    def native_value(self) -> time | None:
        """Return the schedule time, or None if either part is missing."""
        hour = self._raw
        minute = (
            self.coordinator.data.get(self._minute_key)
            if self.coordinator.data
            else None
        )
        if hour is None or minute is None:
            return None
        # The firmware stores the schedule in UTC; show it in HA's local time.
        local_hour, local_minute = device_to_local_hm(hour, minute)
        try:
            return time(hour=local_hour, minute=local_minute)
        except ValueError:
            return None

    async def async_set_value(self, value: time) -> None:
        """Write the hour and minute back to the controller (local -> UTC)."""
        hour, minute = local_to_device_hm(value.hour, value.minute)
        await self.coordinator.async_set_int(self._key, hour)
        await self.coordinator.async_set_int(self._minute_key, minute)
