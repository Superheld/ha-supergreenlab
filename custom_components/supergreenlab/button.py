"""Button platform for SuperGreenLab controllers."""

from __future__ import annotations

import time

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .catalog import BUTTONS, expand
from .coordinator import SuperGreenConfigEntry
from .entity import SGLCatalogEntity

# Serialize writes to the single-threaded controller; reads are coordinator-driven.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SuperGreenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up catalogued buttons."""
    rt = entry.runtime_data
    async_add_entities(
        SuperGreenButton(rt.slow, rt.device, d, ph) for d, ph in expand(BUTTONS, rt.device)
    )


class SuperGreenButton(SGLCatalogEntity, ButtonEntity):
    """A momentary action that writes 1 to its key."""

    async def async_press(self) -> None:
        """Trigger the action: write the current unix time, or 1."""
        value = int(time.time()) if self._def.press_now else 1
        await self.coordinator.api.set_int(self._key, value)
