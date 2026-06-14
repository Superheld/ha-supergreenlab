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


async def test_single_controller_device(hass: HomeAssistant, setup_entry):
    reg = dr.async_get(hass)
    # The controller is the only device; boxes are logical slots, not devices.
    controller = reg.async_get_device(identifiers={("supergreenlab", "abc123")})
    assert controller is not None
    devices = dr.async_entries_for_config_entry(reg, setup_entry.entry_id)
    assert len(devices) == 1


async def test_unload(hass: HomeAssistant, setup_entry):
    assert await hass.config_entries.async_unload(setup_entry.entry_id)
    await hass.async_block_till_done()
    assert setup_entry.state is ConfigEntryState.NOT_LOADED
