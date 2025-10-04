# app.py — NOA Cobros (prod limpio, con CSV import / cobrar / export)

import os, io, csv, time
from datetime import datetime, date, timedelta
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import bcrypt, jwt

# ---------- Config base ----------
def _normalize_db_url(raw: str) -> str:
    if not raw: return "sqlite:///local.db"
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+psycopg://", 1)
    if raw.startswith("postgresql://") and "+psycopg" not in raw:
        return raw.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw

DB_URL      = _normalize_db_url(os.getenv("DATABASE_URL", "sqlite:///local.db"))
JWT_SECRET  = os.getenv("JWT_SECRET", "dev-inseguro-cambia-esto")
ADMIN_SECRET= os.getenv("ADMIN_SECRET", "changeme-admin")
NETLIFY_ORG = (os.getenv("FRONTEND_ORIGIN","").strip()
               or "https://noa-cobros.netlify.app")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DB_URL
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# CORS
CORS(
    app,
    resources={r"/*": {"origins": [NETLIFY_ORG]}},
    supports_credentials=False,
    expose_headers=["Content-Disposition"],
    methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"],
    allow_headers=["Content-Type","Authorization"],
)
@app.after_request
def _add_cors_headers(resp):
    resp.headers.setdefault("Access-Control-Allow-Origin", NETLIFY_ORG)
    resp.headers.setdefault("Vary","Origin")
    resp.headers.setdefault("Access-Control-Allow-Headers","Content-Type, Authorization")
    resp.headers.setdefault("Access-Control-Allow-Methods","GET, POST, PUT, PATCH, DELETE, OPTIONS")
    return resp

db = SQLAlchemy(app)

# ---------- Modelos ----------
class User(db.Model):
    __tablename__ = "user"
    id         = db.Column(db.Integer, primary_key=True)
    email      = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=True)
    creado_en  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class Cobro(db.Model):
    __tablename__ = "cobro"
    id          = db.Column(db.Integer, primary_key=True)
    cliente     = db.Column(db.String(255), nullable=True)    # NUEVO
    monto       = db.Column(db.Float, nullable=False, default=0.0)
    vence       = db.Column(db.Date, nullable=True)           # NUEVO
    descripcion = db.Column(db.String(255), nullable=False, default="")
    estado      = db.Column(db.String(50), nullable=False, default="pendiente")
    referencia  = db.Column(db.String(100), nullable=True)
    creado_en   = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

# ---------- Migraciones mínimas ----------
def ensure_user_columns():
    with app.app_context():
        try:
            db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);'))
            db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS creado_en TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW();'))
            db.session.commit()
        except Exception as e:
            db.session.rollback(); app.logger.error(f"ensure_user_columns error: {e}")

def ensure_cobro_columns():
    with app.app_context():
        try:
            db.session.execute(text('ALTER TABLE "cobro" ADD COLUMN IF NOT EXISTS referencia VARCHAR(100);'))
            db.session.execute(text('ALTER TABLE "cobro" ADD COLUMN IF NOT EXISTS cliente   VARCHAR(255);'))
            db.session.execute(text('ALTER TABLE "cobro" ADD COLUMN IF NOT EXISTS vence     DATE;'))
            db.session.commit()
        except Exception as e:
            db.session.rollback(); app.logger.error(f"ensure_cobro_columns error: {e}")

def create_tables_once():
    with app.app_context():
        db.create_all()
        ensure_user_columns()
        ensure_cobro_columns()

# ---------- Auth helpers ----------
def make_token(email: str) -> str:
    payload = {"sub": email, "exp": datetime.utcnow() + timedelta(hours=12), "iat": datetime.utcnow()}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def read_token(auth_header: str):
    if not auth_header or not auth_header.startswith("Bearer "): return None
    token = auth_header.split(" ", 1)[1].strip()
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return data.get("sub")
    except Exception:
        return None

def require_auth():
    email = read_token(request.headers.get("Authorization", ""))
    if not email: return None, (jsonify({"error": "no_autorizado"}), 401)
    u = User.query.filter_by(email=email).first()
    if not u: return None, (jsonify({"error": "no_autorizado"}), 401)
    return u, None

