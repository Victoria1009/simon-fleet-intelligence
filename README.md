# SIMON | Fleet Intelligence

**Prototipo de inteligencia geoespacial para telemetría vehicular IoT/AVL**, desarrollado con Python, FastAPI y PostgreSQL/PostGIS.

SIMON simula reportes de posición GPS, velocidad y nivel de combustible de tres vehículos, procesa los datos en una arquitectura **Bronce → Plata → Oro**, evalúa geocercas y reglas de negocio, y presenta los resultados en un tablero interactivo.

> Proyecto demostrativo para ejecución local. Los datos, recorridos y geocercas son sintéticos; no es un servicio de producción.

## Arquitectura

```text
Simulador IoT (pipeline/simulador_iot.py)
          |
          v
FastAPI — POST /vehiculos/registrar
          |
          v
PostgreSQL/PostGIS — Bronce (registros_vehiculos)
          |
          v
Plata (registros_enriquecidos) <--- geocercas PostGIS
          |
          v
Oro (registros_oro)
          |
          v
Dashboard Streamlit (visualizacion/dashboard.py)
```

Los procesamientos Plata y Oro se ejecutan de forma incremental mediante tareas periódicas. No se utiliza una infraestructura de *streaming* distribuido.

## Funcionalidades

- **Ingesta y validación:** recepción de telemetría vehicular mediante FastAPI y Pydantic.
- **Análisis espacial:** asignación de geocercas con PostGIS y evaluación de límites de velocidad.
- **Alertas:** exceso de velocidad y autonomía de combustible insuficiente bajo supuestos de demostración.
- **Driver Score:** puntuación heurística a partir de infracciones y alertas.
- **Privacidad de consulta:** protección del endpoint de lectura con `x-api-key`, seudonimización HMAC y aproximación de coordenadas.
- **Visualización:** indicadores, mapas, trayectorias y alertas mediante Streamlit.
- **Pruebas:** validaciones unitarias y una prueba de integración con PostGIS en base aislada.

## Tecnologías

Python 3.12 · FastAPI · Pydantic · PostgreSQL/PostGIS · SQLAlchemy · psycopg · Streamlit · Folium · pytest

## Estructura del proyecto

```text
backend/         API, conexión a BD y privacidad
pipeline/        Simulador, procesamiento Plata/Oro y automatización
database/        Script de inicialización PostGIS
visualizacion/   Dashboard Streamlit
tests/           Pruebas unitarias y de integración
DESIGN.md        Diseño técnico y decisiones de arquitectura
SETUP.md         Instalación, ejecución y pruebas
requirements.txt Dependencias Python
.env.example     Plantilla de variables de entorno
```

## Inicio rápido

**Requisitos:** Python 3.12, PostgreSQL con PostGIS y una terminal PowerShell (Anaconda recomendado).

1. Crear y activar el entorno, desde la raíz del repositorio:

   ```powershell
   conda create -n api_simon python=3.12 -y
   conda activate api_simon
   python -m pip install -r requirements.txt
   ```

2. Crear una base de datos PostgreSQL llamada `simon_db` y ejecutar en ella `database/simon_inicializacion.sql` (por ejemplo, desde pgAdmin). El script crea las tablas, índices y tres geocercas de ejemplo.

3. Copiar `.env.example` a `.env` y configurar las credenciales y secretos locales:

   ```powershell
   Copy-Item .env.example .env
   ```

   El archivo `.env` **no debe publicarse**. La clave de lectura se configura mediante `API_READ_KEY`.

4. Abrir terminales separadas, activando el entorno y situándose en la raíz del proyecto, para ejecutar:

   **API:**
   ```powershell
   python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
   ```

   **Simulador IoT:**
   ```powershell
   python -m pipeline.simulador_iot
   ```

   **Procesamiento Plata:**
   ```powershell
   python -m pipeline.automatizar_plata
   ```

   **Procesamiento Oro:**
   ```powershell
   python -m pipeline.automatizar_oro
   ```

   **Dashboard:**
   ```powershell
   python -m streamlit run visualizacion/dashboard.py
   ```

   API interactiva: <http://127.0.0.1:8000/docs>. El tablero suele estar disponible en <http://localhost:8501>.

Para la preparación de la base de datos, configuración, pruebas de integración y resolución de problemas, consulta **[SETUP.md](SETUP.md)**.

## Pruebas

```powershell
python -m pytest -v tests/test_privacidad.py tests/test_validacion.py
```

La prueba de integración requiere una base separada (`simon_test_db`) inicializada con el mismo SQL y la variable `SIMON_TEST_DB_URL`. **No apuntar esta prueba a la base operativa `simon_db`.** Consulta [SETUP.md](SETUP.md) para configurarla.

En la verificación local del **20 de noviembre de 2026** se aprobaron **11 pruebas unitarias y 1 prueba de integración PostGIS**. Esto no constituye una prueba de rendimiento a gran escala.

## Consideraciones técnicas y límites

Las geometrías se almacenan en **EPSG:4326**. La autonomía utiliza parámetros fijos de tanque, consumo y distancia restante, y el Driver Score es una regla heurística. El endpoint de registro no incorpora autenticación en el prototipo; el dashboard consulta directamente la base y no aplica el enmascaramiento del endpoint de lectura. La seudonimización no equivale a anonimización irreversible.

Para detalles sobre reglas, índices espaciales, decisiones de diseño y trabajo futuro, consulta **[DESIGN.md](DESIGN.md)**.
