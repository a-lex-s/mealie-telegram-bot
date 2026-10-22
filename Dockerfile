# syntax=docker/dockerfile:1

# python:3.12-slim-trixie, pinned by digest. Dependabot proposes updates.
FROM python:3.12-slim-trixie@sha256:cb33f7f771ecec2ef1225cf39b159591a040391bd73e4c01f00fdfc4c47611d2

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Hash-locked dependencies; the build fails if anything does not match.
COPY requirements.txt .
RUN pip install --require-hashes --no-deps -r requirements.txt

COPY mealie_bot ./mealie_bot

RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin bot
USER 10001:10001

# Long polling only: the container needs no inbound port.
ENTRYPOINT ["python", "-m", "mealie_bot"]
