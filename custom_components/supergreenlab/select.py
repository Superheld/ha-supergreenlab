"""Select platform for SuperGreenLab controllers.

Selects back the device's enum-style keys: sensor sources, ventilation
reference sources, timer mode, valve mode and LED-to-box assignment. The
integer<->label mapping comes from the catalog's ``options_map``.
"""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .catalog import SELECTS, EntityDef, expand
from .coordinator import SGLDevice, SuperGreenConfigEntry, SuperGreenDataUpdateCoordinator
from .entity import SGLCatalogEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SuperGreenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up catalogued selects."""
    rt = entry.runtime_data
    async_add_entities(
        SuperGreenSelect(rt.fast if d.fast else rt.slow, rt.device, d, ph)
        for d, ph in expand(SELECTS, rt.device)
    )


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
