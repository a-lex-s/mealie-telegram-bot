import httpx
import pytest

from mealie_bot.mealie import MealieError, MealieNotFound
from tests.conftest import LIST_ID, TOKEN


async def test_sends_bearer_token(client, mealie_mock):
    route = mealie_mock.get("/api/users/self").respond(json={"id": "u"})
    await client.get_self()
    assert route.calls.last.request.headers["Authorization"] == f"Bearer {TOKEN}"


async def test_shopping_lists_fetches_all(client, mealie_mock):
    route = mealie_mock.get("/api/households/shopping/lists").respond(
        json={"items": [{"id": LIST_ID, "name": "Groceries"}]}
    )
    lists = await client.get_shopping_lists()
    assert lists == [{"id": LIST_ID, "name": "Groceries"}]
    assert route.calls.last.request.url.params["perPage"] == "-1"


async def test_create_items_uses_bulk_endpoint(client, mealie_mock):
    route = mealie_mock.post("/api/households/shopping/items/create-bulk").respond(
        201, json={"createdItems": [], "updatedItems": [], "deletedItems": []}
    )
    await client.create_items([{"shoppingListId": LIST_ID, "note": "milk"}])
    assert route.called


async def test_delete_items_repeats_ids_param(client, mealie_mock):
    route = mealie_mock.delete("/api/households/shopping/items").respond(json={"message": "ok"})
    await client.delete_items(["a", "b"])
    assert route.calls.last.request.url.params.get_list("ids") == ["a", "b"]


async def test_delete_nothing_makes_no_request(client, mealie_mock):
    route = mealie_mock.delete("/api/households/shopping/items")
    await client.delete_items([])
    assert not route.called


async def test_not_found(client, mealie_mock):
    mealie_mock.get("/api/households/shopping/items/x").respond(404)
    with pytest.raises(MealieNotFound):
        await client.get_item("x")


async def test_http_error(client, mealie_mock):
    mealie_mock.get("/api/units").respond(500)
    with pytest.raises(MealieError) as info:
        await client.get_units()
    assert info.value.status_code == 500


async def test_connection_error_hides_details(client, mealie_mock):
    mealie_mock.get("/api/app/about").mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(MealieError) as info:
        await client.get_app_info()
    assert TOKEN not in str(info.value)
