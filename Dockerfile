FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PATH=/app/.venv/bin:$PATH

# Install the locked dependency set (the project itself is plain modules in /app)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# EKAP v2 Turnstile verification needs a real browser with coherent
# fingerprints: Camoufox (Firefox-based, BrowserForge) + its system libs.
# Playwright is only a throwaway helper to apt-install the Firefox libs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && uvx --from playwright playwright install-deps firefox \
    && python -m camoufox fetch

COPY *.py ./

# EKAP v2 Turnstile verification runs in a real (headless) browser at request
# time: coherent tr-TR profile, bounded retries (2 x 30 s), then a fast error
# pointing at the local install. Set EKAP_HUMAN_VERIFICATION=off to skip the
# browser entirely and fail fast (e.g. if verification proves flaky here).
# ENV EKAP_HUMAN_VERIFICATION=off

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:${PORT:-8000}/health || exit 1

# Shell form so ${PORT} expands at container start (Coolify injects PORT).
# --proxy-headers + --forwarded-allow-ips='*' make uvicorn trust X-Forwarded-Proto
# from the reverse proxy (Coolify Traefik), so redirects keep https.
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'
