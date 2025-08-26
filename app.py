import os, io
from datetime import datetime, date
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

def _to_date(v):
    if pd.isna(v): return None
    if isinstance(v, (datetime, date, pd.Timestamp)): return pd.Timestamp(v).date()
    s = str(v).strip()
    for fmt in ("%Y-%m-%d","%d/%m/%Y","%d-%m-%Y","%m/%d/%Y"):
        try: return datetime.strptime(s, fmt).date()
        except: pass
    return None

@app.get("/facturas")
def facturas_list():
    with engine.begin() as c:
        rows = [dict(r._mapping) for r in c.execute(sa.select(facturas).order_by(facturas.c.id))]
        for r in rows:
            if isinstance(r["vence"], (datetime,date)): r["vence"] = pd.Timestamp(r["vence"]).date().isoformat()
    return jsonify({"ok": True, "data": rows})

@app.post("/upload-file")
def upload_file():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "Adjunte 'file'."}), 400
    f = request.files["file"]
    name = (f.filename or "").lower()
    buf = io.BytesIO(f.read())
    if name.endswith(".csv"):
        df = pd.read_csv(buf)
    elif name.endswith(".xlsx") or name.endswith(".xls"):
        df = pd.read_excel(buf)
    else:
        return jsonify({"ok": False, "error": "Use .csv/.xlsx/.xls"}), 400

    df.columns = [str(c).strip().lower() for c in df.columns]
    for req in ["cliente","monto","vence"]:
        if req not in df.columns:
            return jsonify({"ok": False, "error": f"Falta columna requerida: {req}"}), 400

    df = df[["cliente","monto","vence"]].copy()
    df["cliente"] = df["cliente"].astype(str).str.strip()
    df["monto"] = pd.to_numeric(df["monto"], errors="coerce")
    df["vence"] = df["vence"].apply(_to_date)
    df = df.dropna(subset=["cliente","monto","vence"])

    hoy = datetime.utcnow().date()
    df["estado"] = df["vence"].apply(lambda d: "vencida" if d < hoy else "pendiente")

    with engine.begin() as c:
        for r in df.to_dict(orient="records"):
            c.execute(facturas.insert().values(**r))

        total = c.execute(sa.func.count(facturas.c.id)).scalar_one()

    return jsonify({"ok": True, "insertados": len(df), "total": int(total)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5050)))
