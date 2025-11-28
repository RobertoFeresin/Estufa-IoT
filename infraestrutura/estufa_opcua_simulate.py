#!/usr/bin/env python3
# estufa_opcua_simulate.py
import time, json, random, paho.mqtt.client as mqtt
from datetime import datetime

BROKER = "localhost"
TOPICO_SENSORES = "estufa/sensores"

client = mqtt.Client()
client.connect(BROKER, 1883, 60)

print("[SIMULADOR] Enviando dados falsos para o tópico:", TOPICO_SENSORES)

try:
    while True:
        data = {
            "sensor_id": "sim_01",
            "sensor_data": {
                "temperature": round(random.uniform(20, 35), 2),
                "humidity": round(random.uniform(40, 80), 2),
                "light": round(random.uniform(100, 1000), 2),
                "water_level": round(random.uniform(1, 20), 2)
            },
            "timestamp": datetime.now().isoformat()
        }
        client.publish(TOPICO_SENSORES, json.dumps(data))
        print("[SIMULADOR] Publicado:", data)
        time.sleep(5)
except KeyboardInterrupt:
    print("\nEncerrando simulador...")
finally:
    client.disconnect()
