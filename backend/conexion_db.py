import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

load_dotenv()

url = URL.create(
    drivername="postgresql+psycopg",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DB_NAME"),
)

engine = create_engine(url)

try:
    with engine.connect() as conexion:
        resultado = conexion.execute(
            text("SELECT PostGIS_Version();")
        )
        print("Conexión exitosa con PostgreSQL")
        print("PostGIS:", resultado.scalar())

except Exception as error:
    print("Error de conexión:", error)
