import json

import pytest

from mealie_bot.features.shopping.parser import ParsedEntry
from mealie_bot.features.shopping.service import (
    NoShoppingListError,
    ShoppingService,
    UnitResolver,
)
from mealie_bot.i18n import unit_synonyms
from tests.conftest import LIST_ID, OTHER_LIST_ID, make_food, make_item, make_unit

UNITS = [
    make_unit("u-l", "Liter", "l"),
    make_unit("u-g", "Gramm", "g"),
    make_unit("u-bund", "Bund"),
    make_unit("u-dose", "Dose", plural="Dosen", aliases=["can"]),
]
LISTS = {
    "items": [
        {"id": LIST_ID, "name": "Groceries"},
        {"id": OTHER_LIST_ID, "name": "Hardware"},
    ]
}


@pytest.fixture
def service(client):
    return ShoppingService(client)


def test_unit_resolver():
    resolver = UnitResolver(UNITS, unit_synonyms())
    assert resolver.resolve("L")["id"] == "u-l"
    assert resolver.resolve("litre")["id"] == "u-l"
    assert resolver.resolve("Dosen")["id"] == "u-dose"
    assert resolver.resolve("tins")["id"] == "u-dose"
    assert resolver.resolve("bunch")["id"] == "u-bund"
    assert resolver.resolve("kg") is None
    assert "liter" in resolver.known_tokens
    assert "kg" in resolver.known_tokens


async def test_active_list_default_and_selection(client, mealie_mock):
    mealie_mock.get("/api/households/shopping/lists").respond(json=LISTS)
    service = ShoppingService(client, default_list="hardware")
    assert (await service.active_list(1))["id"] == OTHER_LIST_ID
    service.select_list(1, LIST_ID)
    assert (await service.active_list(1))["id"] == LIST_ID
    assert (await service.active_list(2))["id"] == OTHER_LIST_ID


async def test_active_list_falls_back_to_first(service, mealie_mock):
    mealie_mock.get("/api/households/shopping/lists").respond(json=LISTS)
    assert (await service.active_list(1))["id"] == LIST_ID


async def test_no_lists(service, mealie_mock):
    mealie_mock.get("/api/households/shopping/lists").respond(json={"items": []})
    with pytest.raises(NoShoppingListError):
        await service.active_list(1)


async def test_build_item_with_food_and_unit(service, mealie_mock):
    mealie_mock.get("/api/units").respond(json={"items": UNITS})
    mealie_mock.get("/api/foods").respond(
        json={"items": [make_food("f-1", "Milchreis"), make_food("f-2", "milch", "lab-1")]}
    )
    item = await service.build_item(LIST_ID, ParsedEntry("Milch", 2, "l"))
    assert item == {
        "shoppingListId": LIST_ID,
        "quantity": 2,
        "checked": False,
        "note": "",
        "unitId": "u-l",
        "foodId": "f-2",
        "labelId": "lab-1",
    }


async def test_build_item_matches_food_plural_and_alias(service, mealie_mock):
    mealie_mock.get("/api/units").respond(json={"items": UNITS})
    mealie_mock.get("/api/foods").respond(
        json={"items": [make_food("f-egg", "Ei", plural="Eier", aliases=["egg"])]}
    )
    assert (await service.build_item(LIST_ID, ParsedEntry("Eier")))["foodId"] == "f-egg"
    assert (await service.build_item(LIST_ID, ParsedEntry("EGG")))["foodId"] == "f-egg"


async def test_build_item_without_food_is_note(service, mealie_mock):
    mealie_mock.get("/api/units").respond(json={"items": UNITS})
    mealie_mock.get("/api/foods").respond(json={"items": []})
    item = await service.build_item(LIST_ID, ParsedEntry("Spülmittel"))
    assert item == {
        "shoppingListId": LIST_ID,
        "quantity": 1,
        "checked": False,
        "note": "Spülmittel",
    }


async def test_build_item_unknown_unit_keeps_text(service, mealie_mock):
    mealie_mock.get("/api/units").respond(json={"items": UNITS})
    mealie_mock.get("/api/foods").respond(json={"items": []})
    item = await service.build_item(LIST_ID, ParsedEntry("Mehl", 1, "kg"))
    assert item["note"] == "kg Mehl"
    assert "unitId" not in item


async def test_build_item_unknown_unit_still_matches_the_food(service, mealie_mock):
    mealie_mock.get("/api/units").respond(json={"items": UNITS})
    mealie_mock.get("/api/foods").respond(json={"items": [make_food("f-t", "Tomaten", "lab-v")]})
    item = await service.build_item(LIST_ID, ParsedEntry("Tomaten", 2, "Netz"))
    assert item["foodId"] == "f-t" and item["labelId"] == "lab-v"
    assert item["note"] == "Netz" and "unitId" not in item


