import math
import time
import random
import requests
from datetime import datetime, timezone

URL = "http://127.0.0.1:8000/vehiculos/registrar"
INTERVALO = 5

# Rutas sintéticas: (latitud, longitud)
RUTAS = {
    "VHC-8472-ABC": [
        (4.7110, -74.0721),
        (4.7150, -74.0700),
        (4.7190, -74.0670),
        (4.7230, -74.0640)
    ],
    "VHC-2356-DEF": [
        (4.6500, -74.1000),
        (4.6540, -74.0970),
        (4.6580, -74.0940),
        (4.6620, -74.0910)
    ],
    "VHC-9812-GHI": [
        (4.7300, -74.0500),
        (4.7340, -74.0530),
        (4.7380, -74.0560),
        (4.7420, -74.0590)
    ]
}


def distancia_km(p1, p2):
    """Distancia geodesica aproximada (Haversine)."""
    lat1, lon1 = map(math.radians, p1)
    lat2, lon2 = map(math.radians, p2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return 6371.0088 * 2 * math.asin(
        min(1, math.sqrt(a))
    )


# Estado persistente durante la simulacion
estados = {}

for dispositivo, ruta in RUTAS.items():
    estados[dispositivo] = {
        "posicion": ruta[0],
        "objetivo": 1,
        "combustible": random.uniform(65, 95)
    }


def actualizar_vehiculo(dispositivo, segundos):
    estado = estados[dispositivo]
    ruta = RUTAS[dispositivo]

    origen = estado["posicion"]
    destino = ruta[estado["objetivo"]]

    # 10 % de probabilidad de detenerse
    velocidad_deseada = (
        0.0 if random.random() < 0.10
        else random.uniform(20, 55)
    )

    distancia_disponible = distancia_km(
        origen, destino
    )

    distancia_maxima = (
        velocidad_deseada * segundos / 3600
    )

    if distancia_disponible <= distancia_maxima:
        nueva_posicion = destino
        estado["objetivo"] = (
            estado["objetivo"] + 1
        ) % len(ruta)

    elif distancia_disponible > 0:
        fraccion = (
            distancia_maxima / distancia_disponible
        )

        nueva_posicion = (
            origen[0] + fraccion *
            (destino[0] - origen[0]),
            origen[1] + fraccion *
            (destino[1] - origen[1])
        )
    else:
        nueva_posicion = origen

    distancia_real = distancia_km(
        origen, nueva_posicion
    )

    velocidad_real = (
        distancia_real / segundos * 3600
        if segundos > 0 else 0
    )

    # Consumo sintetico de 8 L/100 km
    # Deposito supuesto de 50 litros
    litros_consumidos = distancia_real * 0.08
    porcentaje_consumido = (
        litros_consumidos / 50 * 100
    )

    estado["combustible"] = max(
        0,
        estado["combustible"]
        - porcentaje_consumido
    )

    estado["posicion"] = nueva_posicion

    return {
        "dispositivo_id": dispositivo,
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "latitud": round(nueva_posicion[0], 7),
        "longitud": round(nueva_posicion[1], 7),
        "velocidad_kmh": round(velocidad_real, 2),
        "combustible_pct": round(
            estado["combustible"], 2
        )
    }


print("SIMON: simulador iniciado")

ultimo_ciclo = time.monotonic() - INTERVALO

try:
    while True:
        inicio = time.monotonic()
        segundos = max(
            inicio - ultimo_ciclo, 0.001
        )
        ultimo_ciclo = inicio

        for dispositivo in RUTAS:
            paquete = actualizar_vehiculo(
                dispositivo, segundos
            )

            try:
                respuesta = requests.post(
                    URL,
                    json=paquete,
                    timeout=3
                )
                respuesta.raise_for_status()

                print(
                    dispositivo,
                    "Velocidad:",
                    paquete["velocidad_kmh"],
                    "km/h",
                    "Combustible:",
                    paquete["combustible_pct"],
                    "%"
                )

            except requests.RequestException as error:
                print("Error de envio:", error)

        espera = INTERVALO - (
            time.monotonic() - inicio
        )
        time.sleep(max(0, espera))

except KeyboardInterrupt:
    print("Simulacion detenida")
