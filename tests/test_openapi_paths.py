"""Every path the client calls must exist in Mealie's OpenAPI document.

Set MEALIE_OPENAPI to the path of an openapi.json exported from the target
Mealie instance to check against it; the test is skipped otherwise.
"""

import json
import os
import re
from pathlib import Path

import pytest

CLIENT = Path(__file__).parent.parent / "mealie_bot" / "mealie" / "client.py"
CALL = re.compile(r'"(GET|POST|PUT|DELETE)",\s*f?"(/api/[^"]+)"')


def client_calls() -> set[tuple[str, str]]:
    calls = {(m, re.sub(r"{[^}]+}", "{item_id}", p)) for m, p in CALL.findall(CLIENT.read_text())}
    assert calls, "no API calls found in client"
    return calls


def test_client_calls_are_found():
    assert ("POST", "/api/households/shopping/items/create-bulk") in client_calls()


@pytest.mark.skipif(not os.environ.get("MEALIE_OPENAPI"), reason="MEALIE_OPENAPI not set")
def test_paths_exist_in_openapi():
    spec = json.loads(Path(os.environ["MEALIE_OPENAPI"]).read_text())
    for method, path in client_calls():
        assert path in spec["paths"], path
        assert method.lower() in spec["paths"][path], f"{method} {path}"
