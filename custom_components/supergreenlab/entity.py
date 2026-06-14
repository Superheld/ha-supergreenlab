"""Base entities for the SuperGreenLab Controller integration."""

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


def device_info(device: SGLDevice, host: str) -> DeviceInfo:
    """Build the shared device info block."""
    return DeviceInfo(
        identifiers={(DOMAIN, device.client_id)},
        name=device.name,
        manufacturer=MANUFACTURER,
        model=MODEL,
        configuration_url=f"http://{host}",
    )


class SuperGreenEntity(CoordinatorEntity[SuperGreenDataUpdateCoordinator]):
    """Base for hand-written entities (light)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SuperGreenDataUpdateCoordinator) -> None:
        """Initialise shared device info."""
        super().__init__(coordinator)
        self._attr_device_info = device_info(coordinator.device, coordinator.api.host)

    def _unique_id(self, suffix: str) -> str:
        return f"{self.coordinator.device.client_id}_{suffix}"


class SGLCatalogEntity(CoordinatorEntity[SuperGreenDataUpdateCoordinator]):
    """Base for every catalog-driven entity.

    Resolves the templated key/name against its placeholders and wires up the
    device, unique id, category and default-enabled state.
    """

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
        self._attr_name = definition.name.format(**placeholders)
        self._attr_unique_id = f"{device.client_id}_{self._key}"
        self._attr_device_info = device_info(device, coordinator.api.host)
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
