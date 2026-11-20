import os
import hmac
import hashlib
from dotenv import load_dotenv

load_dotenv()

CLAVE = os.getenv("MASKING_SECRET")

if not CLAVE:
    raise RuntimeError(
        "Falta MASKING_SECRET en el archivo .env"
    )


def anonimizar_id(dispositivo_id):
    digest = hmac.new(
        CLAVE.encode("utf-8"),
        dispositivo_id.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return "VEH-" + digest[:16].upper()


def enmascarar_registro(registro):
    return {
        "vehiculo": anonimizar_id(
            registro["dispositivo_id"]
        ),
        "timestamp": registro["timestamp"],
        "latitud_aproximada": round(
            registro["latitud"], 2
        ),
        "longitud_aproximada": round(
            registro["longitud"], 2
        ),
        "velocidad_kmh": registro["velocidad_kmh"],
        "combustible_pct": registro["combustible_pct"]
    }
