# ==========================================
# Stage 1: Build Dependencies using uv
# ==========================================
FROM ghcr.io/astral-sh/uv:0.5.10-python3.12-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install dependencies into virtual environment
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Copy application source code and install project
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ==========================================
# Stage 2: Final Runtime Image
# ==========================================
FROM python:3.12-slim-bookworm AS runner

WORKDIR /app

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy virtual environment and project code from builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app /app

# Set environment variables so Python uses the virtual environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Ensure secrets directory exists with proper permissions
RUN mkdir -p /app/secrets && chown -R appuser:appuser /app/secrets

USER appuser

# Default command runs graph on sample invoice
CMD ["python", "-m", "src.core.graph", "samples/sample_invoice.pdf"]