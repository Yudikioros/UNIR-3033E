# Ejecutar AlimentIA localmente con GPU NVIDIA

Esta guía explica cómo iniciar la aplicación completa con Docker Compose,
cargar los datos de demostración y comprobar que Ollama utiliza la GPU.

## Servicios

| Servicio            | Dirección                       |
| ------------------- | ------------------------------- |
| Interfaz web        | http://localhost:3000           |
| API y documentación | http://localhost:8080/docs      |
| Qdrant              | http://localhost:6333/dashboard |
| Ollama              | http://localhost:11434          |

Los datos persistentes se guardan dentro de `alimentia/data/`. Detener o
recrear los contenedores no elimina la base SQLite, los documentos, el índice
vectorial ni los modelos descargados.

## Requisitos

- Windows con Docker Desktop y el motor WSL 2 activo.
- Docker Compose incluido en Docker Desktop.
- GPU NVIDIA con controladores actualizados.
- Integración de GPU habilitada en Docker Desktop.

Comprueba que Windows reconoce la GPU antes de iniciar:

```powershell
nvidia-smi
```

Si este comando falla, actualiza el controlador NVIDIA antes de utilizar
`docker-compose.gpu.yml`.

## Configuración inicial

Abre PowerShell en la raíz del repositorio y entra al directorio de la
aplicación:

```powershell
cd .\alimentia
```

Crea el archivo de configuración la primera vez:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edita `.env` para seleccionar el modelo y sus parámetros. Las variables más
relevantes son:

```dotenv
LLM_MODEL=qwen3.5:9b
OLLAMA_KEEP_ALIVE=-1
ALIMENTIA_OLLAMA_PRELOAD=true
ALIMENTIA_LLM_CONTEXT_TOKENS=30720
ALIMENTIA_BAM_SAMPLE_SIZE=30
```

`ALIMENTIA_LLM_CONTEXT_TOKENS` controla la ventana completa del modelo. No se
configura un límite de salida separado. `ALIMENTIA_BAM_SAMPLE_SIZE` agrega esa
cantidad de alimentos aleatorios a los alimentos base enviados al modelo para
mejorar la variedad de los planes.

## 1. Iniciar la aplicación

Desde `alimentia/`, ejecuta:

```powershell
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

Este comando:

- construye frontend y backend;
- inicia SQLite/Prisma, Qdrant y Ollama;
- asigna una GPU NVIDIA al contenedor de Ollama;
- descarga el modelo configurado si todavía no existe;
- precarga el modelo y prepara el índice RAG;
- muestra los logs de todos los servicios en la terminal.

La primera ejecución puede tardar por la descarga de imágenes, dependencias,
embeddings y el modelo LLM. Espera hasta ver que el backend completó el
arranque y que el frontend está disponible.

Como `up` permanece mostrando logs, abre otra terminal PowerShell para los
comandos siguientes y vuelve a entrar a `alimentia/`:

```powershell
cd .\alimentia
```

Comprueba la API:

```powershell
Invoke-RestMethod http://localhost:8080/health
```

La respuesta esperada incluye `status: ok`.

## 2. Cargar datos de demostración

Con los contenedores activos, ejecuta:

```powershell
docker compose exec backend uv run --no-sync python seed.py
```

El seed crea o actualiza los cinco casos de evaluación utilizados por el MVP.
Después abre http://localhost:3000 y entra en **Pacientes**.

Vuelve a ejecutar el seed cuando necesites restaurar esos casos de prueba. No
lo ejecutes mientras el backend todavía está migrando la base de datos.

## 3. Comprobar el modelo en Ollama

Ejecuta:

```powershell
docker exec -it alimentia-ollama-1 ollama ps
```

La salida muestra los modelos cargados actualmente, su tamaño, procesador y
tiempo de permanencia. Durante una generación o después de la precarga debe
aparecer el modelo definido en `LLM_MODEL`.

En la columna `PROCESSOR`, un valor como `100% GPU` confirma que Ollama cargó
el modelo completamente en la GPU. Una combinación CPU/GPU indica que parte
del modelo fue descargada a RAM porque no cabía por completo en la VRAM.

Si la lista está vacía, revisa:

```powershell
docker compose logs --tail 100 backend ollama
```

## 4. Supervisar memoria GPU

Para observar continuamente la memoria utilizada, ejecuta en otra terminal:

```powershell
nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free --format=csv -l 1
```

El comando actualiza los valores cada segundo:

- `memory.total`: VRAM total disponible;
- `memory.used`: VRAM ocupada por Ollama y otros procesos;
- `memory.free`: VRAM todavía disponible.

Déjalo activo mientras generas un plan para comprobar el consumo real del
modelo. Detén el seguimiento con `Ctrl+C`.

## Recursos nutricionales y RAG

Para utilizar todos los recursos del MVP, deben existir:

- `alimentia/data/tables/BAM.xlsx`;
- los PDF autorizados en `alimentia/data/pdfs/`;
- `alimentia/data/knowledge_base/manifest.json`.

BAM debe contener la hoja `BAM 18.1.1`, encabezados en la fila 13 y las
columnas `codigomex2`, `nombre_del_alimento`, `energ_kcal`, `protein`,
`lipid_tot` y `carbohydrt`.

Después de agregar o cambiar estos archivos, reinicia el backend:

```powershell
docker compose restart backend
```

## Detener la aplicación

Si ejecutaste Compose en primer plano, pulsa `Ctrl+C`. Después puedes detener
y retirar los contenedores con:

```powershell
docker compose -f docker-compose.yml -f docker-compose.gpu.yml down
```

Los datos persistentes permanecen en `alimentia/data/`. Para iniciar de nuevo,
repite el comando de la sección **Iniciar la aplicación**.

## Diagnóstico rápido

```powershell
docker compose ps
docker compose logs --tail 100 backend frontend ollama qdrant
Invoke-RestMethod http://localhost:8080/health
docker exec -it alimentia-ollama-1 ollama ps
```

Si el puerto 3000 o 8080 ya está ocupado, detén la aplicación que lo utiliza
antes de iniciar Compose. Si Docker no reconoce la GPU, no continúes con el
archivo GPU hasta que `nvidia-smi` funcione y Docker Desktop tenga habilitada
la integración correspondiente.
