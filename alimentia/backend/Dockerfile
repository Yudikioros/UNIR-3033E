FROM python:3.14-slim

# 1. Instalar la librería del sistema necesaria para Prisma/Node.js
RUN apt-get update && apt-get install -y libatomic1 && rm -rf /var/lib/apt/lists/*

# Copiar uv desde su imagen oficial
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 2. Copiar los archivos del backend
COPY . .

# 3. Instalar dependencias
RUN uv sync --no-dev --no-cache

# 4. Generar el cliente de Prisma
RUN uv run prisma generate

EXPOSE 8080

# 5. Arrancar Uvicorn
CMD ["sh", "-c", "uv run prisma db push && uv run uvicorn src.app.main:app --host 0.0.0.0 --port 8080"]