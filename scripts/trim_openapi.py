"""Trim a Mealie OpenAPI document to what the bot uses.

Writes the paths and methods that ``mealie_bot/mealie/client.py`` calls, the
request body schemas of those calls and their property names, nothing else.
The result is ``tests/data/mealie-openapi-<version>.json``, which the tests use
when ``MEALIE_OPENAPI`` is not set.

Usage, from the repository root::

    python scripts/trim_openapi.py path/to/openapi.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CLIENT = ROOT / "mealie_bot" / "mealie" / "client.py"
DATA = ROOT / "tests" / "data"
CALL = re.compile(r'"(GET|POST|PUT|DELETE)",\s*f?"(/api/[^"]+)"')
# Mealie names every path parameter after the route's own variable; the client
# uses descriptive names, so both sides are compared with one placeholder.
_PARAM = re.compile(r"{[^}]+}")
PLACEHOLDER = "{item_id}"


def normalise(path: str) -> str:
    return _PARAM.sub(PLACEHOLDER, path)


def client_calls() -> set[tuple[str, str]]:
    """(method, path) for every request in the client, path parameters normalised."""
    return {(method, normalise(path)) for method, path in CALL.findall(CLIENT.read_text())}


def _body_schema(operation: dict[str, Any]) -> str | None:
    """Name of the request body schema (also for an array of it), if any."""
    schema = (
        operation.get("requestBody", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    )
    ref = schema.get("$ref") or schema.get("items", {}).get("$ref")
    return ref.rsplit("/", 1)[-1] if ref else None


def trim(spec: dict[str, Any]) -> dict[str, Any]:
    paths = {normalise(path): item for path, item in spec["paths"].items()}
    out_paths: dict[str, dict[str, Any]] = {}
    schemas: dict[str, Any] = {}
    for method, path in sorted(client_calls()):
        operation = paths.get(path, {}).get(method.lower())
        if operation is None:
            raise SystemExit(f"{method} {path} is not in the OpenAPI document")
        trimmed: dict[str, Any] = {}
        name = _body_schema(operation)
        if name is not None:
            trimmed["requestBody"] = {"$ref": f"#/components/schemas/{name}"}
            properties = spec["components"]["schemas"][name].get("properties", {})
            schemas[name] = {"properties": sorted(properties)}
        out_paths.setdefault(path, {})[method.lower()] = trimmed
    return {
        "info": {"title": spec["info"]["title"], "version": spec["info"]["version"]},
        "paths": dict(sorted(out_paths.items())),
        "components": {"schemas": dict(sorted(schemas.items()))},
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    trimmed = trim(json.loads(Path(argv[1]).read_text(encoding="utf-8")))
    version = trimmed["info"]["version"].removeprefix("v")
    target = DATA / f"mealie-openapi-{version}.json"
    target.write_text(json.dumps(trimmed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
