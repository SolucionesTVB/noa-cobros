import os
from datetime import datetime, date
import io

from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import sqlalchemy as sa

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///facturas.db")
engine = sa.create_engine(DATABASE_URL, future=True)
metadata = sa.MetaData()

facturas = sa.Table(
    "facturas", metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("cliente", sa.String(255), nullable=False),
    sa.Column("monto", sa.Float, nullable=False),
    sa.Column("vence", sa.Date, nullable=False),
    sa.Column("estado", sa.String(32), nullable=False, default="pendiente"),
)

metadata.create_all(engine)

REQUIRED_COLS = {"cliente", "monto", "vence"}

def _to_date(val):
    if pd.isna(val):
        return None
    if isinstance(val, (datetime, date, pd.Timestamp)):
        return pd.Timestamp(val).date()
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    return None

def _read_any_table(file_storage):
    name = (file_storage.filename or "").lower()
    content = file_storage.read()
    buf = io.BytesIO(content)
    if name.endswith(".csv"):
        df = pd.read_csv(buf)
    elif name.endswith(".xlsx") or name.endswith(".xls"):
        df = pd.read_excel(buf)
    else:
        raise ValueError("Formato no soportado. Use .csv, .xlsx o .xls")

    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {', '.join(sorted(missing))}")

    df = df[list(REQUIRED_COLS)].copy()
    df["cliente"] = df["cliente"].astype(str).str.strip()
    df["monto"] = pd.to_numeric(df["monto"], errors="coerce")
    df["vence"] = df["vence"].apply(_to_date)
    df = df.dropna(subset=["cliente", "monto", "vence"])
    return df

def _estado_por_fecha(fecha_vence: date) -> str:
    hoy = datetime.utcnow().date()
    return "vencida" if fecha_vence < hoy else "pendiente"

@app.get("/facturas")
def listar_facturas():
    with engine.begin() as conn:
        result = conn.execute(sa.select(facturas).order_by(facturas.c.vence.asc(), facturas.c.id.asc()))
        data = [dict(row._mapping) for row in result]
        for r in data:
            if isinstance(r["vence"], (datetime, date)):
                r["vence"] = pd.Timestamp(r["vence"]).date().isoformat()
    return jsonify({"ok": True, "data": data})

@app.post("/upload-file")
def upload_file():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "Adjunte el archivo en el campo 'file'."}), 400
    f = request.files["file"]
    try:
        df = _read_any_table(f)
        rows = df.to_dict(orient="records")

        with engine.begin() as conn:
            for r in rows:
                estado = _estado_por_fecha(r["vence"])
                conn.execute(facturas.insert().values(
                    cliente=r["cliente"],
                    monto=float(r["monto"]),
                    vence=r["vence"],
                    estado=estado
                ))

            result = conn.execute(sa.select(facturas).order_by(facturas.c.vence.asc(), facturas.c.id.asc()))
            data = [dict(row._mapping) for row in result]
            for r in data:
                if isinstance(r["vence"], (datetime, date)):
                    r["vence"] = pd.Timestamp(r["vence"]).date().isoformat()

        return jsonify({"ok": True, "insertados": len(rows), "total": len(data), "data": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5050)))
