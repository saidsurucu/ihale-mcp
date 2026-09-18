FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /bin/uv

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PATH=/app/.venv/bin:$PATH

# Install the locked dependency set (the project itself is plain modules in /app)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# EKAP v2 Turnstile verification needs a real browser: `scrapling install`
# downloads Chromium and apt-installs its system libraries.
RUN scrapling install \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY *.py ./

# Turnstile never issues a token to a browser in a GPU-less Linux container, so
# EKAP v2 tools would hang for 60 s per call. Fail fast with a pointer to the
# local install instead. Override with EKAP_HUMAN_VERIFICATION=on on a host
# where the verification does pass.
ENV EKAP_HUMAN_VERIFICATION=off

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:${PORT:-8000}/health || exit 1

# Shell form so ${PORT} expands at container start (Coolify injects PORT).
# --proxy-headers + --forwarded-allow-ips='*' make uvicorn trust X-Forwarded-Proto
# from the reverse proxy (Coolify Traefik), so redirects keep https.
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'
