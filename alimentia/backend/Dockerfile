# Usamos la versión de Python que definiste en tu toml
FROM python:3.14-slim

# Copiamos el binario de uv directamente desde la imagen oficial de Astral
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Establecemos el directorio de trabajo
WORKDIR /app

# Copiamos los archivos de configuración de dependencias
# (Si más adelante se genera un archivo uv.lock, agrégalo a esta línea)
COPY pyproject.toml ./

# Instalamos las dependencias creando el entorno virtual dentro del contenedor
RUN uv sync --no-dev --no-cache

# Copiamos el código fuente de la aplicación
COPY src/ ./src/

# Aseguramos que los binarios del entorno virtual estén en el PATH
ENV PATH="/app/.venv/bin:$PATH"

# Exponemos el puerto
EXPOSE 8080

# Comando para levantar FastAPI usando la estructura src-layout
CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8080"]