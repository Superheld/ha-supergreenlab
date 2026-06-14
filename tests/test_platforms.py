"""Writing through the control entities reaches the device store."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


def _entity_id(hass, domain, key):
    return er.async_get(hass).async_get_entity_id(domain, "supergreenlab", f"abc123_{key}")


async def test_light_sets_dim(hass: HomeAssistant, setup_entry, store):
    eid = _entity_id(hass, "light", "LED_0_DIM")
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": eid, "brightness": 128}, blocking=True
    )
    assert store["LED_0_DIM"] == round(128 * 100 / 255)


async def test_light_off(hass: HomeAssistant, setup_entry, store):
    eid = _entity_id(hass, "light", "LED_0_DIM")
    await hass.services.async_call(
        "light", "turn_off", {"entity_id": eid}, blocking=True
    )
    assert store["LED_0_DIM"] == 0


async def test_time_sets_both_keys(hass: HomeAssistant, setup_entry, store):
    eid = _entity_id(hass, "time", "BOX_0_ON_HOUR")
    await hass.services.async_call(
        "time", "set_value", {"entity_id": eid, "time": "08:30:00"}, blocking=True
    )
    assert store["BOX_0_ON_HOUR"] == 8
    assert store["BOX_0_ON_MIN"] == 30


async def test_select_source_writes_decoded_int(hass: HomeAssistant, setup_entry, store):
    eid = _entity_id(hass, "select", "BOX_0_TEMP_SOURCE")
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": eid, "option": "SCD30 temperature on port #1"},
        blocking=True,
    )
    assert store["BOX_0_TEMP_SOURCE"] == 16


async def test_source_select_filters_to_present(hass: HomeAssistant, setup_entry, store):
    eid = _entity_id(hass, "select", "BOX_0_TEMP_SOURCE")
    # Only the SHT21 on port #1 is detected as present.
    store["SHT21_0_PRESENT"] = 1
    await setup_entry.runtime_data.slow.async_request_refresh()
    await hass.async_block_till_done()
    opts = hass.states.get(eid).attributes["options"]
    assert "SHT21 temperature on port #1" in opts  # present
    assert "SCD30 temperature on port #1" not in opts  # absent -> hidden
    assert "Off / Manual" in opts  # non-sensor entry always kept


async def test_source_select_falls_back_when_none_present(
    hass: HomeAssistant, setup_entry, store
):
    # No *_PRESENT flags set -> show all sensors so setup isn't blocked.
    eid = _entity_id(hass, "select", "BOX_0_TEMP_SOURCE")
    opts = hass.states.get(eid).attributes["options"]
    assert "SHT21 temperature on port #1" in opts
    assert "SCD30 temperature on port #3" in opts


async def test_light_phase_sets_times(hass: HomeAssistant, setup_entry, store):
    eid = _entity_id(hass, "select", "BOX_0_LIGHT_PHASE")
    assert eid
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": eid, "option": "Bloom"},
        blocking=True,
    )
    assert store["BOX_0_ON_HOUR"] == 6
    assert store["BOX_0_ON_MIN"] == 0
    assert store["BOX_0_OFF_HOUR"] == 18
    assert store["BOX_0_OFF_MIN"] == 0


async def test_light_phase_derived_from_times(hass: HomeAssistant, setup_entry, store):
    eid = _entity_id(hass, "select", "BOX_0_LIGHT_PHASE")
    # Default store times match no preset -> Custom.
    assert hass.states.get(eid).state == "Custom"
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": eid, "option": "Vegetative"},
        blocking=True,
    )
    assert hass.states.get(eid).state == "Vegetative"


async def test_fan_mode_sets_source_and_range(hass: HomeAssistant, setup_entry, store):
    eid = _entity_id(hass, "select", "BOX_0_FAN_MODE")
    assert eid
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": eid, "option": "Temperature"},
        blocking=True,
    )
    assert store["BOX_0_FAN_REF_SOURCE"] == 1
    assert store["BOX_0_FAN_REF_MIN"] == 21
    assert store["BOX_0_FAN_REF_MAX"] == 30
