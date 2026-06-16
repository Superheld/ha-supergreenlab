"""Config-entry diagnostics."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from custom_components.supergreenlab.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_diagnostics_redacts_and_snapshots(
    hass: HomeAssistant, setup_entry
) -> None:
    diag = await async_get_config_entry_diagnostics(hass, setup_entry)
    # Secrets are redacted (client_id is the chip MAC).
    assert diag["device"]["client_id"] == "**REDACTED**"
    assert "auth" in diag["entry_data"]  # present but never a real secret
    # ...but the useful snapshot is there.
    assert diag["device"]["boxes"] == [0]
    assert diag["fast_data"]["BOX_0_TEMP"] == 27
