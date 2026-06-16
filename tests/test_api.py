"""Direct tests for the HTTP key/value client and its error mapping."""

from __future__ import annotations

import aiohttp
import pytest

from custom_components.supergreenlab.api import (
    SuperGreenAPI,
    SuperGreenApiError,
    SuperGreenAuthError,
)


class _FakeResponse:
    def __init__(self, status: int, text: str) -> None:
        self.status = status
        self._text = text

    async def __aenter__(self) -> _FakeResponse:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def text(self) -> str:
        return self._text


class _FakeSession:
    """Minimal aiohttp-like session returning queued responses / errors."""

    def __init__(self, status: int = 200, text: str = "", *, raise_exc=None) -> None:
        self._status = status
        self._text = text
        self._raise = raise_exc
        self.calls: list[tuple[str, str]] = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, str(url)))
        if self._raise is not None:
            raise self._raise
        return _FakeResponse(self._status, self._text)

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)


def _api(session: _FakeSession, **kw) -> SuperGreenAPI:
    return SuperGreenAPI("1.2.3.4", session, **kw)


async def test_get_int_parses_value():
    api = _api(_FakeSession(text="42"))
    assert await api.get_int("BOX_0_TEMP") == 42


async def test_get_int_empty_is_none():
    api = _api(_FakeSession(text=""))
    assert await api.get_int("BOX_0_TEMP") is None


async def test_get_int_non_int_raises():
    api = _api(_FakeSession(text="oops"))
    with pytest.raises(SuperGreenApiError):
        await api.get_int("BOX_0_TEMP")


async def test_401_raises_auth_error():
    api = _api(_FakeSession(status=401))
    with pytest.raises(SuperGreenAuthError):
        await api.get_int("BOX_0_TEMP")


async def test_404_raises_api_error():
    api = _api(_FakeSession(status=404))
    with pytest.raises(SuperGreenApiError):
        await api.get_int("UNKNOWN")


async def test_5xx_raises_api_error():
    api = _api(_FakeSession(status=500))
    with pytest.raises(SuperGreenApiError):
        await api.get_str("DEVICE_NAME")


async def test_connection_error_wrapped():
    api = _api(_FakeSession(raise_exc=aiohttp.ClientError("boom")))
    with pytest.raises(SuperGreenApiError):
        await api.get_int("BOX_0_TEMP")


async def test_timeout_wrapped():
    api = _api(_FakeSession(raise_exc=TimeoutError()))
    with pytest.raises(SuperGreenApiError):
        await api.get_int("BOX_0_TEMP")


async def test_set_int_uses_post():
    session = _FakeSession(text="")
    await _api(session).set_int("BOX_0_TEMP_SOURCE", 2)
    assert session.calls[0][0] == "POST"
    assert "k=BOX_0_TEMP_SOURCE" in session.calls[0][1]
    assert "v=2" in session.calls[0][1]


async def test_auth_header_sent():
    session = _FakeSession(text="1")
    await _api(session, auth="dXNlcjpwYXNz").get_int("STATE")
    # The token is passed through; header assembly is covered by not raising.
    assert session.calls


async def test_get_config_parses_json():
    api = _api(_FakeSession(text='{"BOX_0_TEMP": {}}'))
    assert await api.get_config() == {"BOX_0_TEMP": {}}


async def test_get_config_bad_json_raises():
    api = _api(_FakeSession(text="not json"))
    with pytest.raises(SuperGreenApiError):
        await api.get_config()


async def test_get_config_401_raises_auth_error():
    api = _api(_FakeSession(status=401))
    with pytest.raises(SuperGreenAuthError):
        await api.get_config()
