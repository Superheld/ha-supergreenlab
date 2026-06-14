"""Switch platform for SuperGreenLab controllers."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .catalog import SWITCHES, EntityDef, expand
from .coordinator import SuperGreenConfigEntry, SuperGreenDataUpdateCoordinator, SGLDevice
from .entity import SGLCatalogEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SuperGreenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up catalogued switches."""
    rt = entry.runtime_data
    async_add_entities(
        SuperGreenSwitch(rt.fast if d.fast else rt.slow, rt.device, d, ph)
        for d, ph in expand(SWITCHES, rt.device)
    )


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
