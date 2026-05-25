# syntax=docker/dockerfile:1.9
#
# Multi-stage build using uv for dependency resolution & installation.
# Build context is THIS service's directory:
#     docker build -t aop/slack-notifier services/slack-notifier
#
# No pip. uv only.

ARG UV_VERSION=0.5.10
ARG PYTHON_VERSION=3.13

# ── uv binary (single-file from Astral's distroless image) ──────────────────
# Tag + digest pinning: Dependabot tracks the tag and proposes a digest bump
# when the upstream image is re-pushed. Without the digest, the tag alone is
# mutable (the publisher can re-point it). See ADR / Scorecard Pinned-Dependencies.
FROM ghcr.io/astral-sh/uv:${UV_VERSION}@sha256:e4c08963c249b0e07d88e9313374d00491e69eed0c99ca5ee443e5c234a16a38 AS uv

# ── builder ─────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm@sha256:e4fa1f978c539608a10cdf74700ac32a3f719dfc6e8b6b6001da82deb36302a2 AS builder

# Copy the uv binary in.
COPY --from=uv /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# ── 1) Dependency layer ─────────────────────────────────────────────────────
# Copy manifests only so this layer is cached across source-only changes.
COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ── 2) Source layer ─────────────────────────────────────────────────────────
COPY . .

# Re-sync with project source present (no-op for `package = false`, harmless).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ── runtime ─────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm@sha256:e4fa1f978c539608a10cdf74700ac32a3f719dfc6e8b6b6001da82deb36302a2 AS runtime

# Non-root user for Cloud Run.
RUN groupadd --system --gid 10001 app \
 && useradd  --system --uid 10001 --gid app --no-create-home --shell /sbin/nologin app

WORKDIR /app

# Copy app + venv from builder.
COPY --from=builder /app /app

# Put the venv on PATH so `python` and `uvicorn` resolve correctly.
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    LIVE_SLACK_ENABLED=false

USER app

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:${PORT}/healthz',timeout=2)" \
  || exit 1

# Use sh -c so ${PORT} expands at runtime (Cloud Run injects PORT).
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 1"]
