"""Shopping list operations on top of the Mealie client."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from mealie_bot.features.shopping.parser import ParsedEntry
from mealie_bot.i18n import unit_synonyms
from mealie_bot.mealie import MealieClient
from mealie_bot.mealie.client import JSON

# Fields accepted by PUT /api/households/shopping/items/{id} (ShoppingListItemUpdate).
_UPDATE_FIELDS = (
    "shoppingListId",
    "quantity",
    "note",
    "display",
    "checked",
    "position",
    "foodId",
    "labelId",
    "unitId",
    "extras",
    "recipeReferences",
)


class NoShoppingListError(Exception):
    pass


def _spellings(entity: JSON) -> set[str]:
    """Every name Mealie knows a unit or food by, case-folded."""
    names = {
        entity.get(key) for key in ("name", "pluralName", "abbreviation", "pluralAbbreviation")
    }
    names.update(alias.get("name") for alias in entity.get("aliases") or [])
    return {name.strip().casefold() for name in names if isinstance(name, str) and name.strip()}


class FoodIndex:
    """Exact, case-insensitive lookup of Mealie foods by name, plural name or alias."""

    def __init__(self, foods: list[JSON]) -> None:
        self._by_spelling: dict[str, JSON] = {}
        for food in foods:
            for spelling in _spellings(food):
                self._by_spelling.setdefault(spelling, food)

    def find(self, name: str) -> JSON | None:
        return self._by_spelling.get(name.strip().casefold())


class UnitResolver:
    """Maps what users type ("Liter", "l", "Stk") to a Mealie unit."""

    def __init__(self, units: list[JSON], synonyms: dict[str, frozenset[str]]) -> None:
        self._by_spelling: dict[str, JSON] = {}
        for unit in units:
            for spelling in _spellings(unit):
                self._by_spelling.setdefault(spelling, unit)
        self._synonyms = synonyms
        self.known_tokens: frozenset[str] = frozenset(self._by_spelling).union(*synonyms.values())

    def resolve(self, token: str) -> JSON | None:
        folded = token.casefold()
        if folded in self._by_spelling:
            return self._by_spelling[folded]
        for spellings in self._synonyms.values():
            if folded in spellings:
                for spelling in sorted(spellings):
                    if spelling in self._by_spelling:
                        return self._by_spelling[spelling]
        return None


@dataclass(frozen=True)
class AddResult:
    """Outcome of one bulk create: new items, merged items and their old versions."""

    created: list[JSON] = field(default_factory=list)
    updated: list[JSON] = field(default_factory=list)
    previous: list[JSON] = field(default_factory=list)

    @property
    def items(self) -> list[JSON]:
        """Everything Mealie stored for the request: new items and merged ones."""
        return self.created + self.updated

    @property
    def undoable(self) -> bool:
        """True if undo_add would change anything (created items or known previous versions)."""
        return bool(self.created or self.previous)


@dataclass(frozen=True)
class ListView:
    id: str
    name: str
    items: list[JSON]


class ShoppingService:
    def __init__(
        self,
        client: MealieClient,
        default_list: str | None = None,
        unit_cache_seconds: float = 600,
        food_recheck_seconds: float = 60,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._default_list = default_list
        self._selected: dict[int, str] = {}
        self._unit_cache_seconds = unit_cache_seconds
        self._food_recheck_seconds = food_recheck_seconds
        self._clock = clock
        self._units: UnitResolver | None = None
        self._units_loaded_at = 0.0
        self._foods: FoodIndex | None = None
        self._foods_loaded_at = 0.0

    # --- lists ------------------------------------------------------------

    async def lists(self) -> list[JSON]:
        return await self._client.get_shopping_lists()

    async def active_list(self, user_id: int) -> JSON:
        return self.pick_list(await self.lists(), user_id)

    def pick_list(self, lists: list[JSON], user_id: int) -> JSON:
        """The user's active list: their choice, then SHOPPING_LIST, then the first list."""
        if not lists:
            raise NoShoppingListError
        wanted = [self._selected.get(user_id), self._default_list]
        for key in filter(None, wanted):
            for shopping_list in lists:
                if (
                    key == shopping_list["id"]
                    or key.casefold() == (shopping_list.get("name") or "").casefold()
                ):
                    return shopping_list
        return lists[0]

    def select_list(self, user_id: int, list_id: str) -> None:
        self._selected[user_id] = list_id

    async def view(self, list_id: str) -> ListView:
        data = await self._client.get_shopping_list(list_id)
        return ListView(
            id=data["id"], name=data.get("name") or "", items=list(data.get("listItems") or [])
        )

    # --- items ------------------------------------------------------------

    async def units(self) -> UnitResolver:
        now = self._clock()
        if self._units is None or now - self._units_loaded_at > self._unit_cache_seconds:
            self._units = UnitResolver(await self._client.get_units(), unit_synonyms())
            self._units_loaded_at = now
        return self._units

    async def foods(self, *, reload: bool = False) -> FoodIndex:
        """All Mealie foods, cached like the units; ``reload`` forces a fresh copy."""
        now = self._clock()
        if self._foods is None or reload or now - self._foods_loaded_at > self._unit_cache_seconds:
            self._foods = FoodIndex(await self._client.get_foods())
            self._foods_loaded_at = now
        return self._foods

    async def find_food(self, name: str) -> JSON | None:
        """Exact match among all foods. A miss on a cache older than a minute
        reloads the foods once, so a food just created in Mealie is found."""
        food = (await self.foods()).find(name)
        if food is None and self._clock() - self._foods_loaded_at > self._food_recheck_seconds:
            food = (await self.foods(reload=True)).find(name)
        return food

    async def build_item(self, list_id: str, entry: ParsedEntry) -> JSON:
        units = await self.units()
        item: JSON = {
            "shoppingListId": list_id,
            "quantity": entry.quantity if entry.quantity is not None else 1,
            "checked": False,
            "note": "",
        }
        unit = units.resolve(entry.unit) if entry.unit else None
        if unit is not None:
            item["unitId"] = unit["id"]
        food = await self.find_food(entry.name)
        if food is None:
            # Unknown food: keep everything as free text so nothing is lost.
            item["note"] = (
                f"{entry.unit} {entry.name}" if entry.unit and unit is None else entry.name
            )
        else:
            item["foodId"] = food["id"]
            if food.get("labelId"):
                item["labelId"] = food["labelId"]
            if entry.unit and unit is None:
                # Unknown unit: the food keeps its category, the unit goes into the note.
                item["note"] = entry.unit
        return item

    async def add_entries(self, list_id: str, entries: list[ParsedEntry]) -> AddResult:
        """Create the entries in one bulk request and return what Mealie did with them.

        Mealie merges an entry into an existing unchecked item with the same
        food/unit/note; those come back as ``updated`` together with the
        previous version, so the change can be undone.
        """
        items = [await self.build_item(list_id, entry) for entry in entries]
        if not items:
            return AddResult()
        before = {item["id"]: item for item in (await self.view(list_id)).items}
        result = await self._client.create_items(items) or {}
        created = list(result.get("createdItems") or [])
        updated = list(result.get("updatedItems") or [])
        previous = [before[item["id"]] for item in updated if item["id"] in before]
        return AddResult(created=created, updated=updated, previous=previous)

    async def undo_add(self, result: AddResult) -> int:
        """Revert one ``add_entries`` call. Returns the number of entries reverted."""
        await self._client.delete_items([item["id"] for item in result.created])
        for item in result.previous:
            payload = {key: item[key] for key in _UPDATE_FIELDS if key in item}
            await self._client.update_item(item["id"], payload)
        return len(result.created) + len(result.previous)

    async def set_checked(self, item_id: str, checked: bool) -> JSON:
        """Tick an item off (or put it back) and return the item as it was before."""
        current = await self._client.get_item(item_id)
        payload = {key: current[key] for key in _UPDATE_FIELDS if key in current}
        payload["checked"] = checked
        await self._client.update_item(item_id, payload)
        return current

    async def checked_items(self, list_id: str) -> list[JSON]:
        return [item for item in (await self.view(list_id)).items if item.get("checked")]

    async def clear_checked(self, list_id: str) -> list[JSON]:
        """Delete all ticked-off items and return them."""
        items = await self.checked_items(list_id)
        await self._client.delete_items([item["id"] for item in items])
        return items
