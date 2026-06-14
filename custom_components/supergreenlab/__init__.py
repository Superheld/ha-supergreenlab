"""The SuperGreenLab Controller integration."""

from __future__ import annotations

import logging
import os

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SuperGreenAPI, SuperGreenApiError
from .config_flow import CONF_AUTH
from .const import CONF_HOST, DOMAIN
from .coordinator import (
    RuntimeData,
    SuperGreenConfigEntry,
    async_detect_device,
    build_coordinators,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]

# Bundled Lovelace card, served and auto-loaded so users don't need a separate
# HACS plugin or a manual dashboard resource.
_CARD_URL = "/supergreenlab/sgl-fan-card.js"
_CARD_KEY = f"{DOMAIN}_card_registered"


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the bundled card and load it once for the frontend.

    Best-effort: frontend/http are always present in a real HA but not in some
    test environments, so a failure here must never break integration setup.
    """
    if hass.data.get(_CARD_KEY):
        return
    path = os.path.join(os.path.dirname(__file__), "sgl-fan-card.js")
    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(_CARD_URL, path, False)]
        )
        add_extra_js_url(hass, _CARD_URL)
        hass.data[_CARD_KEY] = True
    except Exception:  # noqa: BLE001 - bundled card is a non-essential extra
        _LOGGER.debug("Could not register bundled Lovelace card", exc_info=True)


async def async_setup_entry(
    hass: HomeAssistant, entry: SuperGreenConfigEntry
) -> bool:
    """Set up SuperGreenLab Controller from a config entry."""
    await _async_register_frontend(hass)
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
