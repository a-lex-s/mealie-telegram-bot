# python:3.12-slim-trixie, pinned by digest. Dependabot proposes updates.
FROM python:3.12-slim-trixie@sha256:cb33f7f771ecec2ef1225cf39b159591a040391bd73e4c01f00fdfc4c47611d2

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Static OCI labels; the release workflow adds source, version, revision and created.
LABEL org.opencontainers.image.title="mealie-telegram-bot" \
      org.opencontainers.image.description="Telegram bot front end for a self-hosted Mealie instance" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Hash-locked dependencies; the build fails if anything does not match or if the
# locked versions contradict each other. pip and setuptools are not needed at
# runtime and only add packages for vulnerability scanners to flag.
COPY requirements.txt .
RUN pip install --require-hashes --no-deps -r requirements.txt \
    && pip check \
    && pip uninstall -y pip setuptools wheel

COPY mealie_bot ./mealie_bot

# Set by the release workflow (same value as the OCI revision label) for /version;
# empty for local builds.
ARG VCS_REF=""
ENV VCS_REF=${VCS_REF}

RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin bot
USER 10001:10001

# Long polling only: the container needs no inbound port.
ENTRYPOINT ["python", "-m", "mealie_bot"]
