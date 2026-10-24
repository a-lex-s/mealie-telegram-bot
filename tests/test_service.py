import json

import httpx
import pytest

from mealie_bot.features.shopping.parser import ParsedEntry
from mealie_bot.features.shopping.service import (
    AssignResult,
    FoodIndex,
    LabelIndex,
    NoShoppingListError,
    ShoppingService,
    UnitResolver,
)
from mealie_bot.i18n import unit_synonyms
from mealie_bot.mealie import MealieError
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
    assert await service.undo_add(result) == 2
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


async def test_view_reads_the_label_order(service, mealie_mock):
    mealie_mock.get(f"/api/households/shopping/lists/{LIST_ID}").respond(
        json={
            "id": LIST_ID,
            "name": "Groceries",
            "listItems": [],
            "labelSettings": [
                {"labelId": "l-2", "position": 1},
                {"labelId": "l-1", "position": 0},
                {"labelId": None, "position": 5},
            ],
        }
    )
    view = await service.view(LIST_ID)
    assert view.label_order == {"l-2": 1, "l-1": 0}


# --- categories ---------------------------------------------------------------

LABELS = [
    {"id": "lab-1", "name": "Würzmittel", "color": "#9b7bb8", "groupId": "g"},
    {"id": "lab-2", "name": "🧴 Drogerie", "color": "#959595", "groupId": "g"},
]


def test_label_index_finds_with_and_without_emoji_and_similar_names():
    index = LabelIndex(LABELS)
    assert index.find("würzmittel")["id"] == "lab-1"
    assert index.find("Drogerie")["id"] == "lab-2"
    assert index.find("🧴 Drogerie")["id"] == "lab-2"
    assert index.find("🧴Drogerie")["id"] == "lab-2"
    assert index.find("Haushalt") is None
    assert index.similar("Würzmitel")["id"] == "lab-1"
    assert index.similar("Haushalt") is None
    assert [label["id"] for label in index.labels] == ["lab-2", "lab-1"]  # by name


def test_food_index_similar():
    index = FoodIndex([make_food("f-1", "Ketchup"), make_food("f-2", "Milch")])
    assert index.similar("Ketchap")["id"] == "f-1"
    assert index.similar("Eier") is None


async def test_create_label_uses_the_emoji_colour_and_refreshes_the_cache(service, mealie_mock):
    labels = mealie_mock.get("/api/groups/labels").respond(json={"items": LABELS})
    post = mealie_mock.post("/api/groups/labels").respond(
        201, json={"id": "lab-3", "name": "Obst", "color": "#d9534f", "groupId": "g"}
    )
    assert await service.find_label("Obst") is None
    label = await service.create_label("Obst")
    assert json.loads(post.calls.last.request.content) == {"name": "Obst", "color": "#d9534f"}
    await service.create_label("Obst", {"obst": "🥛"})  # LABEL_EMOJI overrides count
    assert json.loads(post.calls.last.request.content)["color"] == "#5bc0de"
    assert label["id"] == "lab-3"
    labels.respond(json={"items": [*LABELS, label]})
    assert (await service.find_label("obst"))["id"] == "lab-3"
    assert labels.call_count == 2


