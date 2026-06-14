"""Base entities for the SuperGreenLab Controller integration.

Each enabled grow box is modelled as its own HA device, linked to the
controller via ``via_device``. Entities that belong to a box (sensors, lights,
schedule, sources …) attach to that box device; global entities (state,
restarts, reboot, valve, motors) attach to the controller device. This groups
everything for a box on one page — the box's physical composition in one place.
"""

from __future__ import annotations

from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .catalog import EntityDef, is_structural
from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import SGLDevice, SuperGreenDataUpdateCoordinator

_CATEGORY = {
    "config": EntityCategory.CONFIG,
    "diagnostic": EntityCategory.DIAGNOSTIC,
}


def controller_device_info(device: SGLDevice, host: str) -> DeviceInfo:
    """Device info for the controller itself (the parent device)."""
    return DeviceInfo(
        identifiers={(DOMAIN, device.client_id)},
        name=device.name,
        manufacturer=MANUFACTURER,
        model=MODEL,
        configuration_url=f"http://{host}",
    )


def box_device_info(device: SGLDevice, box: int) -> DeviceInfo:
    """Device info for a grow box, linked under the controller."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{device.client_id}_box{box}")},
        name=f"{device.name} Box {box}",
        manufacturer=MANUFACTURER,
        model=f"{MODEL} grow box",
        via_device=(DOMAIN, device.client_id),
    )


def device_info_for(
    device: SGLDevice, host: str, box: int | None
) -> DeviceInfo:
    """Pick the box device when a box is known, else the controller."""
    if box is not None:
        return box_device_info(device, box)
    return controller_device_info(device, host)


class SuperGreenEntity(CoordinatorEntity[SuperGreenDataUpdateCoordinator]):
    """Base for hand-written entities (light), optionally on a box device."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: SuperGreenDataUpdateCoordinator, box: int | None = None
    ) -> None:
        """Initialise shared device info."""
        super().__init__(coordinator)
        self._attr_device_info = device_info_for(
            coordinator.device, coordinator.api.host, box
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
        box = _box_of(device, placeholders)
        name = definition.name.format(**placeholders)
        # The box sub-device already carries "Box N" in its name; drop the
        # redundant prefix so we don't get "Box 0 Box 0 Temperature".
        if box is not None and name.startswith(f"Box {box} "):
            name = name[len(f"Box {box} ") :]
        self._attr_name = name
        self._attr_unique_id = f"{device.client_id}_{self._key}"
        self._attr_device_info = device_info_for(device, coordinator.api.host, box)
        self._attr_entity_category = _CATEGORY.get(definition.category)
        self._attr_entity_registry_enabled_default = definition.enabled_default
        if definition.icon:
            self._attr_icon = definition.icon

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


def _box_of(device: SGLDevice, placeholders: dict[str, int]) -> int | None:
    """Resolve the owning box for an entity instance, if any."""
    if "box" in placeholders:
        return placeholders["box"]
    if "led" in placeholders:
        return device.led_to_box.get(placeholders["led"])
    return None
