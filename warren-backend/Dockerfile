FROM python:3.12-slim

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Copy dependencies first to leverage Docker cache
COPY pyproject.toml uv.lock ./

# Install dependencies into a virtual environment in /app/.venv
RUN uv sync --frozen --no-install-project

# Copy the rest of the application
COPY . .

# Install the application package
RUN uv sync --frozen

# Ensure the virtual environment is in the PATH
ENV PATH="/app/.venv/bin:$PATH"

# Expose the API port
EXPOSE 8000

# Run uvicorn server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
