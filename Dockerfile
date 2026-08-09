FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked

RUN /app/.venv/bin/patchright install --with-deps chromium


FROM python:3.12-slim AS runtime
WORKDIR /app

COPY --from=builder /app /app
COPY --from=builder /root/.cache/ms-playwright /root/.cache/ms-playwright

ENV PATH="/app/.venv/bin:$PATH"

# System libs only (chromium binary already copied above) — the builder stage's apt install
# doesn't carry over since this is a separate base image/filesystem from a different FROM.
# opencv (an ultralytics dependency) needs the same libs (libxcb etc.) as headless chromium.
# xvfb: the scraper runs Chromium non-headless (Google Maps' review tab bar doesn't render in
# headless mode, confirmed by live testing) — a container has no real display, so we give it a
# virtual one instead.
RUN apt-get update && apt-get install -y --no-install-recommends xvfb \
    && patchright install-deps chromium \
    && rm -rf /var/lib/apt/lists/*

EXPOSE 8000
ENV DISPLAY=:99
# xvfb-run wraps this same idea in a script that waits for Xvfb's SIGUSR1 "ready" signal —
# but that handshake reliably hangs forever with zero output when it's the container's PID 1
# (confirmed live: Xvfb starts fine, lock file appears, the wait just never returns). Starting
# Xvfb directly and giving it a fixed head start sidesteps that fragile signal dance entirely.
CMD Xvfb :99 -screen 0 1280x1024x24 -nolisten tcp & \
    sleep 2 && \
    uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
