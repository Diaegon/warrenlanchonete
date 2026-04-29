FROM python:3.12-slim-bookworm

# Copy uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# WeasyPrint (PDF generation) needs pango at import time.
# fontconfig + fc-cache: pre-generate font cache as root so appuser doesn't
# need write access to /var/cache/fontconfig at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libffi8 \
    libgdk-pixbuf-2.0-0 \
    libglib2.0-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    fontconfig \
    fonts-dejavu-core \
    shared-mime-info \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (separate layer — invalidated only when
# pyproject.toml / uv.lock changes, not on every code change).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Copy application code
COPY . .
RUN uv sync --frozen

# Copy entrypoint and make it executable (must happen as root, before USER switch)
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Add venv to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Non-root user — without --home Debian sets home to /nonexistent which breaks
# fontconfig's user-level cache write attempt at runtime.
RUN addgroup --system --gid 1000 appgroup && \
    adduser --system --uid 1000 --ingroup appgroup --home /home/appuser appuser && \
    chown -R appuser:appgroup /app /home/appuser

ENV HOME=/home/appuser
USER appuser

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
