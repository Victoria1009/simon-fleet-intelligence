# SIMON — Guía de instalación y ejecución local

## 1. Alcance

Este proyecto simula telemetría IoT/AVL de vehículos y la procesa en tres capas: **Bronce** (ingesta de posiciones), **Plata** (geocercas, alertas y puntuación) y **Oro** (datos consolidados para visualización). Se ha utilizado en Windows con Anaconda, PostgreSQL 17 y PostGIS 3.7. Los comandos siguientes están orientados a **Anaconda PowerShell Prompt**.

## 2. Requisitos

- Python 3.12 (entorno Conda recomendado).
- PostgreSQL con extensión PostGIS instalada y habilitable en la base de datos.
- Acceso local a pgAdmin 4 o `psql`.
- Archivos del proyecto, carpeta `tests/` y **`database/simon_inicializacion.sql`** dentro del repositorio.

Los paquetes Python usados por los módulos son: `fastapi`, `uvicorn`, `pydantic`, `sqlalchemy`, `psycopg` (v3), `python-dotenv`, `requests`, `pandas`, `streamlit`, `folium`, `streamlit-folium` y `pytest`.

## 3. Preparar el entorno Python

En Anaconda PowerShell Prompt:

```powershell
conda create -n api_simon python=3.12 -y
conda activate api_simon
cd D:\api_simon
python -m pip install -r requirements.txt
```

Si el entorno `api_simon` ya existe, basta con activarlo e instalar las dependencias faltantes. La ruta `D:\api_simon` es un ejemplo; sustitúyela por la ubicación del proyecto.

## 4. Inicializar PostgreSQL/PostGIS

**Usar una base de datos nueva.** El script de inicialización está pensado para una instalación limpia; no ejecutarlo indiscriminadamente sobre una base con datos existentes.

1. Conéctate desde pgAdmin a la base administrativa `postgres`.
2. Ejecuta:

```sql
CREATE DATABASE simon_db;
```

3. Abre el **Query Tool** conectado a la nueva `simon_db`.
4. Abre el archivo `database/simon_inicializacion.sql` y ejecútalo. Este script incluye `CREATE EXTENSION IF NOT EXISTS postgis`, las tablas `registros_vehiculos`, `geocercas`, `registros_enriquecidos`, `registros_oro`, sus restricciones, índices y tres geocercas de demostración.
5. Comprueba la instalación:

```sql
SELECT PostGIS_Version();
SELECT nombre, velocidad_max_kmh, ST_SRID(geometria) AS srid
FROM public.geocercas ORDER BY id;
```

Se esperan tres geocercas con SRID 4326. Si `CREATE EXTENSION postgis` falla, instala primero PostGIS en el servidor PostgreSQL; no basta con instalar paquetes Python.

## 5. Configurar las variables de entorno

Copia `.env.example` como `.env` en la raíz del proyecto (no lo publiques) y reemplaza los valores de ejemplo:

```powershell
Copy-Item .env.example .env
```

Variables de referencia (el endpoint de consulta utiliza `API_READ_KEY`):

```dotenv
DB_USER=postgres
DB_PASSWORD=REEMPLAZAR_CON_CONTRASENA_LOCAL
DB_HOST=localhost
DB_PORT=5432
DB_NAME=simon_db
API_READ_KEY=REEMPLAZAR_CON_CLAVE_DE_LECTURA
MASKING_SECRET=REEMPLAZAR_CON_SECRETO_ALEATORIO
```

La variable `API_READ_KEY` coincide con `os.getenv("API_READ_KEY")` en `backend/main.py` y con `.env.example`. El código `backend/privacidad.py` lee `MASKING_SECRET` para la seudonimización HMAC. Nunca publiques secretos reales ni un `.env` en GitHub. Agrega al `.gitignore` al menos `.env`, `.pytest_cache/`, `__pycache__/` y `*.pyc`.

Comprueba la conexión:

```powershell
python -c "from backend.conexion_db import engine; print('Conexión configurada')"
```

## 6. Ejecutar el pipeline

Abre **terminales separadas**, todas con el entorno `api_simon` activado y situadas en la carpeta del proyecto.

**Terminal 1 — API FastAPI:**

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Visita `http://127.0.0.1:8000/docs` para explorar los endpoints. `POST /vehiculos/registrar` recibe telemetría y `GET /vehiculos/consulta` requiere el encabezado `x-api-key` con el valor de la variable de entorno que realmente utiliza `backend/main.py` (ver sección 5).

**Terminal 2 — Simulador IoT:**

```powershell
python -m pipeline.simulador_iot
```

Envía posiciones sintéticas a la API periódicamente. Detén la simulación con `Ctrl+C`.

**Terminal 3 — Procesamiento Plata:**

```powershell
python -m pipeline.automatizar_plata
```

