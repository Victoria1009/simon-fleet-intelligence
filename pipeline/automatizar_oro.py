import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

# ==========================================
# CONFIGURACION
# ==========================================

INTERVALO = 5

CARPETA = Path(__file__).resolve().parent
SCRIPT = CARPETA / "procesar_oro.py"

print("SIMON - Automatizacion Capa Oro")
print(f"Intervalo: {INTERVALO} segundos")

# ==========================================
# PROCESAMIENTO CONTINUO
# ==========================================

try:
    while True:

        inicio = time.monotonic()

        print(
            "\nProcesando Capa Oro:",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        resultado = subprocess.run(
            [sys.executable, "-m", "pipeline.procesar_oro"],
            cwd=CARPETA.parent,
            capture_output=True,
            text=True
        )

        if resultado.returncode == 0:
            print(resultado.stdout)
        else:
            print("Error en Capa Oro:")
            print(resultado.stderr)

        duracion = time.monotonic() - inicio
        time.sleep(max(0, INTERVALO - duracion))

except KeyboardInterrupt:
    print("\nAutomatizacion Capa Oro detenida")
