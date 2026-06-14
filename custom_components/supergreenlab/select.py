"""Select platform for SuperGreenLab controllers.

Two kinds of select:

* catalogued enum keys (sensor sources, timer mode, valve mode, …) — a direct
  int<->label mapping from the catalog's ``options_map``;
* friendly **fan / blower mode** selects — a UX abstraction that sets the raw
  reference source plus sensible reference-range presets in one go, mirroring
  the SuperGreenLab app's ventilation modes (Manual / Timer / Temperature /
  Humidity / VPD / CO2).
* a **light phase** select per box — Vegetative / Bloom / Auto presets that
  write the on/off schedule times in one go, mirroring the app's grow phases.
"""

from __future__ import annotations

import re

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .catalog import SELECTS, EntityDef, expand
from .coordinator import SGLDevice, SuperGreenConfigEntry, SuperGreenDataUpdateCoordinator
from .entity import SGLCatalogEntity, SuperGreenEntity
from .sources import SOURCE_MAPS
from .tz import device_to_local_hm, local_to_device_hm

# Source-list labels that name a physical i2c sensor at a port, e.g.
# "SHT21 temperature on port #1". The port number (#1..#3) maps to the
# firmware's zero-based ``{DEVICE}_{n}_PRESENT`` flag.
_SENSOR_OPTION = re.compile(r"^(SHT21|SCD30|HX711) .* on port #(\d)$")

# Reference-range presets per ventilation mode. The *source* is resolved
# separately (see _resolve_source): Manual = 0, Timer = the box's own timer
# output, and the sensor modes follow whatever physical sensor the box already
# uses for that metric. The old code hardcoded ``offset + box`` (assuming the
# sensor sits on the port matching the box number), which silently pointed the
# fan/blower at an absent sensor on devices wired differently.
_VENT_RANGES: dict[str, tuple[int, int]] = {
    "Manual": (0, 100),
    "Timer": (0, 100),
    "Temperature": (21, 30),
    "Humidity": (35, 70),
    "VPD": (80, 160),
    "CO2": (800, 1500),
}

# Sensor modes -> (box source key suffix, the source-list its values use). We
# read the box's already-configured source and translate it (by decoded label)
# into the fan_ref / blower_ref encoding, so the unit follows the same present
# sensor as the box reading.
_VENT_SENSOR_MODES: dict[str, tuple[str, str]] = {
    "Temperature": ("TEMP_SOURCE", "temp_sensor"),
    "Humidity": ("HUMI_SOURCE", "humi_sensor"),
    "VPD": ("VPD_SOURCE", "vpd_sensor"),
    "CO2": ("CO2_SOURCE", "co2_sensor"),
}

# Classify a raw reference value back into a mode via its decoded label.
_MODE_KEYWORDS = (
    ("Timer", "timer"),
    ("Temperature", "temperature"),
    ("Humidity", "humidity"),
    ("VPD", "vpd"),
    ("CO2", "co2"),
)

