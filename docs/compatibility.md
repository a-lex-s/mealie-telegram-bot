# Compatibility

| Component | Version | Notes |
|---|---|---|
| Mealie | 3.29.0 | Developed and verified against the OpenAPI document of this version; see [SPEC.md](SPEC.md#7-mealie-api-usage) for the endpoints used. Nearby 3.x releases are likely to work but are untested. |
| Python | 3.12 | Only 3.12 is supported (`requires-python = ">=3.12,<3.13"`). |
| aiogram | 3.x | Exact version pinned in `requirements.txt`. |
| httpx | 0.28.x | Exact version pinned in `requirements.txt`. |
| Docker image | `linux/amd64` | Based on `python:3.12-slim-trixie`, pinned by digest. |
| Telegram | Bot API, private chats | Groups receive only commands because of Telegram's privacy mode. |

To check the bot against your own Mealie version, download its OpenAPI document
and run the path test (see [Development](development.md#running-locally)).
