from __future__ import annotations

import pytest
import respx

from mealie_bot.mealie import MealieClient

BASE_URL = "http://mealie.example.com:9000"
TOKEN = "test-token-not-a-secret"
LIST_ID = "11111111-1111-4111-8111-111111111111"
OTHER_LIST_ID = "22222222-2222-4222-8222-222222222222"


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch):
    import mealie_bot.mealie.client as client_module

    monkeypatch.setattr(client_module, "RETRY_DELAY_SECONDS", 0)


@pytest.fixture
def mealie_mock():
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as mock:
        yield mock


@pytest.fixture
async def client():
    client = MealieClient(BASE_URL, TOKEN)
    yield client
    await client.aclose()


def make_unit(uid: str, name: str, abbreviation: str = "", plural: str | None = None, aliases=()):
    return {
        "id": uid,
        "name": name,
        "pluralName": plural,
        "abbreviation": abbreviation,
        "aliases": [{"name": a} for a in aliases],
    }


def make_food(fid: str, name: str, label_id: str | None = None, plural=None, aliases=()):
    return {
        "id": fid,
        "name": name,
        "pluralName": plural,
        "labelId": label_id,
        "aliases": [{"name": a} for a in aliases],
    }


def make_item(iid: str, display: str, checked=False, label=None, position=0, **extra):
    item = {
        "id": iid,
        "shoppingListId": LIST_ID,
        "groupId": "g",
        "householdId": "h",
        "display": display,
        "checked": checked,
        "position": position,
        "quantity": 1,
        "note": "",
        "label": {"id": "l-" + label, "name": label, "groupId": "g"} if label else None,
    }
    item.update(extra)
    return item
