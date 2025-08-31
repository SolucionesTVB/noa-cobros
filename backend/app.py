from flask import Flask, request, jsonify
from flask_cors import CORS
app = Flask(__name__)
CORS(app)

@app.get("/health")
def health():
    return jsonify({"ok": True})

@app.post("/upload-file")
def upload_file():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "file missing"}), 400
    f = request.files["file"]
    content = f.read().decode("utf-8", errors="ignore")
    rows = []
    for i, line in enumerate(content.splitlines()):
        if not line.strip(): continue
        if i == 0: continue  # cabecera
        parts = [p.strip() for p in line.split(",")]
        cliente = parts[0] if len(parts)>0 else ""
        try: monto = float(parts[1]) if len(parts)>1 and parts[1] else 0.0
        except: monto = 0.0
        vence  = parts[2] if len(parts)>2 else ""
        estado = parts[3] if len(parts)>3 else "Pendiente"
        rows.append({"Cliente": cliente, "Monto": monto, "Vence": vence, "Estado": estado})
    return jsonify({"ok": True, "rows": rows})

@app.get("/notificar")
def notificar():
    dry = request.args.get("dry_run", "0") == "1"
    # Demo: en real, leerías de DB o memoria
    sample = [
        {"Cliente":"Empresa A","Monto":120000.0,"Vence":"2025-09-05","Estado":"Pendiente"},
        {"Cliente":"Empresa B","Monto":250000.0,"Vence":"2025-09-10","Estado":"Pendiente"},
    ]
    if dry:
        return jsonify({"ok": True, "dry_run": True, "to_send": len(sample), "ejemplos": sample[:2]})
    # Aquí iría el envío real (WhatsApp)
    return jsonify({"ok": True, "sent": len(sample)})

# ========= Notificaciones =========
from typing import List, Dict

def _load_rows_for_notify() -> List[Dict]:
    """
    Fuente de datos para notificar.
    - Si ya tienes filas en memoria tras /upload-file, úsalas.
    - Si guardas en archivo/DB, cámbialo aquí.
    """
    try:
        # Si tu código guarda en una variable global FACTURAS (común en nuestro boceto):
        return FACTURAS  # type: ignore # noqa
    except Exception:
        return []

def _build_message(row: Dict) -> str:
    cliente = str(row.get("Cliente", "")).strip()
    monto   = row.get("Monto", 0)
    vence   = str(row.get("Vence", "")).strip()
    return f"Estimado {cliente}, le recordamos que su factura por ₡{monto:,.0f} vence el {vence}. Gracias."

@app.get("/notificar")
def notificar(dry_run: int = 1, limit: int = 10):
    rows = _load_rows_for_notify()
    if not rows:
        return jsonify({"ok": False, "error": "No hay facturas cargadas."})

    # Prepara mensajes
    preview = []
    for r in rows[:max(1, limit)]:
        msg = _build_message(r)
        # En esta fase no enviamos nada (solo dry run)
        preview.append({
            "Cliente": r.get("Cliente"),
            "Vence":   r.get("Vence"),
            "Monto":   r.get("Monto"),
            "Estado":  r.get("Estado", "Pendiente"),
            "mensaje": msg
        })

    return jsonify({
        "ok": True,
        "dry_run": bool(dry_run),
        "total": len(rows),
        "to_send": min(len(rows), max(1, limit)),
        "ejemplos": preview
    })
# --- Wasender test endpoint (nombre único) ---
import os, requests

WASENDER_API_KEY = os.getenv("WASENDER_API_KEY")
WASENDER_URL = "https://api.wasenderapi.com/sendMessage"

@app.post("/notificar-test")   # ruta distinta de /notificar
def notificar_test():          # nombre de función distinto
    payload = {
        "apiKey": WASENDER_API_KEY,
        "session": "Noa asistencia",      # nombre exacto de tu sesión en Wasender
        "phone": "+50660457989",          # tu número de prueba
        "message": "✅ Prueba Noa Cobros vía WasenderAPI (FastAPI)."
    }
    r = requests.post(WASENDER_URL, json=payload)
    try:
        return {"ok": r.ok, "status": r.status_code, "resp": r.json()}
    except Exception:
        return {"ok": r.ok, "status": r.status_code, "resp": r.text}
# --- Wasender test endpoint (ruta y nombre únicos) ---
import os, requests

WASENDER_API_KEY = os.getenv("WASENDER_API_KEY")
WASENDER_URL = "https://api.wasenderapi.com/sendMessage"

@app.post("/notificar-test")
def notificar_test():
    payload = {
        "apiKey": WASENDER_API_KEY,
        "session": "Noa asistencia",
        "phone": "+50660457989",
        "message": "✅ Prueba Noa Cobros vía WasenderAPI (FastAPI)."
    }
    r = requests.post(WASENDER_URL, json=payload)
    try:
        return {"ok": r.ok, "status": r.status_code, "resp": r.json()}
    except Exception:
        return {"ok": r.ok, "status": r.status_code, "resp": r.text}
