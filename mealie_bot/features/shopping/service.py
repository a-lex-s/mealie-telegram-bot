"""Shopping list operations on top of the Mealie client."""

from __future__ import annotations

import difflib
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field

from mealie_bot.features.shopping.parser import ParsedEntry
from mealie_bot.i18n import unit_synonyms
from mealie_bot.i18n.labels import label_color, label_emoji, split_label_name
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

# Fields accepted by PUT /api/foods/{id} (CreateIngredientFood).
_FOOD_FIELDS = (
    "id",
    "name",
    "pluralName",
    "description",
    "extras",
    "labelId",
    "aliases",
    "substitutions",
    "householdsWithIngredientFood",
)
# Two names closer than this (difflib ratio) count as "did you mean".
SIMILARITY_CUTOFF = 0.75


def food_payload(food: JSON, label_id: str | None = None) -> JSON:
    """The food as PUT /api/foods/{id} accepts it, with ``label_id`` set when given.

    PUT replaces the whole food, so everything Mealie returned is sent back;
    substitutions are returned as objects and accepted by id.
    """
    payload = {key: food[key] for key in _FOOD_FIELDS if key in food}
    payload["substitutions"] = [
        {
            "substituteFoodId": sub.get("substituteFoodId")
            or (sub.get("substituteFood") or {}).get("id"),
            "note": sub.get("note") or "",
        }
        for sub in food.get("substitutions") or []
    ]
    if label_id is not None:
        payload["labelId"] = label_id
    return payload


class NoShoppingListError(Exception):
    pass


def _spellings(entity: JSON) -> set[str]:
    """Every name Mealie knows a unit or food by, case-folded."""
    names = {
        entity.get(key) for key in ("name", "pluralName", "abbreviation", "pluralAbbreviation")
    }
    names.update(alias.get("name") for alias in entity.get("aliases") or [])
    return {name.strip().casefold() for name in names if isinstance(name, str) and name.strip()}


def _closest(name: str, spellings: Iterable[str]) -> str | None:
    matches = difflib.get_close_matches(
        name.strip().casefold(), list(spellings), n=1, cutoff=SIMILARITY_CUTOFF
    )
    return matches[0] if matches else None


class FoodIndex:
    """Exact, case-insensitive lookup of Mealie foods by name, plural name or alias."""

    def __init__(self, foods: list[JSON]) -> None:
        self.foods = foods
        self._by_spelling: dict[str, JSON] = {}
        for food in foods:
            for spelling in _spellings(food):
                self._by_spelling.setdefault(spelling, food)

    def find(self, name: str) -> JSON | None:
        return self._by_spelling.get(name.strip().casefold())

    def similar(self, name: str) -> JSON | None:
        """The food whose spelling is closest to ``name`` ("Ketchap" → Ketchup), if close enough."""
        spelling = _closest(name, self._by_spelling)
        return self._by_spelling[spelling] if spelling else None


class LabelIndex:
    """Case-insensitive lookup of Mealie labels by name, with and without a leading emoji."""

    def __init__(self, labels: list[JSON]) -> None:
        self.labels = sorted(
            labels, key=lambda label: split_label_name(str(label.get("name") or ""))[1].casefold()
        )
        self._by_spelling: dict[str, JSON] = {}
        for label in labels:
            name = str(label.get("name") or "")
            for spelling in (name, split_label_name(name)[1]):
                if spelling.strip():
                    self._by_spelling.setdefault(spelling.strip().casefold(), label)

    def find(self, name: str) -> JSON | None:
        return self._by_spelling.get(name.strip().casefold()) or self._by_spelling.get(
            split_label_name(name)[1].casefold()
        )

    def similar(self, name: str) -> JSON | None:
        spelling = _closest(split_label_name(name)[1], self._by_spelling)
        return self._by_spelling[spelling] if spelling else None


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
class AssignResult:
    """Outcome of putting products into a category, with what it takes to undo it."""

    # (product name as Mealie knows it, label) per product.
    assigned: list[tuple[str, JSON]] = field(default_factory=list)
    created_food_ids: list[str] = field(default_factory=list)
    previous_foods: list[JSON] = field(default_factory=list)
    previous_items: list[JSON] = field(default_factory=list)

    def extend(self, other: AssignResult) -> None:
        self.assigned.extend(other.assigned)
        self.created_food_ids.extend(other.created_food_ids)
        self.previous_foods.extend(other.previous_foods)
        self.previous_items.extend(other.previous_items)

    @property
    def undoable(self) -> bool:
        return bool(self.created_food_ids or self.previous_foods or self.previous_items)


@dataclass(frozen=True)
class LabelCounts:
    """For the category overview: foods per label, foods and open list items without one."""

    labels: list[JSON]
    foods_per_label: dict[str, int]
    foods_without_label: int
    items_without_label: int


