"""Setup, entity creation, and unload."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er


def _entity_id(hass, domain, key):
    return er.async_get(hass).async_get_entity_id(domain, "supergreenlab", f"abc123_{key}")


async def test_temperature_sensor(hass: HomeAssistant, setup_entry):
    eid = _entity_id(hass, "sensor", "BOX_0_TEMP")
    assert eid
    assert hass.states.get(eid).state == "27"


async def test_vpd_scaled_to_kpa(hass: HomeAssistant, setup_entry):
    eid = _entity_id(hass, "sensor", "BOX_0_VPD")
    assert hass.states.get(eid).state == "1.45"


async def test_controller_and_box_devices(hass: HomeAssistant, setup_entry):
    reg = dr.async_get(hass)
    # The controller is the parent device.
    controller = reg.async_get_device(identifiers={("supergreenlab", "abc123")})
    assert controller is not None
    # Each enabled box is its own sub-device linked under the controller.
    box0 = reg.async_get_device(identifiers={("supergreenlab", "abc123_box_0")})
    assert box0 is not None
    assert box0.via_device_id == controller.id
    # One enabled box (box 0) in the fixture -> controller + 1 box device.
    devices = dr.async_entries_for_config_entry(reg, setup_entry.entry_id)
    assert len(devices) == 2


async def test_remove_stale_device_allowed(hass: HomeAssistant, setup_entry):
    """A device the controller no longer exposes may be deleted; a live one not."""
    from custom_components.supergreenlab import async_remove_config_entry_device

    reg = dr.async_get(hass)
    box0 = reg.async_get_device(identifiers={("supergreenlab", "abc123_box_0")})
    stale = reg.async_get_or_create(
        config_entry_id=setup_entry.entry_id,
        identifiers={("supergreenlab", "abc123_box_2")},
    )

    assert await async_remove_config_entry_device(hass, setup_entry, stale) is True
    assert await async_remove_config_entry_device(hass, setup_entry, box0) is False


async def test_write_failure_raises_translated(hass: HomeAssistant, setup_entry):
    """A device write error surfaces as a translated HomeAssistantError."""
    from unittest.mock import patch

    import pytest
    from homeassistant.exceptions import HomeAssistantError

    from custom_components.supergreenlab.api import SuperGreenApiError

    coord = setup_entry.runtime_data.fast
    with patch.object(coord.api, "set_int", side_effect=SuperGreenApiError("boom")):
        with pytest.raises(HomeAssistantError) as exc:
            await coord.async_set_int("BOX_0_TEMP_SOURCE", 1)
    assert exc.value.translation_key == "write_failed"


async def test_unload(hass: HomeAssistant, setup_entry):
    assert await hass.config_entries.async_unload(setup_entry.entry_id)
    await hass.async_block_till_done()
    assert setup_entry.state is ConfigEntryState.NOT_LOADED
