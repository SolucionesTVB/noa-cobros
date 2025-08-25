from flask import Flask, request, jsonify
from flask_cors import CORS
import csv
import io
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# "BD" en memoria para hoy (simple)
FACTURAS = []  # cada item: {"cliente": str, "monto": int, "vence": "dd/mm"}

@app.get("/")
def health():
    return "Servidor vivo ✅"

# 1) Resumen de cobro (ya lo tenías)
@app.post("/ia/resumen-cobro")
def resumen_cobro():
    data = request.get_json() or {}
    texto = data.get("texto", "")
    return jsonify({
        "ok": True,
        "respuesta": f"Resumen IA: {texto[:60]}... Cliente A debe ₡75,000. Fecha límite: 30/08."
    })

# 2) Enviar WhatsApp (simulado)
@app.post("/ia/enviar-whatsapp")
def enviar_whatsapp():
    data = request.get_json() or {}
    telefono = data.get("telefono", "")
    mensaje = data.get("mensaje", "")
    if not telefono or not mensaje:
        return jsonify({"ok": False, "error": "Falta telefono o mensaje"}), 400
    return jsonify({"ok": True, "status": f"Mensaje enviado a {telefono}"}), 200

# ----------- NUEVO: CARGA CSV -----------
# CSV esperado (encabezados flexibles, sin importar mayúsculas):
# cliente | monto | vence    (vence formato dd/mm o dd/mm/aaaa)
@app.post("/ia/upload-csv")
def upload_csv():
    if "archivo" not in request.files:
        return jsonify({"ok": False, "error": "Falta archivo CSV (campo 'archivo')"}), 400

    f = request.files["archivo"]
    if not f.filename.lower().endswith(".csv"):
        return jsonify({"ok": False, "error": "Solo se admite CSV por hoy"}), 400

    # Leer como texto
    content = f.read().decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(content))

    # Normalizar nombres de columnas
    cols = {c.lower().strip(): c for c in reader.fieldnames or []}
    req = ["cliente", "monto", "vence"]
    if not all(k in cols for k in req):
        return jsonify({"ok": False, "error": "CSV debe tener columnas: cliente, monto, vence"}), 400

    # Limpiar actual y cargar
    FACTURAS.clear()
    cargadas = 0
    for row in reader:
        cliente = (row.get(cols["cliente"]) or "").strip()
        monto_raw = (row.get(cols["monto"]) or "").replace("₡", "").replace(",", "").strip()
        vence_raw = (row.get(cols["vence"]) or "").strip()

        if not cliente or not monto_raw or not vence_raw:
            continue

        try:
            monto = int(float(monto_raw))
        except:
            continue

        # Normalizar fecha a dd/mm
        vence = normalizar_fecha_ddmm(vence_raw)
        if not vence:
            continue

        FACTURAS.append({"cliente": cliente, "monto": monto, "vence": vence})
        cargadas += 1

    return jsonify({"ok": True, "cargadas": cargadas})

def normalizar_fecha_ddmm(txt):
    txt = txt.replace("-", "/").strip()
    fmts = ["%d/%m/%Y", "%d/%m/%y", "%d/%m"]
    for fmt in fmts:
        try:
            dt = datetime.strptime(txt, fmt)
            # si vino sin año, asumir año actual
            if fmt == "%d/%m":
                dt = dt.replace(year=datetime.now().year)
            return dt.strftime("%d/%m")
        except:
            continue
    return None

# 3) Reporte mensual dinámico (usa FACTURAS cargadas)
@app.get("/ia/reporte-mensual")
def reporte_mensual():
    if not FACTURAS:
        # sin datos cargados: ejemplo
        reporte = {
            "total_facturas": 1,
            "pagadas": 0,
            "pendientes": 1,
            "monto_total": "₡75,000",
            "vencen_esta_semana": [
                {"cliente": "Cliente A", "monto": "₡75,000", "vence": "30/08"},
            ]
        }
        return jsonify({"ok": True, "reporte": reporte})

    total = len(FACTURAS)
    monto_total = sum(x["monto"] for x in FACTURAS)

    hoy = datetime.now().date()
    fin_semana = hoy + timedelta(days=7)
    vencen_semana = []

    for x in FACTURAS:
        dd, mm = x["vence"].split("/")
        try:
            dt = datetime(year=hoy.year, month=int(mm), day=int(dd)).date()
        except:
            continue
        if hoy <= dt <= fin_semana:
            vencen_semana.append({
                "cliente": x["cliente"],
                "monto": f"₡{x['monto']:,}".replace(",", "."),
                "vence": x["vence"]
            })

    reporte = {
        "total_facturas": total,
        "pagadas": 0,                # sin lógica de pagos hoy
        "pendientes": total,
        "monto_total": f"₡{monto_total:,}".replace(",", "."),
        "vencen_esta_semana": vencen_semana
    }
    return jsonify({"ok": True, "reporte": reporte})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5056)



