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
from .const import (
    CONF_FAST_INTERVAL,
    CONF_HOST,
    DOMAIN,
    FAST_SCAN_INTERVAL,
    MAX_BOXES,
    MAX_LED_CHANNELS,
)
from .coordinator import async_detect_device
from .sources import LED_BOX_MAP

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
    """Integration options: device layout (structural) and HA-side settings.

    Box enable/disable and LED-to-box assignment live here rather than as
    entities: they are structural (they decide which entities exist), rarely
    changed, and would otherwise clutter the device page with controls for
    boxes/channels that aren't in use. The controller stays the source of
    truth — this step writes the chosen layout to the device and the entry is
    reloaded to re-discover entities.
    """

    def _api(self) -> SuperGreenAPI:
        session = async_get_clientsession(self.hass)
        return SuperGreenAPI(
            self.config_entry.data[CONF_HOST],
            session,
            auth=self.config_entry.data.get(CONF_AUTH),
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options menu."""
        return self.async_show_menu(step_id="init", menu_options=["layout", "settings"])

    async def async_step_layout(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enable/disable boxes and assign LED channels to boxes."""
        api = self._api()
        label_to_box = {v: k for k, v in LED_BOX_MAP.items()}

        if user_input is not None:
            for box in range(MAX_BOXES):
                await api.set_int(f"BOX_{box}_ENABLED", 1 if user_input[f"box_{box}"] else 0)
            for led in range(MAX_LED_CHANNELS):
                await api.set_int(f"LED_{led}_BOX", label_to_box[user_input[f"led_{led}"]])
            # Persisting the chosen layout makes the options change, which
            # reloads the entry and re-runs discovery against the device.
            return self.async_create_entry(
                data={**self.config_entry.options, "layout": user_input}
            )

        led_options = list(LED_BOX_MAP.values())
        schema_dict: dict[Any, Any] = {}
        for box in range(MAX_BOXES):
            enabled = await api.get_int(f"BOX_{box}_ENABLED")
            schema_dict[vol.Required(f"box_{box}", default=enabled == 1)] = bool
        for led in range(MAX_LED_CHANNELS):
            raw = await api.get_int(f"LED_{led}_BOX")
            default = LED_BOX_MAP.get(raw if raw is not None else -1, LED_BOX_MAP[-1])
            schema_dict[vol.Required(f"led_{led}", default=default)] = vol.In(led_options)

        return self.async_show_form(step_id="layout", data_schema=vol.Schema(schema_dict))

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the live-polling interval."""
        if user_input is not None:
            return self.async_create_entry(
                data={**self.config_entry.options, **user_input}
            )

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
        return self.async_show_form(step_id="settings", data_schema=schema)
