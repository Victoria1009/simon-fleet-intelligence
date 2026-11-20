# SIMON — Diseño técnico del pipeline geoespacial IoT/AVL

## 1. Objetivo y alcance

Este prototipo procesa reportes simulados de telemetría vehicular mediante una arquitectura de tres capas (Bronce, Plata y Oro). Recibe coordenadas GPS, velocidad y combustible, determina la pertenencia a geocercas, calcula alertas y un puntaje de conducción (*Driver Score*) y expone resultados para consulta y visualización.

Es una demostración técnica local, no una plataforma de producción ni una prueba de rendimiento a escala masiva.

## 2. Arquitectura

```text
pipeline/simulador_iot.py (reportes cada 5 s)
          |
          v
FastAPI: POST /vehiculos/registrar (backend/main.py)
          |
          v
PostgreSQL / PostGIS
  Bronce: registros_vehiculos
          |
          v
pipeline/procesar_plata.py (automatizar_plata.py, cada 5 s)
  Plata: registros_enriquecidos <--- geocercas
          |
          v
pipeline/procesar_oro.py (automatizar_oro.py, cada 5 s)
  Oro: registros_oro
          |
          v
visualizacion/dashboard.py (Streamlit + mapa)
```

La ingesta y el procesamiento se ejecutan como procesos independientes. Los automatizadores invocan scripts Python periódicamente mediante `subprocess`; no se utiliza un broker de mensajes ni una infraestructura de *streaming* distribuido.

## 3. Componentes y modelo de datos

| Tabla | Función | Campos principales |
|---|---|---|
| `registros_vehiculos` | Bronce: conserva cada reporte recibido | `dispositivo_id`, `timestamp`, `latitud`, `longitud`, `velocidad_kmh`, `combustible_pct`, `geometria` |
| `geocercas` | Polígonos de referencia y reglas de velocidad | `nombre`, `tipo`, `velocidad_max_kmh`, `prioridad`, `geometria` |
| `registros_enriquecidos` | Plata: resultados de la evaluación espacial y reglas | `registro_bronce_id`, `geocerca_id`, `exceso_velocidad`, `autonomia_km`, `alerta_combustible`, `driver_score` |
| `registros_oro` | Oro: estructura consolidada para analítica | `registro_plata_id`, `dispositivo_id`, `timestamp`, coordenadas, alertas, autonomía y puntaje |

Las geometrías se almacenan con SRID 4326. Los puntos se crean mediante `ST_SetSRID(ST_MakePoint(longitud, latitud), 4326)`: **el orden es longitud, latitud**. La base aplica restricciones de rango para coordenadas y combustible. Las tablas Plata y Oro usan claves únicas de origen para impedir duplicados por reprocesamiento.

El archivo `database/simon_inicializacion.sql` crea el esquema, índices y tres geocercas de demostración. La geometría de la zona urbana incluye un recorte para evitar superposiciones con otra zona; si en el futuro se superponen polígonos, la selección de reglas también está definida por prioridad.

## 4. Capa Bronce: ingesta y privacidad

`simulador_iot.py` genera movimientos simulados de tres vehículos y envía solicitudes HTTP a `POST /vehiculos/registrar` aproximadamente cada cinco segundos. La API valida el paquete con Pydantic: latitud [-90, 90], longitud [-180, 180], velocidad no negativa y combustible entre 0 y 100 %. Los datos se insertan mediante SQL parametrizado.

El endpoint `GET /vehiculos/consulta` requiere la cabecera `x-api-key` y limita la respuesta a los 100 reportes más recientes. `backend/privacidad.py` reemplaza el identificador original por un seudónimo estable basado en HMAC-SHA256 con `MASKING_SECRET`, y redondea las coordenadas a dos decimales. Este mecanismo **no equivale a anonimización irreversible**: los seudónimos permiten correlacionar registros y las ubicaciones aproximadas pueden seguir siendo sensibles. La API de registro no implementa autenticación en el código actual; el dashboard consulta directamente la base y no aplica ese enmascaramiento. Estas son limitaciones de seguridad a resolver antes de un despliegue real.

