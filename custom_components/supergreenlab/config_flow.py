"""Config flow for the SuperGreenLab Controller integration."""

from __future__ import annotations

import base64
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SuperGreenAPI, SuperGreenApiError
from .const import CONF_FAST_INTERVAL, CONF_HOST, DOMAIN, FAST_SCAN_INTERVAL
from .coordinator import async_detect_device

_LOGGER = logging.getLogger(__name__)

CONF_AUTH = "auth"

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)


def _make_auth(username: str | None, password: str | None) -> str | None:
    """Build the base64 Basic-auth token expected by the firmware."""
    if not username and not password:
        return None
    raw = f"{username or ''}:{password or ''}".encode()
    return base64.b64encode(raw).decode()


class SuperGreenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SuperGreenLab controllers."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step where the user enters the controller IP."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            auth = _make_auth(
                user_input.get(CONF_USERNAME), user_input.get(CONF_PASSWORD)
            )
            session = async_get_clientsession(self.hass)
            api = SuperGreenAPI(host, session, auth=auth)
            try:
                device = await async_detect_device(api)
            except SuperGreenApiError as err:
                _LOGGER.debug("Cannot connect to %s: %s", host, err)
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(device.client_id)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(
                    title=device.name,
                    data={CONF_HOST: host, CONF_AUTH: auth},
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SuperGreenOptionsFlow:
        """Return the options flow handler."""
        return SuperGreenOptionsFlow()


class SuperGreenOptionsFlow(OptionsFlow):
    """Handle integration-level options (HA-side only)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the live-polling interval."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            CONF_FAST_INTERVAL, int(FAST_SCAN_INTERVAL.total_seconds())
        )
        schema = vol.Schema(
            {
                vol.Optional(CONF_FAST_INTERVAL, default=current): vol.All(
                    vol.Coerce(int), vol.Range(min=10, max=600)
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
