"""Thin async client for the parts of the Mealie API the bot uses.

All paths were checked against the OpenAPI document of Mealie v3.29.0.
Responses are returned as plain dicts (camelCase keys, as Mealie sends them).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)

JSON = dict[str, Any]

# Idempotent methods are retried once after a connection problem (Mealie restarting,
# a dropped connection). POST is not: a repeated create-bulk would duplicate items.
_RETRY_METHODS = frozenset({"GET", "PUT", "DELETE"})
RETRY_DELAY_SECONDS = 0.5


class MealieError(Exception):
    """Mealie could not be reached or answered with an error."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class MealieNotFound(MealieError):
    pass


class MealieClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=timeout,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self._send(method, path, **kwargs)
        except httpx.HTTPError as exc:
            # The exception text never contains the Authorization header.
            raise MealieError(f"{method} {path} failed: {type(exc).__name__}") from None
        if response.status_code == 404:
            raise MealieNotFound(f"{method} {path}: not found", 404)
        if response.is_error:
            raise MealieError(
                f"{method} {path} returned HTTP {response.status_code}", response.status_code
            )
        if not response.content:
            return None
        return response.json()

    async def _request_json(self, method: str, path: str, **kwargs: Any) -> JSON:
        data = await self._request(method, path, **kwargs)
        if not isinstance(data, dict):
            raise MealieError(f"{method} {path}: unexpected response body")
        return data

    async def _send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            return await self._http.request(method, path, **kwargs)
        except httpx.TransportError as exc:
            if method not in _RETRY_METHODS:
                raise
            log.info("Retrying %s %s after %s", method, path, type(exc).__name__)
            await asyncio.sleep(RETRY_DELAY_SECONDS)
            return await self._http.request(method, path, **kwargs)

    # --- app / user -------------------------------------------------------

    async def get_app_info(self) -> JSON:
        return await self._request_json("GET", "/api/app/about")

    async def get_self(self) -> JSON:
        return await self._request_json("GET", "/api/users/self")

    # --- shopping lists ---------------------------------------------------

    async def get_shopping_lists(self) -> list[JSON]:
        data = await self._request(
            "GET",
            "/api/households/shopping/lists",
            params={"perPage": -1, "orderBy": "name", "orderDirection": "asc"},
        )
        return list(data.get("items", []))

    async def get_shopping_list(self, list_id: str) -> JSON:
        return await self._request_json("GET", f"/api/households/shopping/lists/{list_id}")

    # --- shopping list items ---------------------------------------------

    async def get_item(self, item_id: str) -> JSON:
        return await self._request_json("GET", f"/api/households/shopping/items/{item_id}")

    async def create_items(self, items: list[JSON]) -> JSON:
        """POST create-bulk; Mealie merges duplicates of unchecked items itself."""
        return await self._request_json(
            "POST", "/api/households/shopping/items/create-bulk", json=items
        )

    async def update_item(self, item_id: str, item: JSON) -> JSON:
        """PUT replaces the whole item, so pass the complete current item."""
        return await self._request_json(
            "PUT", f"/api/households/shopping/items/{item_id}", json=item
        )

    async def delete_items(self, item_ids: list[str]) -> None:
        if not item_ids:
            return
        await self._request(
            "DELETE", "/api/households/shopping/items", params=[("ids", i) for i in item_ids]
        )

    # --- foods / units ----------------------------------------------------

    async def get_foods(self) -> list[JSON]:
        data = await self._request("GET", "/api/foods", params={"perPage": -1})
        return list(data.get("items", []))

    async def get_units(self) -> list[JSON]:
        data = await self._request("GET", "/api/units", params={"perPage": -1})
        return list(data.get("items", []))
