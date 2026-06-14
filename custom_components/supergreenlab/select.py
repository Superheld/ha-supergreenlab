"""Select platform for SuperGreenLab controllers.

Two kinds of select:

* catalogued enum keys (sensor sources, timer mode, valve mode, …) — a direct
  int<->label mapping from the catalog's ``options_map``;
* friendly **fan / blower mode** selects — a UX abstraction that sets the raw
  reference source plus sensible reference-range presets in one go, mirroring
  the SuperGreenLab app's ventilation modes (Manual / Timer / Temperature /
  Humidity / VPD / CO2).
"""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .catalog import SELECTS, EntityDef, expand
from .coordinator import SGLDevice, SuperGreenConfigEntry, SuperGreenDataUpdateCoordinator
from .entity import SGLCatalogEntity, SuperGreenEntity
from .sources import SOURCE_MAPS

# A ventilation mode is a preset of (reference-source offset, ref_min, ref_max).
# The concrete source value is ``offset + box`` (matching the firmware's
# indirection list ordering), except Manual which is 0. ``None`` offset = manual.
_VENT_MODES: dict[str, tuple[int | None, int, int]] = {
    "Manual": (None, 0, 100),
    "Timer": (8, 0, 100),
    "Temperature": (1, 21, 30),
    "Humidity": (15, 35, 70),
    "VPD": (23, 80, 160),
    "CO2": (30, 800, 1500),
}

# Classify a raw reference value back into a mode via its decoded label.
_MODE_KEYWORDS = (
    ("Timer", "timer"),
    ("Temperature", "temperature"),
    ("Humidity", "humidity"),
    ("VPD", "vpd"),
    ("CO2", "co2"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SuperGreenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up catalogued selects plus the fan/blower mode selects."""
    rt = entry.runtime_data
    entities: list[SelectEntity] = [
        SuperGreenSelect(rt.fast if d.fast else rt.slow, rt.device, d, ph)
        for d, ph in expand(SELECTS, rt.device)
    ]
    for box in rt.device.boxes:
        entities.append(SuperGreenVentModeSelect(rt.slow, box, "FAN", "fan_ref"))
        entities.append(SuperGreenVentModeSelect(rt.slow, box, "BLOWER", "blower_ref"))
    async_add_entities(entities)


class SuperGreenSelect(SGLCatalogEntity, SelectEntity):
    """A catalogued enum key exposed as a dropdown."""

    def __init__(
        self,
        coordinator: SuperGreenDataUpdateCoordinator,
        device: SGLDevice,
        definition: EntityDef,
        placeholders: dict[str, int],
    ) -> None:
        """Build the label<->value lookup tables."""
        super().__init__(coordinator, device, definition, placeholders)
        self._int_to_label: dict[int, str] = dict(definition.options_map or {})
        self._label_to_int: dict[str, int] = {
            v: k for k, v in self._int_to_label.items()
        }
        self._attr_options = list(self._int_to_label.values())

    @property
    def current_option(self) -> str | None:
        """Return the label for the current raw value."""
        raw = self._raw
        if raw is None:
            return None
        return self._int_to_label.get(raw)

    async def async_select_option(self, option: str) -> None:
        """Write the integer behind the chosen label."""
        if option not in self._label_to_int:
            return
        await self._write(self._label_to_int[option])


class SuperGreenVentModeSelect(SuperGreenEntity, SelectEntity):
    """Friendly fan/blower mode: sets reference source + range presets at once."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:fan-auto"

    def __init__(
        self,
        coordinator: SuperGreenDataUpdateCoordinator,
        box: int,
        kind: str,
        source_list: str,
    ) -> None:
        """Bind to a box's fan or blower reference keys."""
        super().__init__(coordinator)
        self._box = box
        self._source_list = source_list
        self._source_key = f"BOX_{box}_{kind}_REF_SOURCE"
        self._min_key = f"BOX_{box}_{kind}_REF_MIN"
        self._max_key = f"BOX_{box}_{kind}_REF_MAX"
        label = "Fan" if kind == "FAN" else "Blower"
        self._attr_name = f"Box {box} {label} mode"
        self._attr_unique_id = self._unique_id(f"BOX_{box}_{kind}_MODE")
        self._attr_options = list(_VENT_MODES)

    @property
    def current_option(self) -> str | None:
        """Derive the mode from the current raw reference source."""
        data = self.coordinator.data
        raw = data.get(self._source_key) if data else None
        if raw is None:
            return None
        if raw == 0:
            return "Manual"
        label = SOURCE_MAPS[self._source_list].get(raw, "").lower()
        for mode, keyword in _MODE_KEYWORDS:
            if keyword in label:
                return mode
        return None

    async def async_select_option(self, option: str) -> None:
        """Apply the mode: write reference source and range presets."""
        if option not in _VENT_MODES:
            return
        offset, ref_min, ref_max = _VENT_MODES[option]
        source = 0 if offset is None else offset + self._box
        await self.coordinator.async_set_int(self._source_key, source)
        await self.coordinator.async_set_int(self._min_key, ref_min)
        await self.coordinator.async_set_int(self._max_key, ref_max)
