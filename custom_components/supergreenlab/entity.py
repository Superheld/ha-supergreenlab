"""Base entities for the SuperGreenLab Controller integration.

The controller is the parent HA device; each enabled **box** is its own
sub-device (linked via ``via_device``), so HA groups a box's entities together
natively. Box entities therefore carry short names ("Temperature", "Fan mode")
and the box device supplies the "Box 0" context — which also keeps entity ids
clean (``sensor.box_0_temperature``, no controller-name prefix). Controller-wide
things (state, restart, valve, motors) stay on the controller device.
"""

from __future__ import annotations

from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .catalog import EntityDef, entity_translation_key, is_structural
from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import SGLDevice, SuperGreenDataUpdateCoordinator

_CATEGORY = {
    "config": EntityCategory.CONFIG,
    "diagnostic": EntityCategory.DIAGNOSTIC,
}


def controller_device_info(device: SGLDevice, host: str) -> DeviceInfo:
    """Device info for the controller (the parent device)."""
    return DeviceInfo(
        identifiers={(DOMAIN, device.client_id)},
        name=device.name,
        manufacturer=MANUFACTURER,
        model=MODEL,
        configuration_url=f"http://{host}",
    )


def box_device_info(device: SGLDevice, box: int) -> DeviceInfo:
    """Device info for one grow box, linked under the controller."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{device.client_id}_box_{box}")},
        name=f"Box {box}",
        manufacturer=MANUFACTURER,
        model="Grow box",
        via_device=(DOMAIN, device.client_id),
    )


def _box_for(device: SGLDevice, placeholders: dict[str, int]) -> int | None:
    """Which box (if any) an instance belongs to, for device assignment."""
    if "box" in placeholders:
        return placeholders["box"]
    if "led" in placeholders:
        return device.led_to_box.get(placeholders["led"])
    return None


class SuperGreenEntity(CoordinatorEntity[SuperGreenDataUpdateCoordinator]):
    """Base for hand-written entities (light, synthetic selects/switches/…)."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: SuperGreenDataUpdateCoordinator, box: int | None = None
    ) -> None:
        """Attach to a box sub-device when ``box`` is given, else the controller."""
        super().__init__(coordinator)
        if box is not None:
            self._attr_device_info = box_device_info(coordinator.device, box)
        else:
            self._attr_device_info = controller_device_info(
                coordinator.device, coordinator.api.host
            )

    def _unique_id(self, suffix: str) -> str:
        return f"{self.coordinator.device.client_id}_{suffix}"


class SGLCatalogEntity(CoordinatorEntity[SuperGreenDataUpdateCoordinator]):
    """Base for every catalog-driven entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SuperGreenDataUpdateCoordinator,
        device: SGLDevice,
        definition: EntityDef,
        placeholders: dict[str, int],
    ) -> None:
        """Bind a catalog definition to a concrete instance."""
        super().__init__(coordinator)
        self._def = definition
        self._key = definition.key.format(**placeholders)
        self._structural = is_structural(definition.key)
        # Names come from the translations (entity-translations rule). The box
        # context is supplied by the box sub-device, so only non-box indices are
        # passed through as placeholders for the translated name.
        self._attr_translation_key = entity_translation_key(definition)
        self._attr_translation_placeholders = {
            k: str(v) for k, v in placeholders.items() if k != "box"
        }
        box = _box_for(device, placeholders)
        if box is not None:
            self._attr_device_info = box_device_info(device, box)
        else:
            self._attr_device_info = controller_device_info(device, coordinator.api.host)
        self._attr_unique_id = f"{device.client_id}_{self._key}"
        self._attr_entity_category = _CATEGORY.get(definition.category)
        self._attr_entity_registry_enabled_default = definition.enabled_default

    @property
    def _raw(self) -> int | None:
        """Current raw integer value from the coordinator cache."""
        return self.coordinator.data.get(self._key) if self.coordinator.data else None

    async def _write(self, value: int) -> None:
        """Write a value, reloading the entry if the key is structural."""
        await self.coordinator.async_set_int(self._key, value)
        if self._structural and self.coordinator.config_entry is not None:
            self.hass.config_entries.async_schedule_reload(
                self.coordinator.config_entry.entry_id
            )
