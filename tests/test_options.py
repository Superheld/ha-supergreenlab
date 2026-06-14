"""Options flow: device layout and polling settings."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_layout_writes_to_device(hass: HomeAssistant, setup_entry, store):
    result = await hass.config_entries.options.async_init(setup_entry.entry_id)
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "layout"}
    )
    assert result["type"] == FlowResultType.FORM

    user_input = {f"box_{b}": (b == 0) for b in range(3)}
    user_input.update({f"led_{led}": "Box 0" for led in range(3)})
    user_input.update({f"led_{led}": "Unassigned" for led in range(3, 6)})

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert store["BOX_0_ENABLED"] == 1
    assert store["LED_0_BOX"] == 0
    assert store["LED_3_BOX"] == -1


async def test_settings_interval(hass: HomeAssistant, setup_entry):
    result = await hass.config_entries.options.async_init(setup_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "settings"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"fast_interval": 60}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert setup_entry.options["fast_interval"] == 60
