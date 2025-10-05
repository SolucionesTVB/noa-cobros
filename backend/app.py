# app.py — NOA Cobros (modo abierto, sin token)
import os, csv, io
from datetime import datetime, date
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

# ------------------------
# Config base de DB
# ------------------------
def _normalize_db_url(raw: str) -> str:
    if not raw: 
        return "sqlite:///local.db"
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+psycopg://", 1)
    if raw.startswith("postgresql://") and "+psycopg" not in raw:
        return raw.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw

DB_URL = _normalize_db_url(os.getenv("DATABASE_URL", "sqlite:///local.db"))

# MODO ABIERTO: sin token, todo habilitado
OPEN_MODE = True  # <- cuando quieras volver a login, cambialo a False

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DB_URL
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# CORS para Netlify (permití tu dominio prod)
FRONTEND = os.getenv("FRONTEND_ORIGIN", "https://noa-cobros.netlify.app")
CORS(app, resources={r"/*": {"origins": [FRONTEND, "*"]}}, expose_headers=["Content-Disposition"])

db = SQLAlchemy(app)

# ------------------------
# Modelo
# ------------------------
class Cobro(db.Model):
    __tablename__ = "cobro"
    id = db.Column(db.Integer, primary_key=True)
    cliente = db.Column(db.String(255), nullable=False, default="")
    monto = db.Column(db.Float, nullable=False, default=0.0)
    vence = db.Column(db.String(20), nullable=True)           # guardamos ISO "YYYY-MM-DD"
    estado = db.Column(db.String(20), nullable=False, default="pendiente")  # pendiente|pagado
    referencia = db.Column(db.String(100), nullable=True)
    creado_en = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# Util
def _to_iso(dstr: str) -> str:
    if not dstr: 
        return None
    s = str(dstr).strip()
    # soporta dd/mm/aaaa y yyyy-mm-dd
    try:
        if "/" in s:
            d = datetime.strptime(s, "%d/%m/%Y").date()
        else:
            d = datetime.fromisoformat(s).date()
        return d.isoformat()
    except Exception:
        return None

# ------------------------
# Rutas
# ------------------------
@app.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"ok": True, "db": "on", "db_url_scheme": DB_URL.split(":",1)[0]}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 200

@app.get("/cobros")
def cobros_list():
    q = Cobro.query
    desde = _to_iso(request.args.get("desde"))
    hasta = _to_iso(request.args.get("hasta"))
    if desde: q = q.filter(Cobro.vence >= desde)
    if hasta: q = q.filter(Cobro.vence <= hasta)
    q = q.order_by(Cobro.id.desc())
    items = [{
        "id": x.id,
        "cliente": x.cliente,
        "monto": float(x.monto or 0),
        "vence": x.vence,
        "estado": x.estado,
        "referencia": x.referencia
    } for x in q.all()]
    return jsonify(items), 200

@app.post("/cobros/import_csv")
def cobros_import_csv():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "Adjunte archivo en campo 'file'"}), 400
    f = request.files["file"]
    data = f.read()
    buf = io.StringIO(data.decode("utf-8", errors="ignore"))
    reader = csv.DictReader(buf)
    req_cols = {"cliente","monto","vence"}
    if not req_cols.issubset({c.strip().lower() for c in reader.fieldnames or []}):
        return jsonify({"ok": False, "error": "Columnas requeridas: cliente,monto,vence"}), 400
    creados = 0
    for row in reader:
        cliente = (row.get("cliente") or "").strip()
        monto = row.get("monto")
        vence = _to_iso(row.get("vence"))
        estado = (row.get("estado") or "pendiente").strip().lower() or "pendiente"
        ref = (row.get("referencia") or "").strip() or None
        if not cliente or not monto or not vence: 
            continue
        try:
            c = Cobro(cliente=cliente, monto=float(monto), vence=vence, estado=estado, referencia=ref)
            db.session.add(c)
            creados += 1
        except Exception:
            db.session.rollback()
    db.session.commit()
    return jsonify({"ok": True, "creados": creados}), 201

@app.get("/cobros/export")
def cobros_export():
    rows = Cobro.query.order_by(Cobro.id.asc()).all()
    headers = ["id","cliente","monto","vence","estado","referencia"]
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(headers)
    for r in rows:
        w.writerow([r.id, r.cliente, f"{float(r.monto or 0):.2f}", r.vence or "", r.estado or "", r.referencia or ""])
    csv_bytes = io.BytesIO(out.getvalue().encode("utf-8"))
    return send_file(csv_bytes, mimetype="text/csv; charset=utf-8",
                     as_attachment=True, download_name="export_cobros.csv")

@app.post("/cobros/<int:cid>/cobrar")
def cobros_cobrar(cid: int):
    c = Cobro.query.get(cid)
    if not c:
        return jsonify({"ok": False, "error": "no_encontrado"}), 404
    c.estado = "pagado"
    db.session.commit()
    return jsonify({"ok": True, "id": c.id, "estado": c.estado}), 200
