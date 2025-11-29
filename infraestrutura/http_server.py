#!/usr/bin/env python3
from flask import Flask, jsonify, request, Response
import csv, json, os
from pathlib import Path

# --- CONFIGURAÇÃO DE LOGIN ---
USERNAME = "admin"
PASSWORD = "12345"

# --- Caminhos de dados ---
BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / "data"
JSON_REGISTROS = DATA_DIR / "registros.json"
JSON_ESTADO = DATA_DIR / "estado.json"

app = Flask(__name__)

# --- Autenticação básica ---
def check_auth(username, password):
    return username == USERNAME and password == PASSWORD

def authenticate():
    return Response(
        "Acesso restrito. Informe usuário e senha.", 401,
        {"WWW-Authenticate": 'Basic realm="Estufa IoT"'}
    )

def requires_auth(f):
    def wrapper(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# --- Rotas ---
@app.route("/")
@requires_auth
def home():
    return jsonify({
        "message": "API Estufa IoT rodando com autenticação.",
        "endpoints": ["/estado", "/registros"]
    })

@app.route("/estado")
@requires_auth
def estado():
    if not JSON_ESTADO.exists():
        return jsonify({"erro": "Arquivo estado.json não encontrado"}), 404
    with open(JSON_ESTADO, "r") as f:
        return jsonify(json.load(f))

@app.route("/registros")
@requires_auth
def registros():
    if not JSON_REGISTROS.exists():
        return jsonify({"erro": "Arquivo registros.csv não encontrado"}), 404
    limit = int(request.args.get("limit", 20))
    rows = []
    with open(JSON_REGISTROS, "r") as f:
        historico = json.load(f)

    # Caso o arquivo esteja vazio ou corrompido
    if not isinstance(historico,list):
        return jsonify([])
    return jsonify(historico[-limit:])

if __name__ == "__main__":
    print(f"Servidor HTTP rodando em todas as interfaces (porta 5000)")
    print(f"Acesso protegido - use usuário: {USERNAME} senha: {PASSWORD}")
    app.run(host="0.0.0.0", port=5000)
