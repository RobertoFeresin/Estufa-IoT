#!/home/pi4b/Desktop/Estufa-Iot/infraestrutura/venv/bin/python3
# -*- coding: utf-8 -*-
"""
Estufa Inteligente - Bridge MQTT -> OPC UA + Controle GPIO + CSV
Recebe sensores via MQTT e disponibiliza via OPC UA; controla relés via GPIO.
Mantém duplo comando por relé (cmd_on / cmd_off) e feedbacks (ativado/desativado).
"""

import os
import sys
import csv
import json
import time
import logging
import logging.handlers
import asyncio
import threading
from datetime import datetime


EXPECTED_PYTHON = "/home/pi4b/Desktop/Estufa-Iot/infraestrutura/venv/bin/python3"
if sys.executable != EXPECTED_PYTHON:
    print(f"[AVISO] Recomenda-se executar com: {EXPECTED_PYTHON} (python atual: {sys.executable})")

# -------------------------
# dependências: paho.mqtt, asyncua, RPi.GPIO
# -------------------------
try:
    import paho.mqtt.client as mqtt
except Exception:
    raise SystemExit("paho-mqtt não instalado no venv. Ative venv e 'pip install paho-mqtt'")

try:
    import RPi.GPIO as GPIO
except Exception:
    class _MockGPIO:
        BCM = "BCM"
        OUT = "OUT"
        LOW = False
        HIGH = True
        def setmode(self, mode): print(f"[SIM] GPIO setmode {mode}")
        def setwarnings(self, val): pass
        def setup(self, pin, mode): print(f"[SIM] GPIO setup {pin} {mode}")
        def output(self, pin, state): print(f"[SIM] GPIO out {pin} -> {'HIGH' if state else 'LOW'}")
        def cleanup(self): print("[SIM] GPIO cleanup")
    GPIO = _MockGPIO()

# asyncua (OPC UA)
try:
    from asyncua import Server
except Exception:
    raise SystemExit("asyncua não instalado no venv. Ative venv e 'pip install asyncua'")

# -------------------------
# Paths / logging / csv
# -------------------------
BASE_DIR = "/home/pi4b/Desktop/Estufa-Iot/infraestrutura"
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(BASE_DIR, exist_ok=True)
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "estufa_opcua.log")
JSON_ESTADO = os.path.join(DATA_DIR, "estado.json")
JSON_REGISTRO = os.path.join(DATA_DIR,"registros.json")

logger = logging.getLogger("estufa")
logger.setLevel(logging.INFO)
fh = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
fh.setFormatter(fmt)
logger.addHandler(fh)
logger.addHandler(logging.StreamHandler())

# -------------------------
# GPIO pins (BCM)
# -------------------------
PINS = {
    "bomba": 17,
    "valvula": 25,
    "luminaria": 27,
    "ventilador": 22,
    "exaustor": 23,
    "emergencia": 24
}

# init gpio
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
for name, pin in PINS.items():
    try:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)
    except Exception:
        logger.exception("Erro ao configurar pino %s (%s). Continuando em modo simulacao.", name, pin)

# -------------------------
# variáveis de processo e setpoints
# -------------------------
dados = {
    "temperatura": None,
    "umidade": None,
    "luminosidade": None,
    "umidade_solo": None,
    "nivel_baixo": False,
    "nivel_alto": False
}

setpoints = {
    "temperatura_setpoint": 30.0,
    "umidade_setpoint": 70.0,
    "luminosidade_setpoint": 300.0,
    "umidade_solo_setpoint": 45.0
}
TOLERANCIA = 1.0

estado_reles = {n: False for n in PINS.keys()}
feedbacks = {}
for n in PINS.keys():
    feedbacks[f"{n}_fb_ativado"] = False
    feedbacks[f"{n}_fb_desativado"] = True

