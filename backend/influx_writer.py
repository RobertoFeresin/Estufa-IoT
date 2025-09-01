from influxdb import InfluxDBClient
import random
import time
import math

def _client(host: str):
    return InfluxDBClient(host=host, port=8086, timeout=5)

def _ensure_db(cli, db: str):
    try:
        cli.create_database(db)
    except Exception:
        pass
    cli.switch_database(db)

def _ponto(tempo_idx: int):
    # Simula sinais suaves + ruído
    base_t = 24 + 4 * math.sin(tempo_idx / 15.0) + random.uniform(-0.4, 0.4)
    base_u = 55 + 7 * math.cos(tempo_idx / 20.0) + random.uniform(-0.7, 0.7)
    return [{
        "measurement": "sensores",
        "tags": {"sensor": "dht22", "estufa": "A"},
        "fields": {
            "temperatura": round(base_t, 2),
            "umidade": round(base_u, 2),
        }
    }]

def enviar_lote(n: int = 50, interval_ms: int = 200, host: str = "influxdb", db: str = "estufa"):
    cli = _client(host)
    _ensure_db(cli, db)
    wrote = 0
    for i in range(n):
        cli.write_points(_ponto(i))
        wrote += 1
        time.sleep(max(0, interval_ms) / 1000.0)
    return wrote

def loop(host: str = "influxdb", db: str = "estufa", interval_s: int = 3):
    cli = _client(host)
    _ensure_db(cli, db)
    i = 0
    while True:
        cli.write_points(_ponto(i))
        i += 1
        time.sleep(interval_s)