# Light schedule presets, mirroring the SuperGreenLab app's grow phases. The
# controller only stores the four on/off time values; the phase is a pure
# convenience layer the app keeps on its side. We don't store it either — we
# derive the active phase from the current times (matching none -> "Custom").
# Each preset is (on_hour, on_min, off_hour, off_min).
_LIGHT_PHASES: dict[str, tuple[int, int, int, int]] = {
    "Vegetative": (3, 0, 21, 0),
    "Bloom": (6, 0, 18, 0),
    "Auto": (2, 0, 22, 0),
}
_CUSTOM_PHASE = "Custom"


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
        entities.append(SuperGreenLightPhaseSelect(rt.slow, box))
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
        self._all_options = list(self._int_to_label.values())

    @property
    def options(self) -> list[str]:
        """Offer only sensors the firmware reports as present, plus the rest.

        Source lists enumerate every metric x port; filtering to the
        ``*_PRESENT`` flags keeps the dropdown to the hardware that's actually
        wired. Non-sensor entries (off, box timer outputs, …) always stay. Falls
        back to all sensors if presence detection reports none (so initial setup
        isn't blocked), and always keeps the current selection valid.
        """
        data = self.coordinator.data or {}
        sensors: list[str] = []
        present: list[str] = []
        for label in self._all_options:
            m = _SENSOR_OPTION.match(label)
            if m is None:
                continue
            sensors.append(label)
            device, port = m.group(1), int(m.group(2)) - 1
            if data.get(f"{device}_{port}_PRESENT") == 1:
                present.append(label)
        if not sensors:
            return self._all_options
        keep = set(present or sensors)
        current = self.current_option
        if current is not None:
            keep.add(current)
        return [
            label
            for label in self._all_options
            if not _SENSOR_OPTION.match(label) or label in keep
        ]

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
        self._attr_options = list(_VENT_RANGES)

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

    def _resolve_source(self, option: str) -> int:
        """Resolve the raw reference-source value for a mode.

        Sensor modes follow the box's own configured source for that metric
        (translated by label into this unit's ref encoding), so the fan/blower
        tracks a present sensor instead of a hardcoded port.
        """
        if option == "Manual":
            return 0
        if option == "Timer":
            return 8 + self._box  # 'Box #N timer output' entries are 8/9/10
        key_suffix, src_list = _VENT_SENSOR_MODES[option]
        data = self.coordinator.data or {}
        box_src = data.get(f"BOX_{self._box}_{key_suffix}")
        label = SOURCE_MAPS[src_list].get(box_src) if box_src is not None else None
        if label is None:
            return 0
        return {v: k for k, v in SOURCE_MAPS[self._source_list].items()}.get(label, 0)

    async def async_select_option(self, option: str) -> None:
        """Apply the mode: write reference source and range presets."""
        if option not in _VENT_RANGES:
            return
        ref_min, ref_max = _VENT_RANGES[option]
        await self.coordinator.async_set_int(self._source_key, self._resolve_source(option))
        await self.coordinator.async_set_int(self._min_key, ref_min)
        await self.coordinator.async_set_int(self._max_key, ref_max)


class SuperGreenLightPhaseSelect(SuperGreenEntity, SelectEntity):
    """Friendly light-schedule phase: writes the on/off times in one go.

    Mirrors the app's Vegetative / Bloom / Auto presets. The phase is derived
    from the current times, so it needs no stored state and follows along when
    the times are edited by hand (-> "Custom").
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:sprout"
    _attr_options = [*_LIGHT_PHASES, _CUSTOM_PHASE]

    def __init__(self, coordinator: SuperGreenDataUpdateCoordinator, box: int) -> None:
        """Bind to a box's on/off schedule keys."""
        super().__init__(coordinator)
        self._box = box
        self._on_hour = f"BOX_{box}_ON_HOUR"
        self._on_min = f"BOX_{box}_ON_MIN"
        self._off_hour = f"BOX_{box}_OFF_HOUR"
        self._off_min = f"BOX_{box}_OFF_MIN"
        self._attr_name = f"Box {box} Light phase"
        self._attr_unique_id = self._unique_id(f"BOX_{box}_LIGHT_PHASE")

    @property
    def current_option(self) -> str | None:
        """Match the current times against a preset, else 'Custom'.

        The presets are local wall-clock times; the device stores UTC, so we
        convert the device values to local before matching.
        """
        data = self.coordinator.data
        if not data:
            return None
        raw = [
            data.get(k)
            for k in (self._on_hour, self._on_min, self._off_hour, self._off_min)
        ]
        if any(t is None for t in raw):
            return None
        on_h, on_m = device_to_local_hm(raw[0], raw[1])
        off_h, off_m = device_to_local_hm(raw[2], raw[3])
        times = (on_h, on_m, off_h, off_m)
        for phase, preset in _LIGHT_PHASES.items():
            if times == preset:
                return phase
        return _CUSTOM_PHASE

    async def async_select_option(self, option: str) -> None:
        """Apply a phase preset; 'Custom' is derived-only and does nothing.

        Presets are local times; convert to the UTC values the device stores.
        """
        preset = _LIGHT_PHASES.get(option)
        if preset is None:
            return
        on_hour, on_min = local_to_device_hm(preset[0], preset[1])
        off_hour, off_min = local_to_device_hm(preset[2], preset[3])
        await self.coordinator.async_set_int(self._on_hour, on_hour)
        await self.coordinator.async_set_int(self._on_min, on_min)
        await self.coordinator.async_set_int(self._off_hour, off_hour)
        await self.coordinator.async_set_int(self._off_min, off_min)
