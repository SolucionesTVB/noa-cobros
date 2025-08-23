from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Ruta de prueba para saber si el servidor está vivo
@app.get("/")
def health():
    return "Servidor vivo ✅"

# Ruta principal de IA
@app.post("/ia/resumen-cobro")
def resumen_cobro():
    data = request.get_json() or {}
    texto = data.get("texto", "")
    return jsonify({
        "ok": True,
        "respuesta": f"Resumen IA: {texto[:60]}... Cliente A debe ₡75,000. Fecha límite: 30/08."
    })

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5055, debug=True)

