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

# =======================
#  Wasender: helpers
# =======================
import os, requests
from flask import request, jsonify

def _safe_json_response(resp):
    try:
        return resp.json()
    except Exception:
        return {"text": resp.text[:400]}

def _send_whatsapp_text(to: str, text: str):
    """
    Envía un texto por Wasender API usando variables de entorno:
      - WASENDER_API_KEY     (ya la tienes)
      - WASENDER_API_URL     (opcional, default https://api.wasenderapi.com)
      - WASENDER_SESSION     (nombre de la sesión; ej: "Noa asistencia")
    """
    api_key  = os.getenv("WASENDER_API_KEY", "")
    api_url  = os.getenv("WASENDER_API_URL", "https://api.wasenderapi.com").rstrip("/")
    session  = os.getenv("WASENDER_SESSION", "Noa asistencia")
    headers  = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload  = {"session": session, "to": to, "text": text}

    r = requests.post(f"{api_url}/api/v1/messages/send-text",
                      json=payload, headers=headers, timeout=20)
    return r

# =======================
#  Wasender: endpoints
# =======================

@app.route("/notificar-test", methods=["POST"])
def notificar_test():
    """
    Prueba sencilla de WhatsApp:
    body JSON: { "to": "+506XXXXXXXX", "message": "texto" }
    """
    data = request.get_json(force=True, silent=True) or {}
    to   = data.get("to")
    msg  = data.get("message")

    if not to or not msg:
        return jsonify({"ok": False, "error": "Falta 'to' o 'message'"}), 400

    try:
        r = _send_whatsapp_text(to, msg)
        return jsonify({"ok": r.ok, "status": r.status_code, "resp": _safe_json_response(r)}), r.status_code
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# Si ya tienes /notificar definido en tu archivo, NO dupliques la función.
# Asegúrate de que la ruta acepte GET y POST para dry_run y envío real.
@app.route("/notificar", methods=["GET","POST"])
def notificar():
    """
    GET o POST ?dry_run=1  -> solo calcula y muestra (no envía)
    POST sin dry_run       -> enviaría mensajes (placeholder)
    """
    dry = (request.args.get("dry_run","0").lower() in ("1","true","yes"))
    # Muestra un ejemplo fijo; luego lo cambiaremos a las facturas reales.
    sample = [{"to": "+506XXXXXXXX", "message": "Recordatorio: tienes un saldo pendiente."}]

    if dry or request.method == "GET":
        return jsonify({"ok": True, "dry_run": True, "to_send": len(sample), "sample": sample[:2]})

    # Envío real (luego cambiamos sample por los datos reales)
    results = []
    for it in sample:
        try:
            r = _send_whatsapp_text(it["to"], it["message"])
            results.append({"to": it["to"], "status": r.status_code, "ok": r.ok})
        except Exception as e:
            results.append({"to": it["to"], "error": str(e), "ok": False})

    return jsonify({"ok": True, "sent": len(results), "detail": results})

# ---------- Wasender helpers y endpoint de prueba ----------
import os, requests
from flask import request, jsonify

def _safe_json_response(resp):
    try:
        return resp.json()
    except Exception:
        return {"text": resp.text[:400]}

def _send_whatsapp_text(to: str, text: str):
    api_key  = os.getenv("WASENDER_API_KEY", "")
    api_url  = os.getenv("WASENDER_API_URL", "https://api.wasenderapi.com").rstrip("/")
    session  = os.getenv("WASENDER_SESSION", "Noa asistencia")
    headers  = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload  = {"session": session, "to": to, "text": text}
    r = requests.post(f"{api_url}/api/v1/messages/send-text", json=payload, headers=headers, timeout=20)
    return r

@app.route("/notificar-test", methods=["POST"])
def notificar_test():
    """
    JSON: { "to": "+506XXXXXXXX", "message": "texto" }
    """
    data = request.get_json(force=True, silent=True) or {}
    to   = data.get("to")
    msg  = data.get("message")
    if not to or not msg:
        return jsonify({"ok": False, "error": "Falta 'to' o 'message'"}), 400
    try:
        r = _send_whatsapp_text(to, msg)
        return jsonify({"ok": r.ok, "status": r.status_code, "resp": _safe_json_response(r)}), r.status_code
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ---------- Wasender helpers y endpoint de prueba ----------
import os, requests
from flask import request, jsonify

def _safe_json_response(resp):
    try:
        return resp.json()
    except Exception:
        return {"text": resp.text[:400]}

def _send_whatsapp_text(to: str, text: str):
    api_key  = os.getenv("WASENDER_API_KEY", "")
    api_url  = os.getenv("WASENDER_API_URL", "https://api.wasenderapi.com").rstrip("/")
    session  = os.getenv("WASENDER_SESSION", "Noa asistencia")
    headers  = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload  = {"session": session, "to": to, "text": text}
    r = requests.post(f"{api_url}/api/v1/messages/send-text", json=payload, headers=headers, timeout=20)
    return r

@app.route("/notificar-test", methods=["POST"])
def notificar_test():
    """
    Envía un mensaje de prueba a Tony vía WasenderAPI.
    """
    try:
        r = _send_whatsapp_text("+50660457989", "✅ Hola Tony 👋, prueba de Noa Cobros.")
        return jsonify({"ok": r.ok, "status": r.status_code, "resp": _safe_json_response(r)}), r.status_code
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
