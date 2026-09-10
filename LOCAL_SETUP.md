# Ejecutar AlimentIA en Windows

## Arquitectura

| Servicio | Tecnología | Dirección local |
| --- | --- | --- |
| Interfaz | Next.js 16, React 19, Tailwind 4 | http://localhost:3000 |
| API | FastAPI, Python 3.14, Prisma | http://localhost:8080/docs |
| Documentos vectorizados | Qdrant, LlamaIndex, embeddings de Hugging Face | http://localhost:6333/dashboard |
| Modelo de lenguaje | Ollama | http://localhost:11434 |

Prisma guarda pacientes y planes en SQLite, en `alimentia/data/db/alimentia.db`.

## Requisitos y diagnóstico de este equipo

Se detectaron Windows, WSL 2 con Ubuntu 20.04, aproximadamente 32 GB de RAM,
gráficos Intel UHD 620 y Node.js 21.5.0. Se instaló Docker Desktop 4.89.0 para
el usuario actual en `%LOCALAPPDATA%\Programs\DockerDesktop`, usando WSL 2.
Python, uv y Ollama no se encontraron en el PATH de Windows.

Instala [Docker Desktop para Windows](https://docs.docker.com/desktop/setup/install/windows-install/),
usa el motor WSL 2 y abre Docker Desktop hasta que el motor esté listo.
Si el instalador solicita actualizar WSL o reiniciar Windows, completa ese paso.
Con Docker no necesitas instalar Python ni Ollama por separado.

En este equipo Docker ya está instalado. Si una terminal abierta antes de la
instalación no reconoce `docker`, abre una nueva o añade su ruta a esa sesión:

```powershell
$env:PATH = "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin;$env:PATH"
```

El backend utiliza el índice oficial de PyTorch para CPU, evitando instalar
bibliotecas CUDA en este equipo. Ollama conserva su configuración de GPU opcional.

El Compose principal utiliza CPU. El modelo inicial es `llama3.2:3b`, cuya descarga
es de aproximadamente 2 GB según [Ollama](https://ollama.com/library/llama3.2).
La generación con CPU puede tardar; este modelo sirve para probar la integración.
La calidad de sus planes debe evaluarse por separado.

## Arranque completo

Si ya tienes `npm run dev` activo, detenlo antes de iniciar el frontend de Docker:
ambos utilizan el puerto 3000.

En PowerShell, desde la raíz de este repositorio:

```powershell
cd .\alimentia
docker version
docker compose version
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
New-Item -ItemType Directory -Force data/pdfs, data/tables, data/db | Out-Null
docker compose config --quiet
docker compose up -d --build
docker compose exec ollama ollama pull llama3.2:3b
docker compose logs --tail 100 backend
```

Si un comando falla, resuelve ese error antes de continuar. Si cambias `LLM_MODEL`
en `.env`, utiliza el mismo nombre en `ollama pull` y vuelve a ejecutar
`docker compose up -d` para actualizar la configuración del backend.

La primera ejecución descarga imágenes, dependencias y el modelo de embeddings
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` desde Hugging Face.
El backend carga ese modelo antes de aceptar peticiones. Espera a que los logs
indiquen `Application startup complete` y verifica:

```powershell
Invoke-RestMethod http://localhost:8080/health
docker compose exec backend uv run python seed.py
Invoke-RestMethod http://localhost:8080/api/v1/patients
```

El seed añade tres pacientes de ejemplo solamente si la tabla está vacía.
Abre http://localhost:3000 y entra en Pacientes. La página Resumen contiene
métricas estáticas y no debe usarse para comprobar la conexión a la API.
`/health` comprueba que la API responde; no valida la generación del LLM ni el RAG.

## Fuentes que no vienen incluidas

- Copia las guías clínicas PDF en `alimentia/data/pdfs/`.
- Copia la tabla nutricional en `alimentia/data/tables/BAM.xlsx`.
  El código espera la hoja `BAM 18.1.1`, con encabezados en la fila 13,
  y las columnas `nombre_del_alimento`, `energ_kcal`, `protein`, `lipid_tot`, `carbohydrt`.

Sin BAM.xlsx, el backend registra un error y las búsquedas de alimentos devuelven
una lista vacía. Sin PDFs, no hay base documental clínica; la ingesta actual puede
registrar un error por carpeta vacía en su hilo de arranque. Tras añadir el Excel,
reinicia el backend. Para la primera ingesta de PDFs:

```powershell
docker compose restart backend
Invoke-RestMethod -Method Post http://localhost:8080/api/v1/ingest-pdfs
```

La ingesta actual omite el trabajo si la colección ya contiene datos: este endpoint
no actualiza automáticamente una colección existente al agregar más PDFs.

## Operación

Ejecuta estos comandos desde `alimentia/`:

```powershell
docker compose ps
docker compose logs -f backend frontend
docker compose exec ollama ollama list
docker compose down
```

`down` detiene los servicios; los datos permanecen en `alimentia/data/`.
Para volver a iniciar: `docker compose up -d`.

En otro equipo con NVIDIA y soporte de GPU configurado en Docker:

```powershell
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

## Solo la interfaz, sin Docker

Usa Node.js 22 o 24. Node 21.5.0 genera advertencias de incompatibilidad en algunas
dependencias del proyecto. Desde la raíz:

```powershell
cd .\alimentia\frontend
npm ci
npm run dev
```

Abre http://localhost:3000. Las funciones de pacientes, planes y generación requieren
la API en `http://localhost:8080`; sus URLs están escritas directamente en
`src/services/api.ts`. El backend nativo requiere además Python 3.14, Prisma,
Qdrant y Ollama, y contiene rutas `/app/data/...` diseñadas para Docker.

## Límites de la revisión

Se instaló la interfaz con `npm ci` y se inició Next.js localmente. La petición a
`http://127.0.0.1:3000` devolvió HTTP 200 e incluyó el título `AlimentIA Dashboard`
y el contenido `Pacientes activos`. La conexión al navegador de pruebas falló,
por lo que no se verificaron visualmente la pantalla ni las interacciones.

Se construyó el backend con PyTorch para CPU y se iniciaron backend, Qdrant y
Ollama. Se ejecutó el seed y se verificaron `/health` y `/api/v1/patients`
con HTTP 200; la API devolvió tres pacientes. CORS permite tanto
`http://localhost:3000` como `http://127.0.0.1:3000`. La ruta de interfaz
`/patients` también respondió con HTTP 200. `uv lock --check` pasó.

Ollama está ejecutándose, pero aún no se descargó el modelo `llama3.2:3b`.
No se ha validado la generación de planes ni la calidad clínica del resultado.
Siguen faltando BAM.xlsx y los PDFs, por lo que la ingesta documental registra
el error de carpeta vacía indicado anteriormente; esto no impide listar pacientes.
