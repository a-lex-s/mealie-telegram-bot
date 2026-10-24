"""Every path the client calls must exist in Mealie's OpenAPI document, and the
fields the bot sends must exist in the request schemas.

By default the trimmed document in ``tests/data`` is used (refresh it with
``scripts/trim_openapi.py``). Set MEALIE_OPENAPI to an openapi.json exported
from another Mealie instance to check against that one instead.
"""

import json
import os
from pathlib import Path

import pytest

from mealie_bot.features.shopping.service import _FOOD_FIELDS, _UPDATE_FIELDS
from scripts.trim_openapi import DATA, client_calls, normalise, trim

BUNDLED = DATA / "mealie-openapi-3.29.0.json"


@pytest.fixture(scope="module")
def spec() -> dict:
    path = Path(os.environ.get("MEALIE_OPENAPI") or BUNDLED)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["paths"] = {normalise(p): item for p, item in data["paths"].items()}
    return data


def schema_fields(spec: dict, name: str) -> set[str]:
    return set(spec["components"]["schemas"][name]["properties"])


def test_client_calls_are_found():
    assert ("POST", "/api/households/shopping/items/create-bulk") in client_calls()


def test_paths_exist_in_openapi(spec):
    for method, path in client_calls():
        assert path in spec["paths"], path
        assert method.lower() in spec["paths"][path], f"{method} {path}"


def test_bundled_document_is_up_to_date():
    """The bundled file holds exactly the client's calls; a new call needs a refresh."""
    bundled = json.loads(BUNDLED.read_text(encoding="utf-8"))
    calls = {(m.upper(), p) for p, item in bundled["paths"].items() for m in item}
    assert calls == client_calls()


def test_item_update_fields_exist(spec):
    assert set(_UPDATE_FIELDS) <= schema_fields(spec, "ShoppingListItemUpdate")


def test_item_create_fields_exist(spec):
    # The keys ShoppingService.build_item sets.
    created = {"shoppingListId", "quantity", "checked", "note", "unitId", "foodId", "labelId"}
    assert created <= schema_fields(spec, "ShoppingListItemCreate")


def test_food_fields_exist(spec):
    assert set(_FOOD_FIELDS) <= schema_fields(spec, "CreateIngredientFood")


def test_label_fields_exist(spec):
    assert {"name", "color"} <= schema_fields(spec, "MultiPurposeLabelCreate")


def test_trim_rejects_a_missing_path():
    full = {"info": {"title": "Mealie", "version": "v0"}, "paths": {}, "components": {}}
    with pytest.raises(SystemExit, match="not in the OpenAPI document"):
        trim(full)
