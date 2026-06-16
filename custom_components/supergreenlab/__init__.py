"""The SuperGreenLab Controller integration."""

from __future__ import annotations

import logging
import os

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_integration

from .api import SuperGreenAPI, SuperGreenApiError, SuperGreenAuthError
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
_CARD_URL = "/supergreenlab/sgl-cards.js"
_CARD_KEY = f"{DOMAIN}_card_registered"


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the bundled card and load it once for the frontend.

    Best-effort: frontend/http are always present in a real HA but not in some
    test environments, so a failure here must never break integration setup.
    """
    if hass.data.get(_CARD_KEY):
        return
    path = os.path.join(os.path.dirname(__file__), "sgl-cards.js")
    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(_CARD_URL, path, False)]
        )
        # Append the integration version so browsers reload the card on update
        # instead of serving a stale cached copy.
        integration = await async_get_integration(hass, DOMAIN)
        add_extra_js_url(hass, f"{_CARD_URL}?v={integration.version}")
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
    except SuperGreenAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except SuperGreenApiError as err:
        raise ConfigEntryNotReady(f"Cannot reach controller: {err}") from err

    fast, slow = build_coordinators(hass, entry, api, device)
    await fast.async_config_entry_first_refresh()
    await slow.async_config_entry_first_refresh()

    entry.runtime_data = RuntimeData(api=api, device=device, fast=fast, slow=slow)
    _async_prune_stale_devices(hass, entry, device)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_update))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _valid_device_identifiers(device) -> set[tuple[str, str]]:
    """The device-registry identifiers this controller currently exposes."""
    valid = {(DOMAIN, device.client_id)}
    for box in device.boxes:
        valid.add((DOMAIN, f"{device.client_id}_box_{box}"))
    return valid


@callback
def _async_prune_stale_devices(
    hass: HomeAssistant, entry: SuperGreenConfigEntry, device
) -> None:
    """Remove box sub-devices for boxes that are no longer enabled.

    Disabling a box (or moving its LED channels away) makes its sub-device
    obsolete; drop it so it doesn't linger as an empty, unavailable device.
    """
    registry = dr.async_get(hass)
    valid = _valid_device_identifiers(device)
    for dev in dr.async_entries_for_config_entry(registry, entry.entry_id):
        if not any(identifier in valid for identifier in dev.identifiers):
            registry.async_update_device(
                dev.id, remove_config_entry_id=entry.entry_id
            )


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: SuperGreenConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Allow manual deletion of a device the controller no longer exposes."""
    device = entry.runtime_data.device
    valid = _valid_device_identifiers(device)
    return not any(identifier in valid for identifier in device_entry.identifiers)


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
