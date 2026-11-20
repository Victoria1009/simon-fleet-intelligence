import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

INTERVALO = 5

CARPETA = Path(__file__).resolve().parent
SCRIPT = CARPETA / "procesar_plata.py"

print("SIMON - Procesamiento automatico Capa Plata")
print("Intervalo:", INTERVALO, "segundos")

try:
    while True:
        inicio = time.monotonic()

        print(
            "\nProcesando:",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        resultado = subprocess.run(
            [sys.executable, "-m", "pipeline.procesar_plata"],
            cwd=CARPETA.parent,
            capture_output=True,
            text=True
        )

        if resultado.returncode == 0:
            print(resultado.stdout)
        else:
            print("Error de procesamiento:")
            print(resultado.stderr)

        duracion = time.monotonic() - inicio
        time.sleep(max(0, INTERVALO - duracion))

except KeyboardInterrupt:
    print("\nProcesamiento automatico detenido")