## 5. Capa Plata: enriquecimiento espacial y reglas

### 5.1 Geocercas

La consulta SQL selecciona una geocerca por punto mediante un `LEFT JOIN LATERAL` y `ST_Covers(z.geometria, b.geometria)`. A diferencia de `ST_Contains`, `ST_Covers` también considera cubiertos los puntos sobre el límite del polígono. Si más de una geocerca cubre el punto, se elige la de mayor `prioridad`, luego la de menor `velocidad_max_kmh` y finalmente el menor `id`.

Si no existe una geocerca coincidente, se conserva el registro con campos de geocerca nulos y `exceso_velocidad = FALSE`. En ese caso, el sistema **no verifica** un límite de velocidad exterior a las geocercas.

### 5.2 Exceso de velocidad

Se activa cuando `velocidad_kmh > velocidad_max_kmh` para la geocerca seleccionada. La comparación es estricta: circular exactamente al límite no se considera exceso.

### 5.3 Autonomía predictiva

El cálculo implementado es:

```text
autonomia_km = capacidad_tanque_l * (combustible_pct / 100)
               / consumo_l_100km * 100
alerta_combustible = autonomia_km < distancia_restante_km
```

Los parámetros actuales de `pipeline/procesar_plata.py` son capacidad del tanque **50 L**, consumo **8 L/100 km** y distancia restante estimada **300 km**, iguales para todos los vehículos. La distancia restante no proviene de una ruta real ni de un motor de navegación; es un supuesto de demostración. El modelo supone consumo constante.

### 5.4 Driver Score

Puntaje inicial: **100 puntos**. Penalización por velocidad: 0 si no hay exceso; 10 si el exceso es de hasta 10 km/h; 20 si es de más de 10 y hasta 20 km/h; y 35 si supera 20 km/h. Se descuentan **15 puntos adicionales** cuando existe alerta de combustible.

```text
driver_score = max(0, 100 - penalizacion_velocidad
                       - (15 si hay alerta_combustible, si no 0))
```

Este puntaje es una regla heurística de demostración, no un modelo calibrado de riesgo vial ni una evaluación integral del comportamiento del conductor.

### 5.5 Procesamiento incremental

La capa Plata selecciona registros Bronce sin correspondencia en `registros_enriquecidos` mediante `NOT EXISTS`, e inserta con `ON CONFLICT (registro_bronce_id) DO NOTHING`. La restricción `UNIQUE` protege contra inserciones duplicadas. El proceso se ejecuta por lotes periódicos, no en tiempo real estricto.

## 6. Capa Oro y visualización

`pipeline/procesar_oro.py` copia de forma incremental los registros Plata aún no incluidos en `registros_oro`, usando `NOT EXISTS` y `ON CONFLICT (registro_plata_id) DO NOTHING`. Extrae `latitud` y `longitud` con `ST_Y` y `ST_X` de la geometría y conserva los resultados de las alertas y el puntaje.

`visualizacion/dashboard.py` consulta la capa Oro de las **últimas 24 horas**, permite seleccionar vehículos y representar trayectorias, geocercas, alertas y puntos calientes. Las consultas del tablero tienen caché temporal; la visualización es un complemento analítico y no constituye un sistema de monitoreo de producción.

## 7. Estrategia de indexación y rendimiento

Índices incluidos en el esquema recuperado:

| Índice | Tipo | Propósito |
|---|---|---|
| `idx_geocercas_geom` | GiST sobre `geocercas.geometria` | Búsquedas espaciales para asignación de geocercas |
| `idx_plata_geom` | GiST sobre `registros_enriquecidos.geometria` | Filtros espaciales sobre datos enriquecidos |
| `idx_oro_geom` | GiST sobre `registros_oro.geometria` | Consultas espaciales analíticas |
| `idx_oro_vehiculo_fecha` | B-tree sobre vehículo y fecha descendente | Historiales y trayectorias por vehículo |
| `idx_oro_excesos` | B-tree parcial sobre fecha para `exceso_velocidad = TRUE` | Consultas de infracciones |

