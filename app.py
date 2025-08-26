import os
import io
from datetime import datetime, date, timedelta

from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import sqlalchemy as sa
import requests

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
    sa.Column("telefono", sa.String(32), nullable=True),
)
metadata.create_all(engine)

# si faltara la columna telefono en una tabla vieja, la agregamos
try:
    insp = sa.inspect(engine)
    cols = [c["name"] for c in insp.get_columns("facturas")]
    if "telefono" not in cols:
        with engine.begin() as conn:
            conn.exec_driver_sql("ALTER TABLE facturas ADD COLUMN telefono VARCHAR(32);")
except Exception:
    pass

REQUIRED_COLS = {"cliente", "monto", "vence"}
OPTIONAL_COLS = {"telefono"}

def _to_date(val):
    if pd.isna(val): return None
    if isinstance(val, (datetime, date, pd.Timestamp)):
        return pd.Timestamp(val).date()
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try: return datetime.strptime(s, fmt).date()
        except Exception: pass
    return None

def _read_any_table(file_storage):
    name = (file_storage.filename or "").lower()
    buf = io.BytesIO(file_storage.read())
    if name.endswith(".csv"): df = pd.read_csv(buf)
    elif name.endswith(".xlsx") or name.endswith(".xls"): df = pd.read_excel(buf)
    else: raise ValueError("Formato no soportado. Use .csv, .xlsx o .xls")

    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = REQUIRED_COLS - set(df.columns)
    if missing: raise ValueError(f"Faltan columnas requeridas: {', '.join(sorted(missing))}")

    cols = list(REQUIRED_COLS | (OPTIONAL_COLS & set(df.columns)))
    df = df[cols].copy()
    df["cliente"] = df["cliente"].astype(str).str.strip()
    df["monto"] = pd.to_numeric(df["monto"], errors="coerce")
    df["vence"] = df["vence"].apply(_to_date)
    if "telefono" in df.columns:
        df["telefono"] = df["telefono"].astype(str).str.replace(" ","").str.replace("-","").str.strip()
        df.loc[df["telefono"].isin(["", "nan", "None"]), "telefono"] = None
    df = df.dropna(subset=["cliente","monto","vence"])
    return df

def _estado_por_fecha(f): 
    hoy = datetime.utcnow().date()
    return "vencida" if f < hoy else "pendiente"

def _compose_message(cliente,monto,vence):
    tpl = os.getenv("WASENDER_MSG_TEMPLATE",
        "Estimado {cliente}, le recordamos su factura por ₡{monto} que vence el {vence}. – {firma}")
    firma = os.getenv("PLANTILLA_FIRMA","Noa Cobros")
    return tpl.format(cliente=cliente, monto=f"{monto:,.0f}".replace(",","."), vence=pd.Timestamp(vence).date().strftime("%d/%m/%Y"), firma=firma)

def _send_whatsapp(phone,msg):
    url = os.getenv("WASENDER_URL","https://api.wasenderapi.com/send-message")
    api_key = os.getenv("WASENDER_API_KEY","")
    if not api_key: return {"ok": False, "error": "Falta WASENDER_API_KEY"}
    try:
        r = requests.post(url, json={"api_key": api_key, "phone": phone, "message": msg}, timeout=15)
        ok = 200 <= r.status_code < 300
        return {"ok": ok, "status": r.status_code, "resp": (r.text[:300] if r.text else "")}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/facturas")
def listar_facturas():
    with engine.begin() as conn:
        rows = [dict(r._mapping) for r in conn.execute(sa.select(facturas).order_by(facturas.c.vence.asc(), facturas.c.id.asc()))]
        for r in rows:
            if isinstance(r["vence"], (datetime,date)): r["vence"] = pd.Timestamp(r["vence"]).date().isoformat()
    return jsonify({"ok": True, "data": rows})

@app.post("/upload-file")
def upload_file():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "Adjunte el archivo en el campo 'file'."}), 400
    try:
        df = _read_any_table(request.files["file"])
        rows = df.to_dict(orient="records")
        with engine.begin() as conn:
            for r in rows:
                conn.execute(facturas.insert().values(
                    cliente=r["cliente"], monto=float(r["monto"]), 
                    vence=r["vence"], estado=_estado_por_fecha(r["vence"]), 
                    telefono=r.get("telefono")))
            data = [dict(x._mapping) for x in conn.execute(sa.select(facturas))]
            for r in data:
                if isinstance(r["vence"], (datetime,date)): r["vence"] = pd.Timestamp(r["vence"]).date().isoformat()
        return jsonify({"ok": True, "insertados": len(rows), "total": len(data), "data": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@app.post("/notificar")
def notificar():
    modo = (request.args.get("modo") or "proximas").lower()
    dias = int(request.args.get("dias") or 3)
    dry_run = request.args.get("dry_run") == "1"
    hoy = datetime.utcnow().date()
    hasta = hoy + timedelta(days=dias)

    with engine.begin() as conn:
        data = [dict(r._mapping) for r in conn.execute(sa.select(facturas))]
    for r in data:
        if isinstance(r["vence"], str): r["vence"] = _to_date(r["vence"])

    if   modo == "vencidas": candidatos = [r for r in data if r["estado"] == "vencida"]
    elif modo == "todas":    candidatos = data
    else:                    candidatos = [r for r in data if r["vence"] and hoy <= r["vence"] <= hasta]

    candidatos = [r for r in candidatos if r.get("telefono")]
    resultados = []
    for r in candidatos:
        msg = _compose_message(r["cliente"], float(r["monto"]), r["vence"])
        if dry_run:
            resultados.append({"id": r["id"], "cliente": r["cliente"], "telefono": r["telefono"], "message": msg, "sent": False, "dry_run": True})
        else:
            resp = _send_whatsapp(r["telefono"], msg)
            resultados.append({"id": r["id"], "cliente": r["cliente"], "telefono": r["telefono"], "sent": bool(resp.get("ok")), "resp": resp})
    return jsonify({"ok": True, "total_candidatos": len(candidatos), "enviados_ok": sum(1 for r in resultados if r.get("sent")), "resultados": resultados[:100]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5050)))
