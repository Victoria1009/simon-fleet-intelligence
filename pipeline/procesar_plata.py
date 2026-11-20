from sqlalchemy import text
from backend.conexion_db import engine

CAPACIDAD_TANQUE = 50.0
CONSUMO_L_100KM = 8.0
DISTANCIA_RESTANTE_KM = 300.0

consulta = text("""
WITH pendientes AS (
    SELECT
        b.id,
        b.dispositivo_id,
        b.timestamp,
        b.geometria,
        b.velocidad_kmh,
        b.combustible_pct
    FROM registros_vehiculos b
    WHERE NOT EXISTS (
        SELECT 1
        FROM registros_enriquecidos p
        WHERE p.registro_bronce_id = b.id
    )
),
evaluados AS (
    SELECT
        b.*,
        g.id AS geocerca_id,
        g.nombre AS nombre_geocerca,
        g.velocidad_max_kmh,

        CASE
            WHEN g.id IS NULL THEN FALSE
            ELSE b.velocidad_kmh >
                 g.velocidad_max_kmh
        END AS exceso_velocidad,

        (
            :capacidad *
            (b.combustible_pct / 100.0)
            / :consumo
        ) * 100.0 AS autonomia_km

    FROM pendientes b

    LEFT JOIN LATERAL (
        SELECT
            z.id,
            z.nombre,
            z.velocidad_max_kmh
        FROM geocercas z
        WHERE ST_Covers(
            z.geometria,
            b.geometria
        )
        ORDER BY
            z.prioridad DESC,
            z.velocidad_max_kmh ASC,
            z.id ASC
        LIMIT 1
    ) g ON TRUE
),
calculados AS (
    SELECT
        *,
        autonomia_km < :distancia
            AS alerta_combustible,

        CASE
            WHEN NOT exceso_velocidad THEN 0
            WHEN velocidad_kmh -
                 velocidad_max_kmh <= 10 THEN 10
            WHEN velocidad_kmh -
                 velocidad_max_kmh <= 20 THEN 20
            ELSE 35
        END AS penalizacion_velocidad

    FROM evaluados
)
INSERT INTO registros_enriquecidos (
    registro_bronce_id,
    dispositivo_id,
    timestamp,
    geometria,
    geocerca_id,
    nombre_geocerca,
    velocidad_kmh,
    velocidad_max_kmh,
    exceso_velocidad,
    combustible_pct,
    autonomia_km,
    distancia_restante_km,
    alerta_combustible,
    driver_score
)
SELECT
    id,
    dispositivo_id,
    timestamp,
    geometria,
    geocerca_id,
    nombre_geocerca,
    velocidad_kmh,
    velocidad_max_kmh,
    exceso_velocidad,
    combustible_pct,
    autonomia_km,
    :distancia,
    alerta_combustible,
    GREATEST(
        0,
        100
        - penalizacion_velocidad
        - CASE
            WHEN alerta_combustible THEN 15
            ELSE 0
          END
    )
FROM calculados
ON CONFLICT (registro_bronce_id)
DO NOTHING
RETURNING id;
""")

with engine.begin() as conexion:
    resultado = conexion.execute(
        consulta,
        {
            "capacidad": CAPACIDAD_TANQUE,
            "consumo": CONSUMO_L_100KM,
            "distancia": DISTANCIA_RESTANTE_KM
        }
    )

    cantidad = len(resultado.fetchall())

print("Procesamiento Capa Plata finalizado")
print("Nuevos registros procesados:", cantidad)