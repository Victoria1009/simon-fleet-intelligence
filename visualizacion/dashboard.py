import os
from pathlib import Path

import pandas as pd
import streamlit as st
import folium
import json

from folium.plugins import HeatMap
from streamlit_folium import st_folium
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from dotenv import load_dotenv

# ==========================================
# CONFIGURACION
# ==========================================

st.set_page_config(
    page_title="SIMON | Fleet Intelligence",
    page_icon="🚗",
    layout="wide"
)

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

url = URL.create(
    drivername="postgresql+psycopg",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DB_NAME", "simon_db")
)

@st.cache_resource
def conectar():
    return create_engine(url, pool_pre_ping=True)

engine = conectar()


# ==========================================
# CONSULTAR GEOCERCAS
# ==========================================

@st.cache_data(ttl=60)
def cargar_geocercas():

    consulta = text("""
        SELECT
            id,
            nombre,
            velocidad_max_kmh,
            ST_AsGeoJSON(geometria) AS geojson
        FROM geocercas
        ORDER BY id
    """)

    with engine.connect() as conexion:
        return pd.read_sql(consulta, conexion)


# ==========================================
# CONSULTA CAPA ORO
# ==========================================

@st.cache_data(ttl=5)
def cargar_datos():
    consulta = text("""
        SELECT
            dispositivo_id,
            timestamp,
            latitud,
            longitud,
            velocidad_kmh,
            combustible_pct,
            nombre_geocerca,
            exceso_velocidad,
            alerta_combustible,
            driver_score
        FROM registros_oro
        WHERE timestamp >= NOW() - INTERVAL '24 hours'
        ORDER BY dispositivo_id, timestamp
        LIMIT 50000
    """)

    with engine.connect() as conexion:
        return pd.read_sql(consulta, conexion)

try:
    df = cargar_datos()
    geocercas = cargar_geocercas()
except Exception as e:
    st.error(f"Error consultando PostgreSQL: {e}")
    st.stop()

# ==========================================
# ENCABEZADO
# ==========================================

st.title("🚗 SIMON | Fleet Intelligence")
st.caption("Monitoreo IoT/AVL - Capa Oro")

if df.empty:
    st.warning("No hay registros disponibles en las ultimas 24 horas.")
    st.stop()

# ==========================================
# FILTROS
# ==========================================

vehiculos = sorted(df["dispositivo_id"].unique())

seleccion = st.sidebar.multiselect(
    "Seleccionar vehiculos",
    vehiculos,
    default=vehiculos
)

mostrar_geocercas = st.sidebar.checkbox(
    "Mostrar geocercas",
    value=True
)

mostrar_rutas = st.sidebar.checkbox(
    "Mostrar trayectorias",
    value=True
)

mostrar_alertas = st.sidebar.checkbox(
    "Mostrar excesos de velocidad",
    value=True
)

mostrar_heatmap = st.sidebar.checkbox(
    "Mostrar mapa de calor",
    value=False
)

datos = df[df["dispositivo_id"].isin(seleccion)].copy()

if datos.empty:
    st.info("Selecciona al menos un vehiculo.")
    st.stop()

# ==========================================
# INDICADORES
# ==========================================

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Vehiculos",
    datos["dispositivo_id"].nunique()
)

col2.metric(
    "Registros",
    len(datos)
)

col3.metric(
    "Excesos de velocidad",
    int(datos["exceso_velocidad"].fillna(False).sum())
)

col4.metric(
    "Driver Score promedio",
    round(datos["driver_score"].mean(), 1)
)

# ==========================================
# MAPA INTERACTIVO
# ==========================================

st.subheader("Trayectorias y alertas")

mapa = folium.Map(
    location=[
        datos["latitud"].mean(),
        datos["longitud"].mean()
    ],
    zoom_start=12,
    tiles="OpenStreetMap"
)


# ==========================================
# VISUALIZACION DE GEOCERCAS
# ==========================================

if mostrar_geocercas:

    colores_geocercas = {
        "Zona urbana SIMON": "blue",
        "Zona residencial SIMON": "orange",
        "Corredor vial SIMON": "green"
    }

    for _, zona in geocercas.iterrows():

        nombre = zona["nombre"]

        color = colores_geocercas.get(
            nombre,
            "purple"
        )

        geometria = json.loads(zona["geojson"])

        folium.GeoJson(
            geometria,
            name=nombre,
            style_function=lambda feature, c=color: {
                "fillColor": c,
                "color": c,
                "weight": 2,
                "fillOpacity": 0.35,
                "opacity": 1
            },
            tooltip=folium.Tooltip(
                f"{nombre} | "
                f"Velocidad maxima: "
                f"{zona['velocidad_max_kmh']} km/h"
            )
        ).add_to(mapa)

colores = [
    "blue",
    "green",
    "purple",
    "orange",
    "darkred"
]

for i, vehiculo in enumerate(seleccion):

    subset = datos[
        datos["dispositivo_id"] == vehiculo
    ].sort_values("timestamp")

    color = colores[i % len(colores)]

    coordenadas = subset[
        ["latitud", "longitud"]
    ].dropna().values.tolist()

    if mostrar_rutas and len(coordenadas) >= 2:
        folium.PolyLine(
            coordenadas,
            color=color,
            weight=3,
            opacity=0.8,
            tooltip=vehiculo
        ).add_to(mapa)

    if coordenadas:
        ultima = coordenadas[-1]

        folium.Marker(
            ultima,
            tooltip=f"Vehiculo: {vehiculo}",
            popup=f"Ultima posicion: {vehiculo}",
            icon=folium.Icon(
                color="blue",
                icon="car",
                prefix="fa"
            )
        ).add_to(mapa)

# ==========================================
# ALERTAS DE VELOCIDAD
# ==========================================

infracciones = datos[
    datos["exceso_velocidad"] == True
].dropna(subset=["latitud", "longitud"])

if mostrar_alertas:
    for _, fila in infracciones.iterrows():

        folium.CircleMarker(
            location=[
                fila["latitud"],
                fila["longitud"]
            ],
            radius=4,
            color="red",
            fill=True,
            fill_opacity=0.7,
            tooltip=(
                f"Vehiculo: {fila['dispositivo_id']} | "
                f"Velocidad: {fila['velocidad_kmh']} km/h"
            )
        ).add_to(mapa)

if mostrar_heatmap and not infracciones.empty:

    HeatMap(
        infracciones[
            ["latitud", "longitud"]
        ].values.tolist(),
        radius=15,
        blur=12
    ).add_to(mapa)

folium.LayerControl(
    collapsed=False
).add_to(mapa)

st_folium(
    mapa,
    width=None,
    height=550,
    returned_objects=[]
)

# ==========================================
# TABLA DE INDICADORES
# ==========================================

st.subheader("Indicadores por vehiculo")

resumen = datos.groupby("dispositivo_id").agg(
    registros=("timestamp", "count"),
    velocidad_promedio=("velocidad_kmh", "mean"),
    excesos_velocidad=("exceso_velocidad", "sum"),
    alertas_combustible=("alerta_combustible", "sum"),
    driver_score=("driver_score", "mean")
).round(2)

st.dataframe(
    resumen,
    use_container_width=True
)

# ==========================================
# ACTUALIZACION
# ==========================================

st.caption(
    "Datos consultados desde PostgreSQL/PostGIS - Capa Oro"
)

if st.button("Actualizar datos"):
    st.cache_data.clear()
    st.rerun()