Ejecuta `procesar_plata.py` periódicamente para enriquecer registros pendientes con geocercas, velocidad máxima, autonomía, alertas y Driver Score.

**Terminal 4 — Procesamiento Oro:**

```powershell
python -m pipeline.automatizar_oro
```

Ejecuta `procesar_oro.py` periódicamente para consolidar nuevos registros enriquecidos.

**Terminal 5 — Dashboard:**

```powershell
python -m streamlit run visualizacion/dashboard.py
```

Abre la URL local indicada por Streamlit (habitualmente `http://localhost:8501`). Para una ejecución puntual, en lugar de los automatizadores puedes usar `python -m pipeline.procesar_plata` y después `python -m pipeline.procesar_oro`.

## 7. Verificación de datos

Desde pgAdmin, conectado a la base utilizada por la aplicación:

```sql
SELECT 'bronce' AS capa, COUNT(*) FROM registros_vehiculos
UNION ALL SELECT 'plata', COUNT(*) FROM registros_enriquecidos
UNION ALL SELECT 'oro', COUNT(*) FROM registros_oro;
```

Los conteos aumentarán conforme el simulador y los procesos se ejecuten. Las capas Plata y Oro pueden ir temporalmente rezagadas respecto de Bronce.

## 8. Pruebas automatizadas

**Unitarias** (no requieren ejecutar el simulador):

```powershell
python -m pytest -v tests/test_privacidad.py tests/test_validacion.py
```

**Integración PostGIS** (usar **otra base**, exclusiva para pruebas):

1. Crea `simon_test_db` desde la base administrativa `postgres`.
2. Conéctate a `simon_test_db` y ejecuta allí `database/simon_inicializacion.sql`.
3. Comprueba que las tablas Bronce, Plata y Oro estén vacías y que `geocercas` tenga tres filas.
4. En PowerShell, configura la URL **sin mostrar la contraseña**:

```powershell
$usuario = 'postgres'
$clave = Read-Host 'Contraseña de PostgreSQL' -AsSecureString
$credencial = [System.Net.NetworkCredential]::new($usuario, $clave)
$claveCodificada = [uri]::EscapeDataString($credencial.Password)
$env:SIMON_TEST_DB_URL = "postgresql+psycopg://$($usuario):$($claveCodificada)@localhost:5432/simon_test_db"
Remove-Variable credencial, claveCodificada, clave
python -m pytest -v tests/test_pipeline_postgis.py
```

La prueba usa una transacción revertida al finalizar, pero **no debe ejecutarse contra `simon_db`**: las consultas de procesamiento recorren todos los registros pendientes. Al terminar puedes retirar la variable de la sesión con `Remove-Item Env:SIMON_TEST_DB_URL`.

En la ejecución local del 20 de noviembre de 2026 se verificaron **11 pruebas unitarias** y **1 prueba de integración PostGIS** con resultado satisfactorio. Estos resultados no equivalen a una prueba de carga.

## 9. Problemas frecuentes

- **No se puede conectar a PostgreSQL:** verifica que el servicio esté activo, el puerto 5432, usuario, contraseña y `DB_NAME`.
- **`function postgis_version() does not exist` o falta `geometry`:** habilita PostGIS en la base correspondiente.
- **`relation ... does not exist`:** confirma que ejecutaste la inicialización en la misma base configurada en `.env`.
- **`401 Acceso no autorizado` en consulta:** proporciona `x-api-key` correcto; el endpoint de registro no usa esa dependencia.
- **La prueba de integración se omite (`SKIPPED`):** falta `SIMON_TEST_DB_URL` en la sesión de PowerShell.
- **No aparecen datos en el tablero:** comprueba que estén ejecutándose API, simulador y procesos Plata/Oro, y que todos apunten a la misma base.

## 10. Estructura del proyecto

```text
api_simon/
├── backend/                 # API, conexión y privacidad
├── pipeline/                # Simulador, Plata, Oro y automatizadores
├── database/
│   └── simon_inicializacion.sql
├── visualizacion/
│   └── dashboard.py
├── tests/
├── .env.example
├── .gitignore
├── requirements.txt
├── DESIGN.md
└── SETUP.md
```

Ejecuta los comandos Python desde la **raíz del repositorio** para que se resuelvan correctamente las importaciones de paquetes.

## 11. Consideraciones y límites

Los vehículos, rutas y geocercas son **sintéticos**. El cálculo de autonomía utiliza supuestos fijos de capacidad, consumo y distancia restante; no es una predicción calibrada con rutas reales. La indexación espacial GiST mejora la estrategia de acceso a geometrías, pero no se ha demostrado rendimiento de milisegundos sobre millones de filas mediante un benchmark. Este proyecto es una demostración técnica local, no un servicio de producción endurecido.