# ---------- Util ----------
def _parse_date(s):
    if not s: return None
    if isinstance(s, (date, datetime)): return s if isinstance(s,date) else s.date()
    s = str(s).strip()
    for fmt in ("%Y-%m-%d","%d/%m/%Y","%d-%m-%Y","%m/%d/%Y"):
        try: return datetime.strptime(s, fmt).date()
        except Exception: pass
    return None

# ---------- Rutas base ----------
@app.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"ok": True, "db": "on", "db_url_scheme": DB_URL.split(":", 1)[0]}), 200
    except Exception as e:
        return jsonify({"ok": False, "db": "off", "error": str(e)}), 200

@app.get("/__ok")
def __ok():
    try:
        routes = [str(r) for r in app.url_map.iter_rules()]
        return jsonify({"ok": True, "routes_count": len(routes),
                        "has_stats": any("/stats" in r for r in routes),
                        "version": os.getenv("APP_VERSION", "") or str(int(time.time()))}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ---------- Admin debug ----------
@app.get("/admin/routes")
def admin_routes():
    if request.headers.get("X-Admin-Secret") != ADMIN_SECRET:
        return jsonify({"ok": False, "error": "forbidden"}), 403
    routes = [{"rule": str(r), "methods": sorted(list(r.methods - {"HEAD", "OPTIONS"}))} for r in app.url_map.iter_rules()]
    return jsonify({"ok": True, "count": len(routes), "routes": routes})

# ---------- Auth ----------
@app.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"error": "faltan_datos"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"ok": True, "detail": "ya_existe"}), 200
    try:
        pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        u = User(email=email, password_hash=pw_hash)
        db.session.add(u); db.session.commit()
        return jsonify({"ok": True, "id": u.id, "email": u.email}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "db_error", "detail": str(e)}), 500

@app.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"error": "faltan_datos"}), 400
    u = User.query.filter_by(email=email).first()
    if not u or not getattr(u, "password_hash", None):
        return jsonify({"error": "credenciales_invalidas"}), 401
    try:
        ok = bcrypt.checkpw(password.encode("utf-8"), u.password_hash.encode("utf-8"))
    except Exception as e:
        return jsonify({"error": "bcrypt_error", "detail": str(e)}), 500
    if not ok:
        return jsonify({"error": "credenciales_invalidas"}), 401
    token = make_token(email)
    return jsonify({"access_token": token, "token_type": "bearer"}), 200

@app.get("/users")
def list_users():
    u, err = require_auth()
    if err: return err
    items = [{"id": x.id, "email": x.email} for x in User.query.order_by(User.id.asc()).limit(10).all()]
    if not items: items = [{"id": 1, "email": "demo@noa.com"}]
    return jsonify(items), 200

# ---------- Cobros: listar y crear ----------
@app.get("/cobros")
def cobros_list():
    u, err = require_auth()
    if err: return err
    q = Cobro.query
    estado = request.args.get("estado")
    if estado: q = q.filter(Cobro.estado == estado)
    desde = request.args.get("desde"); hasta = request.args.get("hasta")
    if desde:
        try: q = q.filter(Cobro.creado_en >= datetime.fromisoformat(desde))
        except Exception: pass
    if hasta:
        try: q = q.filter(Cobro.creado_en <= datetime.fromisoformat(hasta))
        except Exception: pass
    q = q.order_by(Cobro.id.desc())
    items = [{
        "id": x.id, "cliente": x.cliente, "monto": float(x.monto or 0.0),
        "vence": x.vence.isoformat() if x.vence else None,
        "estado": x.estado, "referencia": x.referencia,
        "descripcion": x.descripcion, "creado_en": x.creado_en.isoformat()
    } for x in q.all()]
    return jsonify(items), 200

@app.post("/cobros")
def cobros_create():
    u, err = require_auth()
    if err: return err
    data = request.get_json(silent=True) or {}
    try:
        c = Cobro(
            cliente=(data.get("cliente") or "").strip() or None,
            monto=float(data.get("monto") or 0.0),
            vence=_parse_date(data.get("vence")),
            descripcion=(data.get("descripcion") or "").strip(),
            estado=(data.get("estado") or "pendiente").strip(),
            referencia=(data.get("referencia") or None)
        )
        db.session.add(c); db.session.commit()
        return jsonify({
            "id": c.id, "cliente": c.cliente, "monto": c.monto,
            "vence": c.vence.isoformat() if c.vence else None,
            "descripcion": c.descripcion, "estado": c.estado,
            "referencia": c.referencia, "creado_en": c.creado_en.isoformat()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "db_error", "detail": str(e)}), 500

