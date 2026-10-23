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


async def test_unexpected_body_is_an_error(client, mealie_mock):
    mealie_mock.get("/api/users/self").respond(json=["not", "an", "object"])
    with pytest.raises(MealieError, match="unexpected response body"):
        await client.get_self()


@pytest.mark.parametrize("path", ["/api/users/self", "/api/households/shopping/lists"])
async def test_empty_body_is_an_error_for_json_endpoints(client, mealie_mock, path):
    mealie_mock.get(path).respond(204)
    with pytest.raises(MealieError):
        await client._request_json("GET", path)


async def test_html_body_is_an_error(client, mealie_mock):
    # A reverse proxy in front of Mealie may answer 200 with a maintenance page.
    mealie_mock.get("/api/units").respond(200, text="<html>maintenance</html>")
    with pytest.raises(MealieError, match="unexpected response body"):
        await client.get_units()


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.get_shopping_lists(),
        lambda c: c.get_foods(),
        lambda c: c.get_units(),
    ],
)
async def test_list_endpoints_reject_empty_bodies(client, mealie_mock, call):
    for path in ("/api/households/shopping/lists", "/api/foods", "/api/units"):
        mealie_mock.get(path).respond(204)
    with pytest.raises(MealieError):
        await call(client)


async def test_idempotent_requests_are_retried_once(client, mealie_mock, monkeypatch):
    import mealie_bot.mealie.client as module

    monkeypatch.setattr(module, "RETRY_DELAY_SECONDS", 0)
    route = mealie_mock.get("/api/units")
    route.side_effect = [httpx.ConnectError("boom"), httpx.Response(200, json={"items": [1]})]
    assert await client.get_units() == [1]
    assert route.call_count == 2


async def test_create_is_not_retried(client, mealie_mock):
    route = mealie_mock.post("/api/households/shopping/items/create-bulk").mock(
        side_effect=httpx.ConnectError("boom")
    )
    with pytest.raises(MealieError):
        await client.create_items([{"note": "x"}])
    assert route.call_count == 1