alarmes = {
    "alarme_temperatura_baixo": False,
    "alarme_temperatura_alto": False,
    "alarme_umidade_baixo": False,
    "alarme_umidade_alto": False,
    "alarme_luminosidade_baixo": False,
    "alarme_luminosidade_alto": False,
    "alarme_umidade_solo_baixo": False,
    "alarme_umidade_solo_alto": False
}

modo_manual = False
liga_geral = True

# MQTT
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "estufa/sensores"
mqtt_client = mqtt.Client()

data_lock = threading.Lock()

# -------------------------
# funções utilitárias
# -------------------------
def registrar_json_row():
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "temperatura":dados.get("temperatura"),
        "umidade": dados.get("umidade"),
        "luminosidade": dados.get("luminosidade"),
        "umidade_solo":dados.get("umidade_solo"),
        "nivel_baixo":bool(dados.get("nivel_baixo")),
        "nivel_alto": bool(dados.get("nivel_alto")),
        #Estado do relés
        "bomba": int(bool(estado_reles["bomba"])),
        "valvula": int(bool(estado_reles["valvula"])),
        "luminaria": int(bool(estado_reles["luminaria"])),
        "ventilador": int(bool(estado_reles["ventilador"])),
        "exaustor": int(bool(estado_reles["exaustor"])),
        "emergencia": int(bool(estado_reles["emergencia"])),
        # Feedbacka
        "bomba_fb_ativado": int(bool(feedbacks["bomba_fb_ativado"])),       
        "bomba_fb_desativado": int(bool(feedbacks["bomba_fb_desativado"])),
        "valvula_fb_ativado": int(bool(feedbacks["valvula_fb_ativado"])),
        "valvula_fb_desativado": int(bool(feedbacks["valvula_fb_desativado"])),
        "luminaria_fb_ativado": int(bool(feedbacks["luminaria_fb_ativado"])),
        "luminaria_fb_desativado": int(bool(feedbacks["luminaria_fb_desativado"])),
        "ventilador_fb_ativado": int(bool(feedbacks["ventilador_fb_ativado"])),
        "ventilador_fb_desativado": int(bool(feedbacks["ventilador_fb_desativado"])),
        "exaustor_fb_ativado": int(bool(feedbacks["exaustor_fb_ativado"])),
        "exaustor_fb_desativado": int(bool(feedbacks["exaustor_fb_desativado"])),
        "emergencia_fb_ativado": int(bool(feedbacks["emergencia_fb_ativado"])),
        "emergencia_fb_desativado": int(bool(feedbacks["emergencia_fb_desativado"])),
        #Alarmes
        "alarme_temperatura_baixo": int(bool(alarmes["alarme_temperatura_baixo"])),
        "alarme_temperatura_alto": int(bool(alarmes["alarme_temperatura_alto"])),
        "alarme_umidade_baixo": int(bool(alarmes["alarme_umidade_baixo"])),
        "alarme_umidade_alto": int(bool(alarmes["alarme_umidade_alto"])),
        "alarme_luminosidade_baixo": int(bool(alarmes["alarme_luminosidade_baixo"])),
        "alarme_luminosidade_alto": int(bool(alarmes["alarme_luminosidade_alto"])),
        "alarme_umidade_solo_baixo": int(bool(alarmes["alarme_umidade_solo_baixo"])),
        "alarme_umidade_solo_alto": int(bool(alarmes["alarme_umidade_solo_alto"])),
    }

    estado_path = os.path.join(DATA_DIR,"estado.json")
    with open(estado_path, "w") as f:
        json.dump(entry, f, indent=2)

    registros_path = os.path.join(DATA_DIR,"registros.json")

    if os.path.isfile(registros_path):
        with open(registros_path, "r") as f:
           try:
               historico = json.load(f)
               if not isinstance(historico, list):
                   historico = []
           except Exception:
               historico = []

    else:
        historico = []

    historico.append(entry)

    with open(registros_path, "w") as f:
        json.dump(historico, f,indent=2)





