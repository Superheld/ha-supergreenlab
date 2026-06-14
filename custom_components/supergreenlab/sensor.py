"""Sensor platform for SuperGreenLab controllers."""

from __future__ import annotations

from datetime import UTC, datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .catalog import SENSORS, EntityDef, expand
from .coordinator import SGLDevice, SuperGreenConfigEntry, SuperGreenDataUpdateCoordinator
from .entity import SGLCatalogEntity, SuperGreenEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SuperGreenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up catalogued sensors plus the per-box season-date readback."""
    rt = entry.runtime_data
    entities: list[SensorEntity] = [
        SuperGreenSensor(rt.fast if d.fast else rt.slow, rt.device, d, ph)
        for d, ph in expand(SENSORS, rt.device)
    ]
    entities.extend(SuperGreenSeasonDateSensor(rt.slow, box) for box in rt.device.boxes)
    async_add_entities(entities)


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


class SuperGreenSeasonDateSensor(SuperGreenEntity, SensorEntity):
    """The box's current position in the simulated season (Season mode).

    ``BOX_x_SIMULATED_TIME`` is a unix timestamp the firmware advances while a
    season runs; it reads the simulated calendar date the box is currently at.
    Exposed read-only so you can see how far the season has progressed.
    """

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: SuperGreenDataUpdateCoordinator, box: int) -> None:
        """Bind to a box's simulated-time key."""
        super().__init__(coordinator)
        self._key = f"BOX_{box}_SIMULATED_TIME"
        self._attr_name = f"Box {box} Season date"
        self._attr_unique_id = self._unique_id(self._key)

    @property
    def native_value(self) -> datetime | None:
        """Return the simulated season date, or None before a season runs."""
        data = self.coordinator.data
        ts = data.get(self._key) if data else None
        if not ts:
            return None
        return datetime.fromtimestamp(ts, tz=UTC)