async def test_foods_are_cached_and_rechecked_on_a_miss(client, mealie_mock):
    now = [0.0]
    service = ShoppingService(client, food_recheck_seconds=60, clock=lambda: now[0])
    route = mealie_mock.get("/api/foods").respond(json={"items": [make_food("f-1", "Milch")]})
    assert (await service.find_food("milch"))["id"] == "f-1"
    assert await service.find_food("Eier") is None
    assert route.call_count == 1  # a miss on a fresh cache does not reload
    now[0] = 61
    route.respond(json={"items": [make_food("f-1", "Milch"), make_food("f-2", "Eier")]})
    assert (await service.find_food("Eier"))["id"] == "f-2"
    assert route.call_count == 2
    assert route.calls.last.request.url.params["perPage"] == "-1"


async def test_units_are_cached(client, mealie_mock):
    now = [0.0]
    service = ShoppingService(client, unit_cache_seconds=60, clock=lambda: now[0])
    route = mealie_mock.get("/api/units").respond(json={"items": UNITS})
    await service.units()
    await service.units()
    assert route.call_count == 1
    now[0] = 61
    await service.units()
    assert route.call_count == 2


async def test_add_entries_posts_bulk_and_reports_merges(service, mealie_mock):
    mealie_mock.get("/api/units").respond(json={"items": UNITS})
    mealie_mock.get("/api/foods").respond(json={"items": []})
    existing = make_item("old", "a", quantity=1)
    mealie_mock.get(f"/api/households/shopping/lists/{LIST_ID}").respond(
        json={"id": LIST_ID, "name": "Groceries", "listItems": [existing]}
    )
    route = mealie_mock.post("/api/households/shopping/items/create-bulk").respond(
        201,
        json={
            "createdItems": [make_item("new", "b")],
            "updatedItems": [{**existing, "quantity": 2}],
        },
    )
    result = await service.add_entries(LIST_ID, [ParsedEntry("a"), ParsedEntry("b")])
    body = json.loads(route.calls.last.request.content)
    assert [i["note"] for i in body] == ["a", "b"]
    assert [i["id"] for i in result.items] == ["new", "old"]
    assert result.previous == [existing]
    assert result.undoable


async def test_add_nothing(service, mealie_mock):
    result = await service.add_entries(LIST_ID, [])
    assert not result.items and not result.undoable


async def test_undo_add(service, mealie_mock):
    from mealie_bot.features.shopping.service import AddResult

    previous = make_item("old", "a", quantity=1, recipeReferences=[])
    delete = mealie_mock.delete("/api/households/shopping/items").respond(json={})
    put = mealie_mock.put("/api/households/shopping/items/old").respond(json={})
    result = AddResult(created=[make_item("new", "b")], updated=[previous], previous=[previous])
    assert await service.undo_add([i["id"] for i in result.created], result.previous) == 2
    assert delete.calls.last.request.url.params.get_list("ids") == ["new"]
    body = json.loads(put.calls.last.request.content)
    assert body["quantity"] == 1 and "groupId" not in body


async def test_set_checked_sends_full_update(service, mealie_mock):
    current = make_item(
        "i-1",
        "2 l Milch",
        unit={"id": "u-l", "name": "Liter"},
        unitId="u-l",
        createdAt="2026-01-01T00:00:00",
        recipeReferences=[],
    )
    mealie_mock.get("/api/households/shopping/items/i-1").respond(json=current)
    route = mealie_mock.put("/api/households/shopping/items/i-1").respond(json={})
    assert await service.set_checked("i-1", True) == current
    body = json.loads(route.calls.last.request.content)
    assert body["checked"] is True
    assert body["unitId"] == "u-l"
    assert body["shoppingListId"] == current["shoppingListId"]
    assert "unit" not in body and "createdAt" not in body and "groupId" not in body


async def test_clear_checked(service, mealie_mock):
    mealie_mock.get(f"/api/households/shopping/lists/{LIST_ID}").respond(
        json={
            "id": LIST_ID,
            "name": "Groceries",
            "listItems": [make_item("a", "x", checked=True), make_item("b", "y")],
        }
    )
    route = mealie_mock.delete("/api/households/shopping/items").respond(json={"message": "ok"})
    assert [i["id"] for i in await service.clear_checked(LIST_ID)] == ["a"]
    assert route.calls.last.request.url.params.get_list("ids") == ["a"]
