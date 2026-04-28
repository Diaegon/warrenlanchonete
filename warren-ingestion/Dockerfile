FROM python:3.12-slim

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy project files
COPY pyproject.toml ./

# Install dependencies into the system Python
RUN uv pip install --system --no-cache -r pyproject.toml

# Copy the rest of the application
COPY . .

# Default command can be overridden when running the container
CMD ["scrapy", "list"]
