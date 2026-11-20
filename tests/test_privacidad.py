"""Pruebas unitarias de la implementación real de privacidad.py."""
import importlib
import pytest

@pytest.fixture
def privacidad(monkeypatch):
    monkeypatch.setenv('MASKING_SECRET', 'clave-solo-para-pruebas')
    from backend import privacidad
    return importlib.reload(privacidad)

def test_id_determinista_y_no_reversible_directamente(privacidad):
    a = privacidad.anonimizar_id('VHC-8472-ABC')
    assert a == privacidad.anonimizar_id('VHC-8472-ABC')
    assert a.startswith('VEH-') and len(a) == 20
    assert '8472' not in a

def test_ids_diferentes_producen_resultados_diferentes(privacidad):
    assert privacidad.anonimizar_id('VHC-8472-ABC') != privacidad.anonimizar_id('VHC-2356-DEF')

def test_enmascarar_registro(privacidad):
    registro = dict(dispositivo_id='VHC-8472-ABC', timestamp='2026-11-20T10:00:00Z', latitud=4.71234, longitud=-74.07321, velocidad_kmh=42, combustible_pct=70)
    salida = privacidad.enmascarar_registro(registro)
    assert 'dispositivo_id' not in salida
    assert salida['vehiculo'] == privacidad.anonimizar_id(registro['dispositivo_id'])
    assert salida['latitud_aproximada'] == 4.71
    assert salida['longitud_aproximada'] == -74.07
    assert salida['velocidad_kmh'] == 42
