"""The SuperGreenLab Controller integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SuperGreenAPI, SuperGreenApiError
from .config_flow import CONF_AUTH
from .const import CONF_HOST
from .coordinator import (
    RuntimeData,
    SuperGreenConfigEntry,
    async_detect_device,
    build_coordinators,
)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(
    hass: HomeAssistant, entry: SuperGreenConfigEntry
) -> bool:
    """Set up SuperGreenLab Controller from a config entry."""
    session = async_get_clientsession(hass)
    api = SuperGreenAPI(entry.data[CONF_HOST], session, auth=entry.data.get(CONF_AUTH))

    try:
        device = await async_detect_device(api)
    except SuperGreenApiError as err:
        raise ConfigEntryNotReady(f"Cannot reach controller: {err}") from err

    fast, slow = build_coordinators(hass, entry, api, device)
    await fast.async_config_entry_first_refresh()
    await slow.async_config_entry_first_refresh()

    entry.runtime_data = RuntimeData(api=api, device=device, fast=fast, slow=slow)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_update))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_reload_on_update(
    hass: HomeAssistant, entry: SuperGreenConfigEntry
) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: SuperGreenConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
