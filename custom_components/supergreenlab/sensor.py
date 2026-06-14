"""Sensor platform for SuperGreenLab controllers."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .catalog import SENSORS, EntityDef, expand
from .coordinator import SGLDevice, SuperGreenConfigEntry, SuperGreenDataUpdateCoordinator
from .entity import SGLCatalogEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SuperGreenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up catalogued sensors."""
    rt = entry.runtime_data
    async_add_entities(
        SuperGreenSensor(rt.fast if d.fast else rt.slow, rt.device, d, ph)
        for d, ph in expand(SENSORS, rt.device)
    )


class SuperGreenSensor(SGLCatalogEntity, SensorEntity):
    """A catalogued read-only value."""

    def __init__(
        self,
        coordinator: SuperGreenDataUpdateCoordinator,
        device: SGLDevice,
        definition: EntityDef,
        placeholders: dict[str, int],
    ) -> None:
        """Apply sensor metadata from the catalog definition."""
        super().__init__(coordinator, device, definition, placeholders)
        if definition.value_map is not None:
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = list(definition.value_map.values())
        else:
            self._attr_device_class = definition.device_class
            self._attr_native_unit_of_measurement = definition.unit
            self._attr_state_class = definition.state_class
            if definition.precision is not None:
                self._attr_suggested_display_precision = definition.precision

    @property
    def native_value(self) -> float | str | None:
        """Return the scaled or mapped current value."""
        raw = self._raw
        if raw is None:
            return None
        if self._def.value_map is not None:
            return self._def.value_map.get(raw)
        if self._def.scale != 1.0:
            return raw * self._def.scale
        return raw