def atualizar_hardware(nome, estado: bool):
    if nome not in PINS:
        logger.error("Atualizacao hardware solicitada para nome inválido: %s", nome)
        return
    try:
        GPIO.output(PINS[nome], GPIO.HIGH if estado else GPIO.LOW)
    except Exception:
        logger.exception("Falha ao escrever pino %s", nome)
    estado_reles[nome] = bool(estado)
    feedbacks[f"{nome}_fb_ativado"] = bool(estado)
    feedbacks[f"{nome}_fb_desativado"] = not bool(estado)
    logger.info("Hardware %s -> %s", nome, "ON" if estado else "OFF")

def atualizar_alarmes():
    with data_lock:
        for sp_key, sp in setpoints.items():
            var = sp_key.replace("_setpoint", "")
            val = dados.get(var)
            if val is None:
                alarmes[f"alarme_{var}_baixo"] = False
                alarmes[f"alarme_{var}_alto"] = False
            else:
                alarmes[f"alarme_{var}_baixo"] = val < (sp - TOLERANCIA)
                alarmes[f"alarme_{var}_alto"] = val > (sp + TOLERANCIA)

def controle_automatico():
    global modo_manual, liga_geral
    if modo_manual or not liga_geral:
        return
    atualizar_alarmes()
    with data_lock:
        sp = setpoints["umidade_solo_setpoint"]
        um_solo = dados.get("umidade_solo")
        if um_solo is not None:
            if um_solo < (sp - TOLERANCIA):
                atualizar_hardware("bomba", True)
            elif um_solo > (sp + TOLERANCIA):
                atualizar_hardware("bomba", False)
        if dados.get("nivel_baixo"):
            atualizar_hardware("valvula", True)
        elif dados.get("nivel_alto"):
            atualizar_hardware("valvula", False)
        sp_l = setpoints["luminosidade_setpoint"]
        light = dados.get("luminosidade")
        if light is not None:
            if light < (sp_l - TOLERANCIA):
                atualizar_hardware("luminaria", True)
            elif light > (sp_l + TOLERANCIA):
                atualizar_hardware("luminaria", False)
        sp_t = setpoints["temperatura_setpoint"]
        temp = dados.get("temperatura")
        if temp is not None:
            if temp > (sp_t + TOLERANCIA):
                atualizar_hardware("ventilador", True)
                atualizar_hardware("exaustor", True)
            elif temp < (sp_t - TOLERANCIA):
                atualizar_hardware("ventilador", False)
                atualizar_hardware("exaustor", False)

# -------------------------
# MQTT callbacks
# -------------------------
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Conectado ao broker MQTT %s:%s", MQTT_BROKER, MQTT_PORT)
        client.subscribe(MQTT_TOPIC)
    else:
        logger.error("Falha MQTT. rc=%s", rc)

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
    except Exception:
        logger.exception("Payload MQTT inválido")
        return
    with data_lock:
        if "sensor_data" in payload:
            payload = payload["sensor_data"]
        if "humidity" in payload:
            dados["umidade"] = payload.get("humidity")
        if "light" in payload:
            dados["luminosidade"] = payload.get("light")
        if "temperature" in payload:
            dados["temperatura"] = payload.get("temperature")
        if "soil_moisture" in payload:
            dados["umidade_solo"] = payload.get("soil_moisture")
        if "nivel_baixo" in payload:
            dados["nivel_baixo"] = bool(payload.get("nivel_baixo"))
        if "nivel_alto" in payload:
            dados["nivel_alto"] = bool(payload.get("nivel_alto"))
    logger.debug("MQTT recebido e atualizado: %s", payload)

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

def iniciar_mqtt():
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
    except Exception:
        logger.exception("Erro conectando ao MQTT broker")