Las claves primarias y restricciones `UNIQUE` también generan índices de soporte. El uso de GiST permite al planificador reducir candidatos en operaciones espaciales compatibles, pero el beneficio concreto depende del volumen, la selectividad y el plan de ejecución.

**Límite de evidencia:** no se han realizado pruebas con millones de puntos ni mediciones `EXPLAIN (ANALYZE, BUFFERS)` que permitan asegurar respuestas en milisegundos. La prueba automatizada de integración mide la ejecución de un escenario pequeño, no el rendimiento Big Data. Para escalar, sería necesario evaluar planes reales, paginación/lotes acotados, particionamiento temporal, retención de históricos, concurrencia y monitoreo.

## 8. Pruebas y resultados

- `tests/test_privacidad.py`: seudonimización y formato de consulta.
- `tests/test_validacion.py`: validación de rangos de entrada.
- `tests/test_pipeline_postgis.py`: inserta un registro en una base de prueba, ejecuta el SQL original de Plata y Oro y verifica geocerca, exceso de velocidad, autonomía, alerta y Driver Score; al finalizar revierte la transacción.

**Ejecución local reportada el 20/11/2026:** 11 pruebas unitarias aprobadas y 1 prueba de integración PostGIS aprobada. El escenario espacial de integración comprobó una geocerca residencial de 30 km/h, velocidad de 45 km/h, combustible al 20 %, autonomía de 125 km, alerta activa y Driver Score de 65.

La cobertura no es exhaustiva: faltan escenarios de límites de polígonos, puntos fuera de geocercas, empates de prioridad, valores nulos, concurrencia y pruebas de carga.

## 9. Decisiones y compromisos (*trade-offs*)

- **PostGIS frente a geoprocesamiento en Python:** se priorizan consultas espaciales en base de datos para evitar transferencias de grandes conjuntos de puntos al cliente; a cambio, la lógica depende de funciones SQL/PostGIS.
- **Tablas materializadas por capa frente a vistas:** facilitan trazabilidad y consumo BI, pero duplican información y requieren sincronización.
- **Lotes periódicos frente a streaming:** simplifican el prototipo y su operación local, con latencia variable entre ingesta y disponibilidad en Oro.
- **Parámetros globales de autonomía frente a modelo por vehículo/ruta:** hacen reproducible el cálculo, pero limitan su precisión operativa.
- **HMAC y coordenadas aproximadas:** reducen exposición en un endpoint de lectura, sin reemplazar autenticación robusta, autorización por roles ni controles de acceso a base de datos.

## 10. Limitaciones y próximos pasos

1. Incorporar autenticación/autorización por roles para ingesta, consultas y dashboard; restringir privilegios de base de datos.
2. Parametrizar capacidad, consumo y ruta restante por vehículo; calibrar el Driver Score con evidencia de conducción.
3. Agregar más escenarios de pruebas, carga y concurrencia, y documentar planes de ejecución con `EXPLAIN ANALYZE`.
4. Procesar lotes limitados con reintentos y observabilidad, y estudiar particionamiento por fecha para históricos grandes.
5. Establecer una estrategia de despliegue, gestión de secretos, auditoría y retención de datos sensibles.

## 11. Archivos principales

- **`backend/`**: `main.py` (API), `conexion_db.py` (conexión), `privacidad.py` (seudonimización).
- **`pipeline/`**: `simulador_iot.py`, `procesar_plata.py`, `automatizar_plata.py`, `procesar_oro.py`, `automatizar_oro.py`.
- **`database/simon_inicializacion.sql`**: esquema PostGIS, índices y geocercas de demostración.
- **`visualizacion/dashboard.py`**: tablero Streamlit.
- **`tests/`**: pruebas unitarias y de integración.
- **`SETUP.md`**: instalación, ejecución y verificación.

**Nota de configuración pendiente de cotejo:** la guía de instalación original citaba `API_READ_KEY` y el archivo `.env.example` usa `API_KEY`. Antes de publicar, confirmar el nombre efectivo en `backend/main.py` y unificar los archivos de configuración. Esta discrepancia documental no permite determinar por sí sola qué nombre espera el código.