async def test_assign_creates_foods_relabels_foods_and_updates_items(service, mealie_mock):
    mealie_mock.get("/api/units").respond(json={"items": UNITS})
    senf = make_food("f-senf", "Senf", "lab-old", aliases=["mustard"])
    senf["substitutions"] = [{"substituteFood": {"id": "f-dijon", "name": "Dijon"}, "note": "x"}]
    senf["label"] = {"id": "lab-old", "name": "Old"}
    foods = mealie_mock.get("/api/foods").respond(json={"items": [senf]})
    senf_item = make_item("i-1", "Senf", foodId="f-senf", labelId="lab-old", food={"id": "f-senf"})
    note_item = make_item("i-2", "ketchup", note="ketchup")
    other = make_item("i-3", "Milch", note="Milch")
    mealie_mock.get(f"/api/households/shopping/lists/{LIST_ID}").respond(
        json={"id": LIST_ID, "name": "Groceries", "listItems": [senf_item, note_item, other]}
    )
    create = mealie_mock.post("/api/foods").respond(
        201, json={"id": "f-ketchup", "name": "Ketchup", "labelId": "lab-1"}
    )
    put_food = mealie_mock.put("/api/foods/f-senf").respond(
        json={**make_food("f-senf", "Senf", "lab-1")}
    )
    put_items = mealie_mock.put(url__regex=r"/api/households/shopping/items/.*").respond(json={})

    result = await service.assign(LIST_ID, ["Ketchup", "mustard"], LABELS[0], {})

    assert json.loads(create.calls.last.request.content) == {"name": "Ketchup", "labelId": "lab-1"}
    food_body = json.loads(put_food.calls.last.request.content)
    assert food_body["labelId"] == "lab-1" and food_body["aliases"] == [{"name": "mustard"}]
    assert "label" not in food_body  # only the fields PUT accepts
    # Substitutions are kept, in the shape PUT accepts.
    assert food_body["substitutions"] == [{"substituteFoodId": "f-dijon", "note": "x"}]
    bodies = {
        call.request.url.path.rsplit("/", 1)[1]: json.loads(call.request.content)
        for call in put_items.calls
    }
    assert set(bodies) == {"i-1", "i-2"}  # the unrelated note item is untouched
    assert bodies["i-2"]["foodId"] == "f-ketchup" and bodies["i-2"]["labelId"] == "lab-1"
    assert bodies["i-2"]["note"] == "" and "display" not in bodies["i-2"]
    assert bodies["i-1"]["labelId"] == "lab-1" and bodies["i-1"]["foodId"] == "f-senf"
    assert [name for name, _ in result.assigned] == ["Ketchup", "Senf"]
    assert result.created_food_ids == ["f-ketchup"]
    assert [food["id"] for food in result.previous_foods] == ["f-senf"]
    assert [item["id"] for item in result.previous_items] == ["i-2", "i-1"]
    assert result.undoable
    # The food cache is dropped so the new food is found right away.
    assert foods.call_count == 1
    await service.foods()
    assert foods.call_count == 2


async def test_assign_with_a_chosen_food_skips_the_lookup(service, mealie_mock):
    mealie_mock.get("/api/foods").respond(json={"items": []})
    mealie_mock.get(f"/api/households/shopping/lists/{LIST_ID}").respond(
        json={"id": LIST_ID, "name": "Groceries", "listItems": []}
    )
    chosen = make_food("f-k", "Ketchup", "lab-1")
    create = mealie_mock.post("/api/foods")
    result = await service.assign(LIST_ID, ["Ketchap"], LABELS[0], {"Ketchap": chosen})
    assert not create.called  # already in the label: nothing to write
    assert result.assigned == [("Ketchup", LABELS[0])] and not result.undoable


async def test_undo_assign_restores_items_and_foods_then_deletes_created(service, mealie_mock):
    calls = []
    for method, pattern in (
        ("PUT", r"/api/households/shopping/items/.*"),
        ("PUT", r"/api/foods/.*"),
        ("DELETE", r"/api/foods/.*"),
    ):
        mealie_mock.route(method=method, url__regex=pattern).mock(
            side_effect=lambda request: (
                (calls.append((request.method, request.url.path)), 200)
                and httpx.Response(200, json={})
            )
        )
    result = AssignResult(
        assigned=[("Ketchup", LABELS[0]), ("Senf", LABELS[0])],
        created_food_ids=["f-ketchup"],
        previous_foods=[make_food("f-senf", "Senf", "lab-old")],
        previous_items=[make_item("i-2", "Ketchup", note="Ketchup", label=None)],
    )
    assert await service.undo_assign(result) == 2
    assert calls == [
        ("PUT", "/api/households/shopping/items/i-2"),
        ("PUT", "/api/foods/f-senf"),
        ("DELETE", "/api/foods/f-ketchup"),
    ]


async def test_label_counts(service, mealie_mock):
    mealie_mock.get("/api/groups/labels").respond(json={"items": LABELS})
    mealie_mock.get("/api/foods").respond(
        json={
            "items": [
                make_food("f-1", "Senf", "lab-1"),
                make_food("f-2", "Ketchup", "lab-1"),
                make_food("f-3", "Milch"),
            ]
        }
    )
    mealie_mock.get(f"/api/households/shopping/lists/{LIST_ID}").respond(
        json={
            "id": LIST_ID,
            "name": "Groceries",
            "listItems": [
                make_item("i-1", "Milch"),
                make_item("i-2", "Senf", label="Würzmittel"),
                make_item("i-3", "Seife", checked=True),
            ],
        }
    )
    counts = await service.label_counts(LIST_ID)
    assert [label["id"] for label in counts.labels] == ["lab-2", "lab-1"]
    assert counts.foods_per_label == {"lab-1": 2}
    assert counts.foods_without_label == 1
    assert counts.items_without_label == 1  # ticked-off items do not count


