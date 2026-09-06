# --- build stage: resolve dependencies and the project into a self-contained venv ---
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS build

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install third-party dependencies first so this layer caches across code changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Then install the project itself, non-editable so the venv is self-contained.
COPY src ./src
COPY README.md ./
RUN uv sync --frozen --no-dev --no-editable

# --- runtime stage ---
FROM python:3.13-slim-bookworm AS runtime

# ffmpeg brings both ffmpeg and ffprobe, required by yt-dlp for muxing/inspection.
RUN apt-get update \
    && apt-get install --no-install-recommends -y ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --system --create-home --uid 10001 app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    XOWNLOADER_HOST=0.0.0.0 \
    XOWNLOADER_PORT=8000 \
    XOWNLOADER_DOWNLOAD_DIRECTORY=/data/downloads \
    XOWNLOADER_DATABASE_PATH=/data/xownloader.db

WORKDIR /app
COPY --from=build /app/.venv /app/.venv

RUN mkdir -p /data/downloads && chown -R app:app /data
USER app
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health').read()" || exit 1

# --proxy-headers + --forwarded-allow-ips let the app trust X-Forwarded-* from a
# reverse proxy, so per-client rate limiting sees real client IPs. The container
# is only reachable through that proxy (compose publishes to 127.0.0.1).
CMD ["uvicorn", "xownloader_server.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
