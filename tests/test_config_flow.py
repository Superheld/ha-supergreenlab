"""Config flow tests."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.supergreenlab.api import SuperGreenApiError
from custom_components.supergreenlab.const import DOMAIN


async def test_user_flow_success(hass: HomeAssistant, mock_api):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "1.2.3.4"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Dings"
    assert result["result"].unique_id == "abc123"


async def test_user_flow_cannot_connect(hass: HomeAssistant):
    with patch(
        "custom_components.supergreenlab.config_flow.async_detect_device",
        side_effect=SuperGreenApiError("nope"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "1.2.3.4"}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_duplicate_aborts(hass: HomeAssistant, mock_api):
    first = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(first["flow_id"], {"host": "1.2.3.4"})

    second = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        second["flow_id"], {"host": "9.9.9.9"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
