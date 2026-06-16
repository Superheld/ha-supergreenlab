"""Config flow tests."""

from __future__ import annotations

from ipaddress import ip_address
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from custom_components.supergreenlab.api import SuperGreenApiError
from custom_components.supergreenlab.const import DOMAIN

_ZEROCONF = ZeroconfServiceInfo(
    ip_address=ip_address("1.2.3.4"),
    ip_addresses=[ip_address("1.2.3.4")],
    port=80,
    hostname="supergreencontroller.local.",
    type="_http._tcp.local.",
    name="supergreencontroller._http._tcp.local.",
    properties={},
)


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


async def test_zeroconf_discovery(hass: HomeAssistant, mock_api):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=_ZEROCONF
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Dings"
    assert result["data"]["host"] == "1.2.3.4"
    assert result["result"].unique_id == "abc123"


async def test_zeroconf_aborts_when_unreachable(hass: HomeAssistant):
    with patch(
        "custom_components.supergreenlab.config_flow.async_detect_device",
        side_effect=SuperGreenApiError("nope"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=_ZEROCONF
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


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
