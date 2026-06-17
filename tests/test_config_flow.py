"""Config flow tests."""

from __future__ import annotations

from ipaddress import ip_address
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.supergreenlab.api import SuperGreenApiError, SuperGreenAuthError
from custom_components.supergreenlab.const import DOMAIN
from custom_components.supergreenlab.coordinator import SGLDevice

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


def _entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, data={"host": "1.2.3.4", "auth": None}, unique_id="abc123"
    )
    entry.add_to_hass(hass)
    return entry


async def test_reconfigure_updates_host(hass: HomeAssistant, mock_api):
    entry = _entry(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "5.6.7.8"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["host"] == "5.6.7.8"
    await hass.async_block_till_done()


async def test_reconfigure_wrong_device(hass: HomeAssistant, mock_api):
    entry = _entry(hass)
    result = await entry.start_reconfigure_flow(hass)
    with patch(
        "custom_components.supergreenlab.config_flow.async_detect_device",
        return_value=SGLDevice(client_id="other", name="Other"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "5.6.7.8"}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert entry.data["host"] == "1.2.3.4"


async def test_reauth_success(hass: HomeAssistant, mock_api):
    entry = _entry(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "u", "password": "p"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["auth"] is not None
    await hass.async_block_till_done()


async def test_reauth_invalid(hass: HomeAssistant, mock_api):
    entry = _entry(hass)
    result = await entry.start_reauth_flow(hass)
    with patch(
        "custom_components.supergreenlab.config_flow.async_detect_device",
        side_effect=SuperGreenAuthError("nope"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "u", "password": "x"}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_dhcp_updates_host(hass: HomeAssistant, mock_api):
    """A DHCP lease for a known controller updates its stored IP."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={"host": "1.2.3.4", "auth": None}, unique_id="abc123"
    )
    entry.add_to_hass(hass)
    info = DhcpServiceInfo(ip="5.6.7.8", hostname="dings", macaddress="abc123")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=info
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data["host"] == "5.6.7.8"


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
