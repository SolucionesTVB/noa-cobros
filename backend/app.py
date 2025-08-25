from flask import Flask, request, jsonify
from datetime import datetime
import csv, io
from flask_cors import CORS
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "noa_cobros.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_schema():
    with get_conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS facturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT NOT NULL,
            monto REAL NOT NULL,
            vence TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'pendiente',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """)
        conn.commit()

app = Flask(__name__)

# CORS: habilitado para cualquier origen (Netlify) y métodos comunes
CORS(app, resources={r"/*": {"origins": "*"}})

# Refuerzo CORS (headers después de cada respuesta, incluido OPTIONS)
@app.after_request
def add_cors_headers(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return resp

init_schema()

# --- Salud
@app.get("/")
def raiz():
    return {"ok": True, "service": "Noa Cobros API"}

@app.get("/status")
def status():
    return {"ok": True, "service": "Noa Cobros API", "port": 5056}

# --- Utils
def parse_iso(d):
    d = str(d).strip()
    try:
        if "/" in d:
            return datetime.strptime(d, "%d/%m/%Y").date().isoformat()
        return datetime.strptime(d, "%Y-%m-%d").date().isoformat()
    except Exception:
        raise ValueError("Fecha inválida. Use aaaa-mm-dd o dd/mm/aaaa.")

# --- CRUD demo mínimo
@app.get("/facturas")
def listar_facturas():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM facturas ORDER BY vence ASC").fetchall()
        return jsonify([dict(r) for r in rows])

@app.post("/facturas")
def crear_factura():
    data = request.get_json(force=True)
    cliente, monto, vence = data.get("cliente"), data.get("monto"), data.get("vence")
    if not cliente or monto is None or not vence:
        return {"error": "cliente, monto, vence son obligatorios"}, 400
    try:
        vence = parse_iso(vence)
        monto = float(monto)
    except Exception as e:
        return {"error": str(e)}, 400
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO facturas (cliente, monto, vence) VALUES (?, ?, ?)",
            (cliente, monto, vence)
        )
        conn.commit()
        fid = cur.lastrowid
        row = conn.execute("SELECT * FROM facturas WHERE id=?", (fid,)).fetchone()
        return dict(row), 201

# --- IA: endpoint con soporte de OPTIONS para preflight
@app.route("/ia/resumen-cobro", methods=["POST", "OPTIONS"])
def ia_resumen_cobro():
    if request.method == "OPTIONS":
        # Respuesta al preflight
        return ("", 204)
    data = request.get_json(silent=True) or {}
    cliente = data.get("cliente", "N/D")
    try:
        monto = float(data.get("monto", 0) or 0)
    except:
        monto = 0.0
    return {
        "ok": True,
        "resumen": f"Preparar cobro a {cliente} por {monto:,.2f} CRC.",
        "sugerencias": ["Enviar WhatsApp", "Programar recordatorio", "Marcar seguimiento"]
    }

# Log de rutas (útil en Render Logs)
for r in app.url_map.iter_rules():
    print(f"[ROUTE] {r.rule} -> {sorted(r.methods)}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5056)

# --- Actualizar factura (p. ej. marcar pagada)
@app.route("/facturas/<int:fid>", methods=["PUT", "OPTIONS"])
def actualizar_factura(fid):
    if request.method == "OPTIONS":
        return ("", 204)
    data = request.get_json(silent=True) or {}
    fields, values = [], []
    for k in ("cliente", "monto", "vence", "estado"):
        if k in data and data[k] is not None:
            v = data[k]
            if k == "monto":
                try: v = float(v)
                except: v = 0.0
            if k == "vence":
                v = parse_iso(v)
            fields.append(f"{k}=?"); values.append(v)
    if not fields:
        return {"error": "Nada que actualizar"}, 400
    values.append(fid)
    with get_conn() as conn:
        conn.execute(f"UPDATE facturas SET {', '.join(fields)} WHERE id=?", values)
        conn.commit()
        row = conn.execute("SELECT * FROM facturas WHERE id=?", (fid,)).fetchone()
        if not row:
            return {"error": "No existe"}, 404
        return dict(row), 200
