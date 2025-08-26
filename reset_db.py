import os
import sqlalchemy as sa

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///facturas.db")
engine = sa.create_engine(DATABASE_URL, future=True)

with engine.begin() as conn:
    conn.exec_driver_sql("DROP TABLE IF EXISTS facturas;")
print("Tabla 'facturas' eliminada. Se recreará al iniciar app.py")
