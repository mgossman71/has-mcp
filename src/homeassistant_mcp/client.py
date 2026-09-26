"""Async Home Assistant REST API client."""

from __future__ import annotations

from typing import Any

import aiohttp

from .config import Config


class HomeAssistantClient:
    """Minimal async client for the Home Assistant REST API."""

    def __init__(self, config: Config):
        self._config = config
        self._session: aiohttp.ClientSession | None = None

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._config.token}",
            "Content-Type": "application/json",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                base_url=self._config.base_url,
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=10),
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_states(self, entity_id: str) -> list[dict[str, Any]]:
        """GET /api/states — returns list of state dicts."""
        session = await self._get_session()
        async with session.get("/api/states") as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get_state(self, entity_id: str) -> dict[str, Any]:
        """GET /api/states/{entity_id} — returns a single state dict."""
        session = await self._get_session()
        async with session.get(f"/api/states/{entity_id}") as resp:
            if resp.status == 404:
                raise ValueError(f"Entity '{entity_id}' not found in Home Assistant")
            resp.raise_for_status()
            return await resp.json()

    async def call_service(
        self, domain: str, service: str, data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """POST /api/services/{domain}/{service}"""
        session = await self._get_session()
        payload = data or {}
        async with session.post(
            f"/api/services/{domain}/{service}", json=payload
        ) as resp:
            if resp.status == 404:
                # Service returned empty result (e.g. entity not found)
                try:
                    return await resp.json()
                except Exception:
                    return {}
            resp.raise_for_status()
            try:
                return await resp.json()
            except Exception:
                return {}