@dataclass(frozen=True)
class ListView:
    id: str
    name: str
    items: list[JSON]
    # Category order as set in Mealie for this list: label id -> position.
    label_order: dict[str, int] = field(default_factory=dict)


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
        self._labels: LabelIndex | None = None
        self._labels_loaded_at = 0.0

    # --- lists ------------------------------------------------------------

    async def lists(self) -> list[JSON]:
        return await self._client.get_shopping_lists()

    async def active_list(self, chat_id: int) -> JSON:
        return self.pick_list(await self.lists(), chat_id)

    def pick_list(self, lists: list[JSON], chat_id: int) -> JSON:
        """The list a chat works on: chosen with /lists, else SHOPPING_LIST, else the first."""
        if not lists:
            raise NoShoppingListError
        wanted = [self._selected.get(chat_id), self._default_list]
        for key in filter(None, wanted):
            for shopping_list in lists:
                if (
                    key == shopping_list["id"]
                    or key.casefold() == (shopping_list.get("name") or "").casefold()
                ):
                    return shopping_list
        return lists[0]

    def select_list(self, chat_id: int, list_id: str) -> None:
        self._selected[chat_id] = list_id

    async def view(self, list_id: str) -> ListView:
        data = await self._client.get_shopping_list(list_id)
        order = {
            str(setting["labelId"]): int(setting["position"])
            for setting in data.get("labelSettings") or []
            if setting.get("labelId") is not None and setting.get("position") is not None
        }
        return ListView(
            id=data["id"],
            name=data.get("name") or "",
            items=list(data.get("listItems") or []),
            label_order=order,
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

    async def labels(self, *, reload: bool = False) -> LabelIndex:
        """All Mealie labels, cached like the units; ``reload`` forces a fresh copy."""
        now = self._clock()
        if (
            self._labels is None
            or reload
            or now - self._labels_loaded_at > self._unit_cache_seconds
        ):
            self._labels = LabelIndex(await self._client.get_labels())
            self._labels_loaded_at = now
        return self._labels

    async def find_label(self, name: str) -> JSON | None:
        """Exact match among all labels; a miss on a cache older than a minute reloads once."""
        label = (await self.labels()).find(name)
        if label is None and self._clock() - self._labels_loaded_at > self._food_recheck_seconds:
            label = (await self.labels(reload=True)).find(name)
        return label

    async def create_label(self, name: str, emoji: Mapping[str, str] | None = None) -> JSON:
        """Create a label; its colour follows its emoji (``LABEL_EMOJI`` overrides,
        own emoji or the keyword table)."""
        label = await self._client.create_label(name, label_color(label_emoji(name, emoji)))
        self._labels = None
        return label

    # --- categories -------------------------------------------------------

    async def assign(
        self, list_id: str, names: Iterable[str], label: JSON, foods: dict[str, JSON | None]
    ) -> AssignResult:
        """Put products into ``label``: the food keeps the label for good, and the
        list's items for that product follow right away.

        ``foods`` maps a typed name to the food chosen for it; a missing or
        ``None`` entry means a new food is created under that name. Items
        that only carry the name as a note are linked to the food.
        """
        result = AssignResult()
        label_id = str(label["id"])
        items = (await self.view(list_id)).items
        for name in names:
            food = foods.get(name) or (await self.find_food(name))
            if food is None:
                food = await self._client.create_food(name, label_id)
                result.created_food_ids.append(str(food["id"]))
            elif food.get("labelId") != label_id:
                result.previous_foods.append(dict(food))
                payload = food_payload(food, label_id)
                food = {**payload, **(await self._client.update_food(str(food["id"]), payload))}
            result.assigned.append((str(food.get("name") or name), label))
            for item in items:
                is_food = (item.get("foodId") or (item.get("food") or {}).get("id")) == food["id"]
                is_note = not item.get("foodId") and not item.get("food")
                is_note = is_note and (item.get("note") or "").strip().casefold() == name.casefold()
                if (is_food and item.get("labelId") != label_id) or is_note:
                    result.previous_items.append(dict(item))
                    payload = {key: item[key] for key in _UPDATE_FIELDS if key in item}
                    payload.update({"foodId": food["id"], "labelId": label_id})
                    if is_note:
                        # The name moves from the note into the food; Mealie recomputes display.
                        payload["note"] = ""
                        payload.pop("display", None)
                    await self._client.update_item(str(item["id"]), payload)
        self._foods = None
        return result

    async def undo_assign(self, result: AssignResult) -> int:
        """Revert one ``assign``: items first (so created foods are unreferenced), then
        the foods' previous labels, then the created foods. Returns the number of
        products reverted."""
        for item in result.previous_items:
            payload = {key: item[key] for key in _UPDATE_FIELDS if key in item}
            await self._client.update_item(str(item["id"]), payload)
        for food in result.previous_foods:
            await self._client.update_food(str(food["id"]), food_payload(food))
        for food_id in result.created_food_ids:
            await self._client.delete_food(food_id)
        self._foods = None
        return len(result.assigned)

    async def label_counts(self, list_id: str) -> LabelCounts:
        labels = (await self.labels(reload=True)).labels
        foods = (await self.foods(reload=True)).foods
        per_label: dict[str, int] = {}
        for food in foods:
            if food.get("labelId"):
                per_label[str(food["labelId"])] = per_label.get(str(food["labelId"]), 0) + 1
        items = (await self.view(list_id)).items
        return LabelCounts(
            labels=labels,
            foods_per_label=per_label,
            foods_without_label=sum(1 for food in foods if not food.get("labelId")),
            items_without_label=sum(
                1
                for item in items
                if not item.get("checked") and not (item.get("labelId") or item.get("label"))
            ),
        )

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

    async def undo_add(self, created_ids: list[str], previous: list[JSON]) -> int:
        """Revert one ``add_entries`` call: delete the created items and restore the
        previous versions of merged ones. Returns the number of entries reverted."""
        await self._client.delete_items(created_ids)
        for item in previous:
            payload = {key: item[key] for key in _UPDATE_FIELDS if key in item}
            await self._client.update_item(item["id"], payload)
        return len(created_ids) + len(previous)

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
