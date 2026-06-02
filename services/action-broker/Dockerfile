# syntax=docker/dockerfile:1.9
#
# Multi-stage build using uv for dependency resolution & installation.
# Build context is THIS service's directory:
#     docker build -t aop/action-broker services/action-broker
#
# No pip. uv only.

ARG UV_VERSION=0.11.18
ARG PYTHON_VERSION=3.13

# ── uv binary (single-file from Astral's distroless image) ──────────────────
# Tag + digest pinning: Dependabot tracks the tag and proposes a digest bump
# when the upstream image is re-pushed. Without the digest, the tag alone is
# mutable (the publisher can re-point it). See ADR / Scorecard Pinned-Dependencies.
FROM ghcr.io/astral-sh/uv:${UV_VERSION}@sha256:78bc42400d77b0678ba95765305c826652ed5431f399257271dda681d0318f03 AS uv

# ── builder ─────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-trixie@sha256:b04b5d7233d2ad9c379e22ea8927cd1378cd15c60d4ef876c065b25ea8fb3bf3 AS builder

COPY --from=uv /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# ── 1) Dependency layer ─────────────────────────────────────────────────────
COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ── 2) Source layer ─────────────────────────────────────────────────────────
COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ── runtime ─────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-trixie@sha256:b04b5d7233d2ad9c379e22ea8927cd1378cd15c60d4ef876c065b25ea8fb3bf3 AS runtime

RUN groupadd --system --gid 10001 app \
 && useradd  --system --uid 10001 --gid app --no-create-home --shell /sbin/nologin app

WORKDIR /app

COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    LIVE_MODE=false

USER app

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:${PORT}/healthz',timeout=2)" \
  || exit 1

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 1"]