# -------------------------
# OPC UA server (async)
# -------------------------
async def servidor_opcua():
    global modo_manual, liga_geral
    server = Server()
    await server.init()
    
    # LINHAS CORRIGIDAS - Removidas as chamadas set_certificate e set_private_key
    # server.set_certificate(None)  # REMOVIDO
    # server.set_private_key(None)  # REMOVIDO
    
    # Endpoint corrigido para usar 0.0.0.0
    server.set_endpoint("opc.tcp://0.0.0.0:4840/estufa/")
    server.set_server_name("Estufa Inteligente - OPC UA")

    ns = await server.register_namespace("EstufaInteligente")
    obj = await server.nodes.objects.add_object(ns, "Estufa")

    sensor_vars = {}
    for k in ["temperatura", "umidade", "luminosidade", "umidade_solo", "nivel_baixo", "nivel_alto"]:
        sensor_vars[k] = await obj.add_variable(ns, k, dados.get(k, 0.0))
        await sensor_vars[k].set_writable(False)

    setpoint_vars = {}
    for k, v in setpoints.items():
        setpoint_vars[k] = await obj.add_variable(ns, k, v)
        await setpoint_vars[k].set_writable(True)

    rele_cmd_on = {}
    rele_cmd_off = {}
    rele_state_vars = {}
    for n in PINS.keys():
        rele_cmd_on[n] = await obj.add_variable(ns, f"{n}_cmd_on", False)
        await rele_cmd_on[n].set_writable(True)
        rele_cmd_off[n] = await obj.add_variable(ns, f"{n}_cmd_off", False)
        await rele_cmd_off[n].set_writable(True)
        rele_state_vars[n] = await obj.add_variable(ns, f"{n}_state", False)
        await rele_state_vars[n].set_writable(False)

    feedback_vars = {}
    for fb_name, fb_val in feedbacks.items():
        feedback_vars[fb_name] = await obj.add_variable(ns, fb_name, fb_val)
        await feedback_vars[fb_name].set_writable(False)

    alarme_vars = {}
    for a_name, a_val in alarmes.items():
        alarme_vars[a_name] = await obj.add_variable(ns, a_name, a_val)
        await alarme_vars[a_name].set_writable(False)

    modo_manual_var = await obj.add_variable(ns, "modo_manual", modo_manual)
    await modo_manual_var.set_writable(True)
    liga_geral_var = await obj.add_variable(ns, "liga_geral", liga_geral)
    await liga_geral_var.set_writable(True)

    logger.info("OPC UA iniciado em opc.tcp://0.0.0.0:4840/estufa/")

    async with server:
        while True:
            try:
                atualizar_alarmes()
                with data_lock:
                    for k, var in sensor_vars.items():
                        await var.write_value(dados.get(k))
                for n, var in rele_state_vars.items():
                    await var.write_value(estado_reles[n])
                for name, var in feedback_vars.items():
                    await var.write_value(feedbacks[name])
                for name, var in alarme_vars.items():
                    await var.write_value(alarmes[name])

                for k, var in setpoint_vars.items():
                    setpoints[k] = await var.read_value()
                modo_manual = await modo_manual_var.read_value()
                liga_geral = await liga_geral_var.read_value()

                for n in PINS.keys():
                    v_on = await rele_cmd_on[n].read_value()
                    v_off = await rele_cmd_off[n].read_value()
                    if v_on:
                        atualizar_hardware(n, True)
                        await rele_cmd_on[n].write_value(False)
                    if v_off:
                        atualizar_hardware(n, False)
                        await rele_cmd_off[n].write_value(False)

                if not modo_manual:
                    controle_automatico()

                if not liga_geral:
                    for n in PINS.keys():
                        atualizar_hardware(n, False)

                registrar_json_row()
                await asyncio.sleep(60)
            except Exception:
                logger.exception("Erro no loop OPC UA")
                await asyncio.sleep(5)

# -------------------------
# MAIN
# -------------------------
def main():
    iniciar_mqtt()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(servidor_opcua())
    except KeyboardInterrupt:
        logger.info("Interrompido pelo usuário")
    finally:
        try:
            mqtt_client.loop_stop()
        except Exception:
            pass
        GPIO.cleanup()

if __name__ == "__main__":
    main()
