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
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import SuperGreenAPI, SuperGreenApiError, SuperGreenAuthError
from .const import (
    CONF_FAST_INTERVAL,
    CONF_HOST,
    DOMAIN,
    FAST_SCAN_INTERVAL,
    MAX_BOXES,
    MAX_LED_CHANNELS,
)
from .coordinator import SGLDevice, async_detect_device
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

STEP_REAUTH_SCHEMA = vol.Schema(
    {
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

    async def _async_probe(
        self, host: str, auth: str | None
    ) -> tuple[SGLDevice | None, str | None]:
        """Probe a controller, returning ``(device, error_key)``.

        ``error_key`` is ``None`` on success, otherwise ``"invalid_auth"`` or
        ``"cannot_connect"`` so callers can surface the right form error.
        """
        session = async_get_clientsession(self.hass)
        api = SuperGreenAPI(host, session, auth=auth)
        try:
            return await async_detect_device(api), None
        except SuperGreenAuthError as err:
            _LOGGER.debug("Auth rejected by %s: %s", host, err)
            return None, "invalid_auth"
        except SuperGreenApiError as err:
            _LOGGER.debug("Cannot connect to %s: %s", host, err)
            return None, "cannot_connect"

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
            device, error = await self._async_probe(host, auth)
            if error:
                errors["base"] = error
            else:
                assert device is not None
                await self.async_set_unique_id(device.client_id)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(
                    title=device.name,
                    data={CONF_HOST: host, CONF_AUTH: auth},
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user change the controller's host/IP (and credentials).

        Common case: DHCP handed the controller a new IP. This updates the
        existing entry in place instead of forcing a remove + re-add, which
        would lose all entities and their history.
        """
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            auth = _make_auth(
                user_input.get(CONF_USERNAME), user_input.get(CONF_PASSWORD)
            )
            device, error = await self._async_probe(host, auth)
            if error:
                errors["base"] = error
            else:
                # Guard against pointing the entry at a *different* controller.
                assert device is not None
                await self.async_set_unique_id(device.client_id)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    entry, data={CONF_HOST: host, CONF_AUTH: auth}
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str,
                vol.Optional(CONF_USERNAME): str,
                vol.Optional(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Start reauth after the controller rejected the stored credentials."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for new credentials and update the entry if they work."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            auth = _make_auth(
                user_input.get(CONF_USERNAME), user_input.get(CONF_PASSWORD)
            )
            device, error = await self._async_probe(entry.data[CONF_HOST], auth)
            if error:
                errors["base"] = error
            else:
                assert device is not None
                await self.async_set_unique_id(device.client_id)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    entry, data={**entry.data, CONF_AUTH: auth}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={"name": entry.title},
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a controller found via mDNS (_http._tcp, name supergreencontroller*)."""
        host = str(discovery_info.ip_address)
        session = async_get_clientsession(self.hass)
        api = SuperGreenAPI(host, session)
        try:
            device = await async_detect_device(api)
        except SuperGreenApiError:
            # Not reachable, needs auth, or not actually an SGL controller.
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(device.client_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        self._discovered = {CONF_HOST: host, "name": device.name}
        self.context["title_placeholders"] = {"name": device.name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm adding a discovered controller."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovered["name"],
                data={CONF_HOST: self._discovered[CONF_HOST], CONF_AUTH: None},
            )
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": self._discovered["name"]},
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Track a controller's IP via DHCP (name-independent).

        With ``registered_devices`` this mostly fires for already-configured
        controllers whose lease changed: we just update the stored host. The
        chip MAC is our unique id, so this works no matter what the device was
        renamed to. If an unknown controller turns up, fall back to confirming.
        """
        await self.async_set_unique_id(discovery_info.macaddress)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})

        device, error = await self._async_probe(discovery_info.ip, None)
        if error:
            return self.async_abort(reason="cannot_connect")
        assert device is not None
        self._discovered = {CONF_HOST: discovery_info.ip, "name": device.name}
        self.context["title_placeholders"] = {"name": device.name}
        return await self.async_step_zeroconf_confirm()

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
