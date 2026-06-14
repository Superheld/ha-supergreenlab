"""Fixtures: a dict-backed fake controller so tests run without hardware."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import pytest_asyncio
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.supergreenlab.const import DOMAIN

# A minimal but representative controller state: one enabled box, three LED
# channels on it, the rest unassigned.
DEFAULT_STORE: dict[str, object] = {
    "BROKER_CLIENTID": "abc123",
    "DEVICE_NAME": "Dings",
    "BOX_0_ENABLED": 1,
    "BOX_1_ENABLED": 0,
    "BOX_2_ENABLED": 0,
    "LED_0_BOX": 0,
    "LED_1_BOX": 0,
    "LED_2_BOX": 0,
    "LED_3_BOX": -1,
    "LED_4_BOX": -1,
    "LED_5_BOX": -1,
    "BOX_0_TEMP": 27,
    "BOX_0_HUMI": 48,
    "BOX_0_VPD": 145,
    "BOX_0_CO2": 0,
    "LED_0_DIM": 100,
    "LED_1_DIM": 100,
    "LED_2_DIM": 100,
    "LED_0_TYPE": 0,
    "BOX_0_ON_HOUR": 1,
    "BOX_0_ON_MIN": 0,
    "BOX_0_OFF_HOUR": 21,
    "BOX_0_OFF_MIN": 0,
    "BOX_0_TEMP_SOURCE": 1,
    "STATE": 2,
    "N_RESTARTS": 1,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow loading the custom integration in every test."""
    yield


@pytest.fixture
def store() -> dict[str, object]:
    """A fresh copy of the fake controller's key/value store per test."""
    return dict(DEFAULT_STORE)


@pytest.fixture
def mock_api(store):
    """Patch the HTTP client to read/write the in-memory store."""

    async def get_int(self, key):
        v = store.get(key, 0)
        return None if v is None else int(v)

    async def get_str(self, key):
        return str(store.get(key, ""))

    async def set_int(self, key, value):
        store[key] = int(value)

    async def set_str(self, key, value):
        store[key] = str(value)

    with patch.multiple(
        "custom_components.supergreenlab.api.SuperGreenAPI",
        get_int=get_int,
        get_str=get_str,
        set_int=set_int,
        set_str=set_str,
    ):
        yield store


@pytest_asyncio.fixture
async def setup_entry(hass, mock_api):
    """Set up a configured entry against the fake controller."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={"host": "1.2.3.4", "auth": None}, unique_id="abc123"
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
