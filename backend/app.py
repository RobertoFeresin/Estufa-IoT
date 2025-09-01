import os
import threading
from flask import Flask, jsonify, send_file, request
from flask_cors import CORS
import influx_reader
import influx_writer
import analyzer
import chatbot

INFLUX_HOST = os.getenv("INFLUX_HOST", "influxdb")
INFLUX_DB = os.getenv("INFLUX_DB", "estufa")
EXPORT_PATH = os.getenv("EXPORT_PATH", "/app/exports/sensores.csv")
SIMULATE = os.getenv("SIMULATE", "0") == "1"

app = Flask(__name__)
CORS(app)

@app.route("/health")
def health():
    ok, msg = influx_reader.health_check(INFLUX_HOST, INFLUX_DB)
    return jsonify({"ok": ok, "msg": msg})

@app.route("/dados")
def dados():
    limit = int(request.args.get("limit", 100))
    data = influx_reader.ler_dados(host=INFLUX_HOST, db=INFLUX_DB, limit=limit)
    return jsonify(data)

@app.route("/series")
def series():
    limit = int(request.args.get("limit", 200))
    pts = influx_reader.ler_dados(host=INFLUX_HOST, db=INFLUX_DB, limit=limit)
    return jsonify({
        "time": [p["time"] for p in pts],
        "temperatura": [p["temperatura"] for p in pts],
        "umidade": [p["umidade"] for p in pts],
    })

@app.route("/analise")
def analise():
    limit = int(request.args.get("limit", 200))
    pts = influx_reader.ler_dados(host=INFLUX_HOST, db=INFLUX_DB, limit=limit)
    return jsonify(analyzer.analisar(pts))

@app.route("/seed", methods=["POST"])
def seed():
    n = int(request.args.get("n", 50))
    interval_ms = int(request.args.get("interval_ms", 200))
    written = influx_writer.enviar_lote(
        n=n, interval_ms=interval_ms, host=INFLUX_HOST, db=INFLUX_DB
    )
    return jsonify({"ok": True, "written": written})

@app.route("/export.csv")
def export_csv():
    count = influx_reader.exportar_csv(path=EXPORT_PATH, host=INFLUX_HOST, db=INFLUX_DB)
    return send_file(EXPORT_PATH, mimetype="text/csv", as_attachment=True, download_name="sensores.csv")

@app.route("/chat/<mensagem>")
def chat(mensagem):
    return jsonify({"resposta": chatbot.responder(mensagem)})

def maybe_start_simulation():
    if SIMULATE:
        th = threading.Thread(target=influx_writer.loop, kwargs={
            "host": INFLUX_HOST, "db": INFLUX_DB, "interval_s": 3
        }, daemon=True)
        th.start()

if __name__ == "__main__":
    maybe_start_simulation()
    app.run(host="0.0.0.0", port=5000)
