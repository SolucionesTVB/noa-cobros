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
