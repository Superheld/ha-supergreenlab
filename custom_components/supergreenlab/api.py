"""Thin async client for the SuperGreenController HTTP/key-value API.

The controller exposes its whole key/value store over a tiny HTTP server:

    GET  /i?k=KEY            -> integer value as plain text
    POST /i?k=KEY&v=123      -> set integer value
    GET  /s?k=KEY            -> string value as plain text
    POST /s?k=KEY&v=...      -> set string value (url-encoded)
    GET  /fs/config.json     -> gzipped key manifest (auto-decompressed)

Authentication is HTTP Basic and only enforced when ``HTTPD_AUTH`` is set on
the device; by default the API is open on the local network.
"""

from __future__ import annotations

import json
from typing import Any

import aiohttp
from yarl import URL


class SuperGreenApiError(Exception):
    """Raised when the controller cannot be reached or returns an error."""


class SuperGreenAPI:
    """Minimal wrapper around the controller's REST endpoints."""

    def __init__(
        self,
        host: str,
        session: aiohttp.ClientSession,
        *,
        auth: str | None = None,
        timeout: int = 10,
    ) -> None:
        """Store connection details.

        ``auth`` is the base64 token stored in the device's ``HTTPD_AUTH`` key
        (i.e. base64("user:password")), or ``None`` when the API is open.
        """
        self._host = host
        self._session = session
        self._auth = auth
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    @property
    def host(self) -> str:
        """Return the controller host/IP."""
        return self._host

    def _headers(self) -> dict[str, str]:
        if self._auth:
            return {"Authorization": f"Basic {self._auth}"}
        return {}

    def _url(self, path: str) -> str:
        return f"http://{self._host}{path}"

    async def _request(self, method: str, path: str, params: dict[str, Any]) -> str:
        # Build the URL ourselves so values are encoded exactly the way the
        # firmware's primitive query parser expects.
        url = URL(self._url(path)).with_query(params)
        try:
            async with self._session.request(
                method, url, headers=self._headers(), timeout=self._timeout
            ) as resp:
                if resp.status == 401:
                    raise SuperGreenApiError("Authentication required or wrong credentials")
                if resp.status == 404:
                    raise SuperGreenApiError(f"Unknown key for {path}: {params!r}")
                if resp.status >= 400:
                    raise SuperGreenApiError(f"HTTP {resp.status} for {url}")
                return (await resp.text()).strip()
        except aiohttp.ClientError as err:
            raise SuperGreenApiError(f"Connection error: {err}") from err
        except TimeoutError as err:
            raise SuperGreenApiError(f"Timeout talking to {self._host}") from err

    async def get_int(self, key: str) -> int | None:
        """Read an integer key. Returns None when the value is empty."""
        raw = await self._request("GET", "/i", {"k": key})
        if raw == "":
            return None
        try:
            return int(raw)
        except ValueError as err:
            raise SuperGreenApiError(f"{key} did not return an int: {raw!r}") from err

    async def get_str(self, key: str) -> str:
        """Read a string key."""
        return await self._request("GET", "/s", {"k": key})

    async def set_int(self, key: str, value: int) -> None:
        """Write an integer key."""
        await self._request("POST", "/i", {"k": key, "v": int(value)})

    async def set_str(self, key: str, value: str) -> None:
        """Write a string key."""
        await self._request("POST", "/s", {"k": key, "v": value})

    async def get_config(self) -> dict[str, Any]:
        """Fetch and parse the device's key manifest (config.json).

        The endpoint is served gzip-encoded; aiohttp transparently decodes it.
        """
        url = self._url("/fs/config.json")
        try:
            async with self._session.get(
                url, headers=self._headers(), timeout=self._timeout
            ) as resp:
                if resp.status >= 400:
                    raise SuperGreenApiError(f"HTTP {resp.status} fetching config.json")
                text = await resp.text()
        except aiohttp.ClientError as err:
            raise SuperGreenApiError(f"Connection error: {err}") from err
        except TimeoutError as err:
            raise SuperGreenApiError(f"Timeout fetching config.json") from err
        try:
            return json.loads(text)
        except json.JSONDecodeError as err:
            raise SuperGreenApiError("config.json is not valid JSON") from err
