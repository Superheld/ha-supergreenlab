"""Number platform for SuperGreenLab controllers."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .catalog import NUMBERS, EntityDef, expand
from .coordinator import SuperGreenConfigEntry, SuperGreenDataUpdateCoordinator, SGLDevice
from .entity import SGLCatalogEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SuperGreenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up catalogued numbers."""
    rt = entry.runtime_data
    async_add_entities(
        SuperGreenNumber(rt.fast if d.fast else rt.slow, rt.device, d, ph)
        for d, ph in expand(NUMBERS, rt.device)
    )


class SuperGreenNumber(SGLCatalogEntity, NumberEntity):
    """A catalogued writable integer."""

    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: SuperGreenDataUpdateCoordinator,
        device: SGLDevice,
        definition: EntityDef,
        placeholders: dict[str, int],
    ) -> None:
        """Apply number bounds and unit."""
        super().__init__(coordinator, device, definition, placeholders)
        self._attr_native_min_value = definition.min
        self._attr_native_max_value = definition.max
        self._attr_native_step = definition.step
        self._attr_native_unit_of_measurement = definition.unit

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        raw = self._raw
        return None if raw is None else float(raw)

    async def async_set_native_value(self, value: float) -> None:
        """Write the new value to the controller."""
        await self._write(int(value))
