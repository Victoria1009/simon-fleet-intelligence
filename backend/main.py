import os
import hmac
from fastapi import FastAPI
from fastapi import HTTPException, Depends, Header
from datetime import datetime
from pydantic import BaseModel, Field
from sqlalchemy import text
from backend.conexion_db import engine
from backend.privacidad import enmascarar_registro

app = FastAPI(
    title="API SIMON",
    description="Sistema de monitoreo de vehículos IoT/AVL",
    version="1.0.0"
)

@app.get("/")
def inicio():
    return {
        "mensaje": "API SIMON funcionando correctamente",
        "estado": "activo"
    }


# Estructura del paquete IoT/AVL
class RegistroVehiculo(BaseModel):
    dispositivo_id: str
    timestamp: datetime
    latitud: float = Field(ge=-90, le=90)
    longitud: float = Field(ge=-180, le=180)
    velocidad_kmh: float = Field(ge=0)
    combustible_pct: float = Field(ge=0, le=100)

# Endpoint para recibir datos
@app.post("/vehiculos/registrar")
def registrar_vehiculo(datos: RegistroVehiculo):

    consulta = text("""
        INSERT INTO registros_vehiculos (
            dispositivo_id,
            timestamp,
            latitud,
            longitud,
            velocidad_kmh,
            combustible_pct,
            geometria
        )
        VALUES (
            :dispositivo_id,
            :timestamp,
            :latitud,
            :longitud,
            :velocidad_kmh,
            :combustible_pct,
            ST_SetSRID(
                ST_MakePoint(:longitud, :latitud),
                4326
            )
        )
        RETURNING id
    """)

    try:
        with engine.begin() as conexion:
            resultado = conexion.execute(
                consulta,
                datos.model_dump()
            )
            registro_id = resultado.scalar_one()

        return {
            "mensaje": "Registro almacenado correctamente",
            "registro_id": registro_id
        }

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="No se pudo almacenar el registro"
        )


def verificar_api_key(
    x_api_key: str = Header(default="")
):
    clave_esperada = os.getenv("API_READ_KEY")

    if not clave_esperada:
        raise HTTPException(
            status_code=503,
            detail="Clave de lectura no configurada"
        )

    if not hmac.compare_digest(
        x_api_key, clave_esperada
    ):
        raise HTTPException(
            status_code=401,
            detail="Acceso no autorizado"
        )


@app.get("/vehiculos/consulta")
def consultar_vehiculos(
    _: None = Depends(verificar_api_key)
):
    consulta = text("""
        SELECT
            dispositivo_id,
            timestamp,
            latitud,
            longitud,
            velocidad_kmh,
            combustible_pct
        FROM registros_vehiculos
        ORDER BY timestamp DESC, id DESC
        LIMIT 100
    """)

    with engine.connect() as conexion:
        filas = conexion.execute(
            consulta
        ).mappings().all()

    return {
        "total": len(filas),
        "registros": [
            enmascarar_registro(dict(fila))
            for fila in filas
        ]
    }