# ---------- Cobros: importar CSV ----------
@app.post("/cobros/import_csv")
def cobros_import_csv():
    u, err = require_auth()
    if err: return err
    f = request.files.get("file")
    if not f: return jsonify({"error":"archivo_requerido"}), 400
    # Leer CSV (coma o punto y coma)
    raw = f.read().decode("utf-8", errors="ignore")
    sniffer = csv.Sniffer()
    dialect = sniffer.sniff(raw.splitlines()[0]) if raw else csv.excel
    reader = csv.DictReader(io.StringIO(raw), dialect=dialect)
    creados = 0
    for row in reader:
        try:
            cliente = (row.get("cliente") or row.get("nombre") or row.get("descripcion") or "").strip()
            monto = float((row.get("monto") or "0").replace(",","").replace(" ",""))
            vence = _parse_date(row.get("vence"))
            estado = (row.get("estado") or "pendiente").strip().lower()
            referencia = (row.get("referencia") or row.get("ref") or None)
            c = Cobro(cliente=cliente or None, monto=monto, vence=vence,
                      estado=estado if estado in ("pendiente","pagado") else "pendiente",
                      referencia=referencia, descripcion=cliente[:255] if cliente else "")
            db.session.add(c); creados += 1
        except Exception:
            db.session.rollback()
    db.session.commit()
    return jsonify({"ok": True, "creados": creados})

# ---------- Cobros: cobrar ----------
@app.post("/cobros/<int:cid>/cobrar")
@app.patch("/cobros/<int:cid>/cobrar")
def cobros_cobrar(cid):
    u, err = require_auth()
    if err: return err
    c = Cobro.query.get(cid)
    if not c: return jsonify({"error":"no_encontrado"}), 404
    c.estado = "pagado"; db.session.commit()
    return jsonify({"ok":True, "id": c.id, "estado": c.estado})

# ---------- Cobros: export CSV ----------
@app.get("/cobros/export")
def cobros_export():
    u, err = require_auth()
    if err: return err
    q = Cobro.query.order_by(Cobro.id.desc()).all()
    cols = ["id","cliente","monto","vence","estado","referencia","creado_en"]
    def gen():
        yield ",".join(cols) + "\n"
        for x in q:
            row = {
                "id": x.id,
                "cliente": x.cliente or "",
                "monto": f"{float(x.monto or 0):.2f}",
                "vence": x.vence.isoformat() if x.vence else "",
                "estado": x.estado,
                "referencia": x.referencia or "",
                "creado_en": x.creado_en.isoformat()
            }
            yield ",".join(f"\"{str(row[k]).replace('\"','\"\"')}\"" for k in cols) + "\n"
    headers = {
        "Content-Type":"text/csv; charset=utf-8",
        "Content-Disposition":"attachment; filename=cobros_export.csv"
    }
    return Response(gen(), headers=headers)

# ---------- Stats ----------
@app.get("/stats")
def stats():
    u, err = require_auth()
    if err: return err
    q = Cobro.query
    desde = request.args.get("desde"); hasta = request.args.get("hasta"); estado = request.args.get("estado")
    if desde:
        try: q = q.filter(Cobro.creado_en >= datetime.fromisoformat(desde))
        except Exception: pass
    if hasta:
        try: q = q.filter(Cobro.creado_en <= datetime.fromisoformat(hasta))
        except Exception: pass
    if estado: q = q.filter(Cobro.estado == estado)
    items = q.all()
    total = sum(float(x.monto or 0.0) for x in items)
    count = len(items)
    pagados = sum(1 for x in items if x.estado == "pagado")
    pendientes = sum(1 for x in items if x.estado == "pendiente")
    return jsonify({"count": count, "total": total, "pagados": pagados, "pendientes": pendientes}), 200

# ---------- Boot ----------
create_tables_once()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5050)))
