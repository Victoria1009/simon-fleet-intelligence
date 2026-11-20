"""Integración: ejecuta el SQL original Plata/Oro en una transacción que se revierte.
Requiere SIMON_TEST_DB_URL apuntando a una BD DE PRUEBAS inicializada con simon_inicializacion.sql.
No usar simon_db de producción/desarrollo: los scripts procesan TODOS los pendientes.
"""
import ast
import os
from pathlib import Path
import pytest
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]

def sql_original(nombre):
    tree=ast.parse((ROOT/nombre).read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t,ast.Name) and t.id=='consulta' for t in node.targets):
            return text(ast.literal_eval(node.value.args[0]))
    raise AssertionError(f'No se encontró consulta SQL en {nombre}')

@pytest.fixture
def conn():
    url=os.getenv('SIMON_TEST_DB_URL')
    if not url:
        pytest.skip('Configura SIMON_TEST_DB_URL para ejecutar integración PostGIS')
    engine=create_engine(url)
    with engine.connect() as c:
        transaction=c.begin()
        try:
            yield c
        finally:
            transaction.rollback()
    engine.dispose()

def test_geocercas_alertas_autonomia_y_oro(conn):
    # Coordenadas dentro de la geocerca residencial original.
    registro=conn.execute(text('''INSERT INTO registros_vehiculos
        (dispositivo_id,"timestamp",latitud,longitud,velocidad_kmh,combustible_pct,geometria)
        VALUES ('TEST-RESIDENCIAL',NOW(),4.715,-74.075,45,20,ST_SetSRID(ST_MakePoint(-74.075,4.715),4326))
        RETURNING id''')).scalar_one()
    plata=sql_original('pipeline/procesar_plata.py')
    conn.execute(plata,{'capacidad':50.0,'consumo':8.0,'distancia':300.0}).fetchall()
    r=conn.execute(text('''SELECT nombre_geocerca,velocidad_max_kmh,exceso_velocidad,
        autonomia_km,alerta_combustible,driver_score FROM registros_enriquecidos
        WHERE registro_bronce_id=:id'''),{'id':registro}).mappings().one()
    assert r['nombre_geocerca']=='Zona residencial SIMON'
    assert r['velocidad_max_kmh']==30
    assert r['exceso_velocidad'] is True
    assert r['autonomia_km']==pytest.approx(125.0)
    assert r['alerta_combustible'] is True
    assert r['driver_score']==65  # 100 - 20 por 15 km/h - 15 por combustible
    conn.execute(sql_original('pipeline/procesar_oro.py')).fetchall()
    o=conn.execute(text('''SELECT o.driver_score,o.exceso_velocidad,o.autonomia_km
        FROM registros_oro o JOIN registros_enriquecidos p ON p.id=o.registro_plata_id
        WHERE p.registro_bronce_id=:id'''),{'id':registro}).mappings().one()
    assert o['driver_score']==65 and o['exceso_velocidad'] is True
    assert o['autonomia_km']==pytest.approx(125.0)
