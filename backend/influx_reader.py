from influxdb import InfluxDBClient
from datetime import datetime, timezone
import csv
import os

def _client(host: str):
    return InfluxDBClient(host=host, port=8086, timeout=5)

def _ensure_db(cli, db: str):
    try:
        cli.create_database(db)
    except Exception:
        pass
    cli.switch_database(db)

def health_check(host: str, db: str):
    try:
        cli = _client(host)
        pong = cli.ping()
        _ensure_db(cli, db)
        return True, f"influxdb ok ({pong})"
    except Exception as e:
        return False, f"erro: {e}"

def ler_dados(host: str, db: str, limit: int = 100):
    cli = _client(host)
    _ensure_db(cli, db)
    q = f'SELECT "temperatura","umidade" FROM "sensores" ORDER BY time DESC LIMIT {int(limit)}'
    res = cli.query(q)
    pts = list(res.get_points())
    # Normaliza e devolve em ordem cronológica (asc)
    pts = pts[::-1]
    for p in pts:
        # p["time"] já vem em ISO 8601 (UTC). Apenas certifica chaves.
        p["temperatura"] = float(p.get("temperatura", 0.0))
        p["umidade"] = float(p.get("umidade", 0.0))
    return pts
