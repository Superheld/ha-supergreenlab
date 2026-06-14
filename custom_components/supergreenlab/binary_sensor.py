"""Binary sensor platform for SuperGreenLab controllers."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .catalog import BINARY_SENSORS, EntityDef, expand
from .coordinator import SuperGreenConfigEntry, SuperGreenDataUpdateCoordinator, SGLDevice
from .entity import SGLCatalogEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SuperGreenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up catalogued binary sensors."""
    rt = entry.runtime_data
    async_add_entities(
        SuperGreenBinarySensor(rt.fast if d.fast else rt.slow, rt.device, d, ph)
        for d, ph in expand(BINARY_SENSORS, rt.device)
    )


class SuperGreenBinarySensor(SGLCatalogEntity, BinarySensorEntity):
    """A catalogued on/off value (true when the raw value is non-zero)."""

    def __init__(
        self,
        coordinator: SuperGreenDataUpdateCoordinator,
        device: SGLDevice,
        definition: EntityDef,
        placeholders: dict[str, int],
    ) -> None:
        """Apply binary-sensor metadata."""
        super().__init__(coordinator, device, definition, placeholders)
        self._attr_device_class = definition.device_class

    @property
    def is_on(self) -> bool | None:
        """Return True when the raw value is above zero."""
        raw = self._raw
        return None if raw is None else raw > 0