# --- SHOPPING_CREATE_FOODS ------------------------------------------------


@pytest.fixture
def creating(client, mealie_mock):
    mealie_mock.get("/api/units").respond(json={"items": UNITS})
    mealie_mock.get("/api/foods").respond(json={"items": [make_food("f-milk", "Milch", "lab")]})
    mealie_mock.get(f"/api/households/shopping/lists/{LIST_ID}").respond(
        json={"id": LIST_ID, "listItems": []}
    )
    return ShoppingService(client, create_foods=True)


async def test_unknown_names_become_foods_once(creating, mealie_mock):
    ids = iter(["f-new-1", "f-new-2"])
    foods = mealie_mock.post("/api/foods").mock(
        side_effect=lambda request: httpx.Response(
            201, json={"id": next(ids), **json.loads(request.content)}
        )
    )
    bulk = mealie_mock.post("/api/households/shopping/items/create-bulk").respond(
        201, json={"createdItems": [make_item("n-1", "x")]}
    )
    entries = [
        ParsedEntry("Ketchup"),
        ParsedEntry("ketchup", 2),
        ParsedEntry("Milch"),
        ParsedEntry("Tomaten", 2, "Netz"),
    ]
    result = await creating.add_entries(LIST_ID, entries)
    assert [json.loads(c.request.content) for c in foods.calls] == [
        {"name": "Ketchup"},
        {"name": "Tomaten"},
    ]
    body = json.loads(bulk.calls.last.request.content)
    assert [(i.get("foodId"), i["note"]) for i in body] == [
        ("f-new-1", ""),
        ("f-new-1", ""),
        ("f-milk", ""),
        ("f-new-2", "Netz"),  # the unknown unit stays in the note
    ]
    assert "labelId" not in body[0]  # a created food has no category yet
    assert result.created_food_ids == ["f-new-1", "f-new-2"] and result.undoable


async def test_failed_add_deletes_the_created_foods(creating, mealie_mock):
    mealie_mock.post("/api/foods").respond(201, json={"id": "f-new", "name": "Ketchup"})
    mealie_mock.post("/api/households/shopping/items/create-bulk").respond(500)
    delete = mealie_mock.delete("/api/foods/f-new").respond(json={})
    with pytest.raises(MealieError):
        await creating.add_entries(LIST_ID, [ParsedEntry("Ketchup")])
    assert delete.called


async def test_undo_add_deletes_created_foods_after_the_items(creating, mealie_mock):
    from mealie_bot.features.shopping.service import AddResult

    calls = []
    mealie_mock.delete("/api/households/shopping/items").mock(
        side_effect=lambda request: calls.append("items") or httpx.Response(200, json={})
    )
    mealie_mock.delete("/api/foods/f-new").mock(
        side_effect=lambda request: calls.append("food") or httpx.Response(200, json={})
    )
    result = AddResult(created=[make_item("n-1", "Ketchup")], created_food_ids=["f-new"])
    assert await creating.undo_add(result) == 1
    assert calls == ["items", "food"]


async def test_undo_add_keeps_going_when_a_food_cannot_be_deleted(creating, mealie_mock):
    from mealie_bot.features.shopping.service import AddResult

    mealie_mock.delete("/api/households/shopping/items").respond(json={})
    mealie_mock.delete("/api/foods/f-1").respond(500)
    second = mealie_mock.delete("/api/foods/f-2").respond(json={})
    result = AddResult(created=[make_item("n-1", "Ketchup")], created_food_ids=["f-1", "f-2"])
    assert await creating.undo_add(result) == 1
    assert second.called


async def test_no_foods_are_created_by_default(client, mealie_mock):
    mealie_mock.get("/api/units").respond(json={"items": []})
    mealie_mock.get("/api/foods").respond(json={"items": []})
    foods = mealie_mock.post("/api/foods").respond(201, json={"id": "f"})
    item = await ShoppingService(client).build_item(LIST_ID, ParsedEntry("Ketchup"), {})
    assert item["note"] == "Ketchup" and "foodId" not in item and not foods.called
