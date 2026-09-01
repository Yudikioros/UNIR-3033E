FROM python:3.14-slim

# Copy uv from its official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 1. Copy ALL backend files (including pyproject.toml and the src folder)
COPY . .

# 2. Now sync and install dependencies and the local package
RUN uv sync --no-dev --no-cache

# 3. Expose the port
EXPOSE 8080

# 4. Start Uvicorn using uv run
CMD ["uv", "run", "uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8080"]