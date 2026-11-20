import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

# ==========================================
# 1. CONEXION A POSTGRESQL
# ==========================================

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

url = URL.create(
    drivername="postgresql+psycopg",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DB_NAME", "simon_db"),
)

engine = create_engine(url, pool_pre_ping=True)

# ==========================================
# 2. PROCESAMIENTO INCREMENTAL CAPA ORO
# ==========================================

consulta = text("""
    INSERT INTO registros_oro (
        registro_plata_id,
        dispositivo_id,
        timestamp,
        latitud,
        longitud,
        geometria,
        velocidad_kmh,
        combustible_pct,
        nombre_geocerca,
        limite_velocidad,
        exceso_velocidad,
        alerta_combustible,
        driver_score,
        autonomia_km,
        distancia_restante_km,
        fecha_procesamiento
    )
    SELECT
        p.id,
        p.dispositivo_id,
        p.timestamp,
        ST_Y(p.geometria),
        ST_X(p.geometria),
        p.geometria,
        p.velocidad_kmh,
        p.combustible_pct,
        p.nombre_geocerca,
        p.velocidad_max_kmh,
        p.exceso_velocidad,
        p.alerta_combustible,
        p.driver_score,
        p.autonomia_km,
        p.distancia_restante_km,
        NOW()
    FROM registros_enriquecidos p
    WHERE NOT EXISTS (
        SELECT 1
        FROM registros_oro o
        WHERE o.registro_plata_id = p.id
    )
    ON CONFLICT (registro_plata_id)
    DO NOTHING
    RETURNING id;
""")

# ==========================================
# 3. EJECUCION
# ==========================================

try:
    with engine.begin() as conexion:
        resultado = conexion.execute(consulta)
        nuevos = len(resultado.fetchall())

    print("Conexion exitosa con PostgreSQL")
    print("Procesamiento Capa Oro finalizado")
    print(f"Nuevos registros incorporados: {nuevos}")

except Exception as error:
    print("Error procesando Capa Oro:")
    print(error)
    raise
finally:
    engine.dispose()
