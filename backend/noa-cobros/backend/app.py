from flask import Flask, request, jsonify
from datetime import date, datetime
import csv, io
from db import get_conn, init_schema
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Inicializa DB
init_schema()

def parse_iso(d):
    d = str(d).strip()
    try:
        if "/" in d:
            return datetime.strptime(d, "%d/%m/%Y").date().isoformat()
        return datetime.strptime(d, "%Y-%m-%d").date().isoformat()
    except Exception:
        raise ValueError("Fecha inválida. Use aaaa-mm-dd o dd/mm/aaaa.")

@app.get("/status")
def status():
    return {"ok": True, "service": "Noa Cobros API", "port": 5056}

@app.get("/facturas")
def listar_facturas():
    q = request.args.get("q", "").strip().lower()
    with get_conn() as conn:
        if q:
            rows = conn.execute(
                "SELECT * FROM facturas WHERE lower(cliente) LIKE ? ORDER BY vence ASC",
                (f"%{q}%",)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM facturas ORDER BY vence ASC"
            ).fetchall()
        return jsonify([dict(r) for r in rows])

@app.post("/facturas")
def crear_factura():
    data = request.get_json(force=True)
    cliente = data.get("cliente")
    monto = data.get("monto")
    vence = data.get("vence")
    estado = data.get("estado", "pendiente")

    if not cliente or monto is None or not vence:
        return {"error": "cliente, monto, vence son obligatorios"}, 400

    try:
        vence = parse_iso(vence)
        monto = float(monto)
    except Exception as e:
        return {"error": str(e)}, 400

    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO facturas (cliente, monto, vence, estado) VALUES (?, ?, ?, ?)",
            (cliente, monto, vence, estado)
        )
        conn.commit()
        fid = cur.lastrowid
        row = conn.execute("SELECT * FROM facturas WHERE id=?", (fid,)).fetchone()
        return dict(row), 201

@app.put("/facturas/<int:fid>")
def actualizar_factura(fid):
    data = request.get_json(force=True)
    fields, values = [], []
    for k in ("cliente", "monto", "vence", "estado"):
        if k in data and data[k] is not None:
            v = data[k]
            if k == "vence":
                v = parse_iso(v)
            if k == "monto":
                v = float(v)
            fields.append(f"{k}=?")
            values.append(v)

    if not fields:
        return {"error": "Nada que actualizar"}, 400

    values.append(fid)
    with get_conn() as conn:
        conn.execute(f"UPDATE facturas SET {', '.join(fields)} WHERE id=?", values)
        conn.commit()
        row = conn.execute("SELECT * FROM facturas WHERE id=?", (fid,)).fetchone()
        if not row:
            return {"error": "No existe"}, 404
        return dict(row)

@app.delete("/facturas/<int:fid>")
def borrar_factura(fid):
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM facturas WHERE id=?", (fid,))
        conn.commit()
        if cur.rowcount == 0:
            return {"error": "No existe"}, 404
        return {"ok": True}

@app.post("/facturas/csv")
def subir_csv():
    if "file" not in request.files:
        return {"error": "Suba un archivo CSV en 'file'"}, 400

    f = request.files["file"]
    content = f.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    expected = {"cliente", "monto", "vence"}
    if set([c.strip().lower() for c in (reader.fieldnames or [])]) != expected:
        return {"error": "Encabezados requeridos: cliente,monto,vence"}, 400

    inserted = 0
    with get_conn() as conn:
        for row in reader:
            cliente = row["cliente"].strip()
            monto = float(row["monto"])
            vence = parse_iso(row["vence"])
            conn.execute(
                "INSERT INTO facturas (cliente, monto, vence) VALUES (?, ?, ?)",
                (cliente, monto, vence)
            )
            inserted += 1
        conn.commit()

    return {"ok": True, "insertadas": inserted}

@app.get("/reporte/mensual")
def reporte_mensual():
    mes = request.args.get("mes")
    hoy = date.today().isoformat()
    y, m = (mes.split("-") if mes else hoy[:7].split("-"))
    like = f"{y}-{int(m):02d}%"

    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM facturas WHERE vence LIKE ?", (like,)).fetchall()

    data = [dict(r) for r in rows]
    total = sum(r["monto"] for r in data) if data else 0.0
    hoy_iso = date.today().isoformat()
    vencidas = [r for r in data if r["vence"] < hoy_iso and r["estado"] == "pendiente"]
    por_vencer = [r for r in data if r["vence"] >= hoy_iso and r["estado"] == "pendiente"]

    resumen = {
        "mes": f"{y}-{int(m):02d}",
        "total_facturas": len(data),
        "monto_total": round(total, 2),
        "pendientes": len([r for r in data if r['estado'] == 'pendiente']),
        "vencidas": len(vencidas),
        "por_vencer": len(por_vencer),
    }
    return {"resumen": resumen, "facturas": data}

@app.post("/whatsapp/simulado")
def whatsapp_simulado():
    payload = request.get_json(force=True)
    return {"ok": True, "simulado": True, "payload": payload}

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5056, debug=True)
