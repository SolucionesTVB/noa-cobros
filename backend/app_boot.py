from flask import Flask, request, jsonify
from flask_cors import CORS
import io

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
    # Intentar leer CSV sin pandas (para evitar líos de dependencias)
    content = f.read().decode("utf-8", errors="ignore")
    rows = []
    for i, line in enumerate(content.splitlines()):
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(",")]
        if i == 0:
            # cabecera esperada: Cliente,Monto,Vence,Estado
            continue
        # Normalizar mínimo
        cliente = parts[0] if len(parts) > 0 else ""
        try:
            monto = float(parts[1]) if len(parts) > 1 and parts[1] else 0.0
        except:
            monto = 0.0
        vence = parts[2] if len(parts) > 2 else ""
        estado = parts[3] if len(parts) > 3 else "Pendiente"
        rows.append({"Cliente": cliente, "Monto": monto, "Vence": vence, "Estado": estado})
    return jsonify({"ok": True, "rows": rows})
