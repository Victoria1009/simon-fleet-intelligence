"""Valida el modelo Pydantic real, sin abrir una conexión a la BD."""
import ast
from datetime import datetime, timezone
from pathlib import Path
import pytest
from pydantic import BaseModel, Field, ValidationError

# Se extrae la clase original sin importar main.py (que importa conexion_db).
source = Path(__file__).resolve().parents[1] / 'backend' / 'main.py'
tree = ast.parse(source.read_text(encoding='utf-8'))
node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'RegistroVehiculo')
namespace = {'BaseModel': BaseModel, 'Field': Field, 'datetime': datetime}
exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
RegistroVehiculo = namespace['RegistroVehiculo']

@pytest.fixture
def valido():
    return dict(dispositivo_id='VHC-8472-ABC', timestamp=datetime.now(timezone.utc), latitud=4.7, longitud=-74.1, velocidad_kmh=50, combustible_pct=60)

@pytest.mark.parametrize('campo,valor', [('latitud',91),('latitud',-91),('longitud',181),('longitud',-181),('velocidad_kmh',-1),('combustible_pct',-1),('combustible_pct',101)])
def test_rechaza_valores_invalidos(valido,campo,valor):
    valido[campo]=valor
    with pytest.raises(ValidationError):
        RegistroVehiculo(**valido)

def test_acepta_limites_validos(valido):
    valido.update(latitud=90, longitud=-180, velocidad_kmh=0, combustible_pct=100)
    assert RegistroVehiculo(**valido).combustible_pct == 100
