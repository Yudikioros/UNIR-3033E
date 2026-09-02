# UNIR-3033E

Planes Dietéticos Asistidos por Modelos de Lenguaje Grande bajo Supervisión de Nutriólogos

Este proyecto consiste en una plataforma para la creación de planes dietéticos personalizados utilizando modelos de lenguaje grande (LLMs) y técnicas de Recuperación Aumentada por Generación (RAG). El sistema permite a los usuarios ingresar sus datos personales, objetivos, patologías y preferencias alimentarias para generar planes nutricionales que son validados y supervisados por profesionales de la nutrición.

## Tecnologías utilizadas

- **Backend**: FastAPI, Python, Prisma, Qdrant (Vector Database), LlamaIndex.
- **Frontend**: Next.js, React, Tailwind CSS.
- **Infraestructura**: Docker, Docker Compose.

# Integrantes

- Esdras de la Torre Valdivia
- Adrián Lago Aponte
- Oscar Arturo López Córdova

## Configuración y Ejecución

### Requisitos previos

- Tener instalado Docker y Docker Compose.
- Tener configuradas las variables de entorno necesarias (ver archivos `.env` en cada carpeta).
- Configurar las variables de entorno para el modelo de lenguaje (LLM) que se desea desplegar (ej. `LLM_MODEL`, `LLM_QUANTIZATION`, `LLM_MAX_LEN`).

### Ejecución con Docker Compose

Para levantar ambos servicios (backend y frontend) utilizando Docker Compose:

```bash
docker-compose up -d
```

## Base de Datos

Para inicializar la base de datos con datos de prueba:

```bash
docker exec -it alimentia-backend-1 uv run python seed.py
```
