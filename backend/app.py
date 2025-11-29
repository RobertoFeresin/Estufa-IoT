import os
import threading
import time
from flask import Flask, jsonify, send_file, request, send_from_directory
from flask_cors import CORS
import analyzer
import requests
import json
import base64
import uuid
from datetime import datetime, timedelta
import random

# =========================
# CONFIGURAÇÕES BÁSICAS
# =========================

# Configurações do servidor externo (onde estão os dados da estufa)
EXTERNAL_SERVER_URL = "http://192.168.68.111:5000"
USERNAME = "admin"
PASSWORD = "12345"

# Codificar credenciais para Basic Auth
credentials = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
AUTH_HEADER = {"Authorization": f"Basic {credentials}"}

# URL do Ollama
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434/api/chat")

app = Flask(__name__)
CORS(app, origins=["*"], methods=["GET", "POST"], allow_headers=["Content-Type"])

# =========================
# ESTADO EM MEMÓRIA
# =========================

# Dicionário para armazenar históricos de conversa
conversation_histories = {}

# Cache de dados numéricos
data_cache = {
    'last_update': 0,
    'dados': [],
    'series': {'time': [], 'temperatura': [], 'umidade': []},
    'analise': {}
}

# Flag do sistema
system_ready = False

# =========================
# PARÂMETROS AGRONÔMICOS (TOMATE CEREJA)
# =========================

def get_estufa_parameters():
    """Parâmetros ideais e limiares para controle da estufa (tomate cereja)."""
    return {
        "temperatura": {
            "ideal_min": 18,
            "ideal_max": 25,
            "limiar_inferior": 15,
            "limiar_superior": 28,
            "acao_inferior": "Ligar aquecedor",
            "acao_superior": "Ativar ventilação/exaustor"
        },
        "umidade": {
            "ideal_min": 60,
            "ideal_max": 80,
            "limiar_inferior": 50,
            "limiar_superior": 85,
            "acao_inferior": "Ligar umidificador",
            "acao_superior": "Ventilação forçada"
        },
        "co2": {
            "ideal_min": 800,
            "ideal_max": 1200,
            "limiar_inferior": 800,
            "limiar_superior": 1200,
            "acao_inferior": "Injetar CO₂ (se disponível)",
            "acao_superior": "Ventilar"
        },
        "luminosidade": {
            "ideal_min": 200,
            "ideal_max": 400,
            "limiar_inferior": 200,
            "limiar_superior": 600,
            "acao_inferior": "Ligar LEDs",
            "acao_superior": "Sombrear plantas"
        },
        "umidade_solo": {
            "ideal_min": 20,
            "ideal_max": 30,
            "limiar_inferior": 20,
            "limiar_superior": 35,
            "acao_inferior": "Acionar irrigação",
            "acao_superior": "Parar irrigação"
        },
        "ph_solo": {
            "ideal_min": 5.5,
            "ideal_max": 6.5,
            "limiar_inferior": 5.5,
            "limiar_superior": 6.8,
            "acao_inferior": "Aplicar calcário",
            "acao_superior": "Adicionar enxofre"
        },
        "ec_solo": {
            "ideal_min": 1.5,
            "ideal_max": 3.5,
            "limiar_inferior": 1.5,
            "limiar_superior": 3.5,
            "acao_inferior": "Adubar",
            "acao_superior": "Lavar solo com água"
        }
    }

# =========================
# SISTEMA PREDITIVO DE COLHEITA
# =========================

def calcular_maturidade_planta(dados_estufa, dias_plantio=0):
    """
    Calcula a maturidade da planta baseado nas condições ambientais.
    Retorna dias restantes estimados para colheita.
    """
    if not dados_estufa or not dados_estufa.get("mediaTemperatura"):
        return None
    
    # Parâmetros base para tomate cereja
    ciclo_base = 90  # dias para colheita em condições ideais
    
    # Calcular índice de qualidade atual
    avaliacao, indice_qualidade = avaliar_variaveis_ambiente(dados_estufa)
    
    # Fatores de ajuste baseados nas condições
    fatores_ajuste = {
        'temperatura': 1.0,
        'umidade': 1.0,
        'luminosidade': 1.0,
        'solo': 1.0
    }
    
    # Ajuste por temperatura
    temp_media = dados_estufa.get("mediaTemperatura", 22)
    if 20 <= temp_media <= 25:
        fatores_ajuste['temperatura'] = 0.9  # Acelera em condições ideais
    elif temp_media < 15 or temp_media > 30:
        fatores_ajuste['temperatura'] = 1.3  # Desacelera em condições ruins
    elif temp_media < 18 or temp_media > 28:
        fatores_ajuste['temperatura'] = 1.15  # Desacelera moderadamente
    
    # Ajuste por umidade
    umid_media = dados_estufa.get("mediaUmidade", 65)
    if 60 <= umid_media <= 75:
        fatores_ajuste['umidade'] = 0.95  # Condições ideais
    elif umid_media < 50 or umid_media > 85:
        fatores_ajuste['umidade'] = 1.25  # Condições ruins
    elif umid_media < 55 or umid_media > 80:
        fatores_ajuste['umidade'] = 1.1   # Condições moderadas
    
    # Ajuste por luminosidade
    lum_media = dados_estufa.get("mediaLuminosidade", 300)
    if 250 <= lum_media <= 400:
        fatores_ajuste['luminosidade'] = 0.92  # Condições ideais
    elif lum_media < 150:
        fatores_ajuste['luminosidade'] = 1.3   # Muito escuro
    elif lum_media > 600:
        fatores_ajuste['luminosidade'] = 1.1   # Muito claro
    
    # Ajuste por condições do solo (composto)
    ajuste_solo = 1.0
    if dados_estufa.get("mediaUmidadeSolo"):
        umid_solo = dados_estufa["mediaUmidadeSolo"]
        if 25 <= umid_solo <= 30:
            ajuste_solo *= 0.95
        elif umid_solo < 20 or umid_solo > 35:
            ajuste_solo *= 1.2
    
    if dados_estufa.get("mediaPHSolo"):
        ph_solo = dados_estufa["mediaPHSolo"]
        if 5.8 <= ph_solo <= 6.2:
            ajuste_solo *= 0.95
        elif ph_solo < 5.5 or ph_solo > 6.8:
            ajuste_solo *= 1.15
    
    fatores_ajuste['solo'] = ajuste_solo
    
    # Calcular fator total
    fator_total = (
        fatores_ajuste['temperatura'] * 
        fatores_ajuste['umidade'] * 
        fatores_ajuste['luminosidade'] * 
        fatores_ajuste['solo']
    )
    
    # Dias restantes baseado no ciclo ajustado
    ciclo_ajustado = ciclo_base * fator_total
    dias_restantes = max(0, ciclo_ajustado - dias_plantio)
    
    return {
        'dias_restantes': int(dias_restantes),
        'ciclo_total_estimado': int(ciclo_ajustado),
        'indice_qualidade': indice_qualidade,
        'fatores_ajuste': fatores_ajuste,
        'estagio_maturidade': calcular_estagio_maturidade(dias_plantio, ciclo_ajustado),
        'recomendacoes': gerar_recomendacoes_colheita(fatores_ajuste, dias_restantes)
    }

def calcular_estagio_maturidade(dias_plantio, ciclo_total):
    """Calcula o estágio de maturidade da planta."""
    if dias_plantio == 0:
        return "Plantio recente"
    
    percentual = (dias_plantio / ciclo_total) * 100
    
    if percentual < 25:
        return "Estágio inicial - Crescimento vegetativo"
    elif percentual < 50:
        return "Estágio intermediário - Desenvolvimento"
    elif percentual < 75:
        return "Estágio avançado - Floração e frutificação"
    elif percentual < 90:
        return "Maturação - Frutos em desenvolvimento"
    else:
        return "Pronto para colheita"

def gerar_recomendacoes_colheita(fatores_ajuste, dias_restantes):
    """Gera recomendações baseadas nos fatores de ajuste."""
    recomendacoes = []
    
    if fatores_ajuste['temperatura'] > 1.1:
        recomendacoes.append("Ajustar temperatura para acelerar crescimento")
    elif fatores_ajuste['temperatura'] < 0.95:
        recomendacoes.append("Temperatura ideal mantida")
    
    if fatores_ajuste['umidade'] > 1.1:
        recomendacoes.append("Otimizar umidade para melhor desenvolvimento")
    elif fatores_ajuste['umidade'] < 0.95:
        recomendacoes.append("Umidade em nível excelente")
    
    if fatores_ajuste['luminosidade'] > 1.1:
        recomendacoes.append("Ajustar iluminação para otimizar fotossíntese")
    elif fatores_ajuste['luminosidade'] < 0.95:
        recomendacoes.append("Luminosidade adequada")
    
    if dias_restantes <= 7:
        recomendacoes.append("Preparar para colheita iminente")
    elif dias_restantes <= 14:
        recomendacoes.append("Monitorar frutos diariamente")
    
    return recomendacoes

def gerar_analise_preditiva_colheita(dados_estufa):
    """
    Gera análise preditiva completa para colheita.
    """
    if not dados_estufa:
        return "Não tenho dados suficientes para análise preditiva."
    
    # Simular dias de plantio (em produção real, isso viria de um banco de dados)
    dias_plantio = random.randint(30, 60)
    
    predicao = calcular_maturidade_planta(dados_estufa, dias_plantio)
    
    if not predicao:
        return "Erro ao calcular predição de colheita."
    
    analise = []
    analise.append("🌱 **ANÁLISE PREDITIVA DE COLHEITA**")
    analise.append("")
    analise.append(f"📅 **Dias desde o plantio:** {dias_plantio} dias")
    analise.append(f"🎯 **Estágio atual:** {predicao['estagio_maturidade']}")
    analise.append(f"⏱️ **Dias restantes estimados:** {predicao['dias_restantes']} dias")
    analise.append(f"📊 **Ciclo total previsto:** {predicao['ciclo_total_estimado']} dias")
    analise.append(f"⭐ **Índice de qualidade:** {predicao['indice_qualidade']*10:.1f}/10")
    analise.append("")
    
    # Fatores de influência
    analise.append("**Fatores que influenciam:**")
    fatores = predicao['fatores_ajuste']
    if fatores['temperatura'] > 1.1:
        analise.append(f"🌡️  Temperatura: +{((fatores['temperatura']-1)*100):.0f}% no ciclo")
    elif fatores['temperatura'] < 0.9:
        analise.append(f"🌡️  Temperatura: -{((1-fatores['temperatura'])*100):.0f}% no ciclo")
    else:
        analise.append("🌡️  Temperatura: Ideal")
    
    if fatores['umidade'] > 1.1:
        analise.append(f"💧  Umidade: +{((fatores['umidade']-1)*100):.0f}% no ciclo")
    elif fatores['umidade'] < 0.9:
        analise.append(f"💧  Umidade: -{((1-fatores['umidade'])*100):.0f}% no ciclo")
    else:
        analise.append("💧  Umidade: Ideal")
    
    if fatores['luminosidade'] > 1.1:
        analise.append(f"☀️  Luminosidade: +{((fatores['luminosidade']-1)*100):.0f}% no ciclo")
    elif fatores['luminosidade'] < 0.9:
        analise.append(f"☀️  Luminosidade: -{((1-fatores['luminosidade'])*100):.0f}% no ciclo")
    else:
        analise.append("☀️  Luminosidade: Ideal")
    
    analise.append("")
    
    # Recomendações
    if predicao['recomendacoes']:
        analise.append("💡 **Recomendações:**")
        for rec in predicao['recomendacoes']:
            analise.append(f"• {rec}")
    
    # Previsão de colheita
    data_colheita = datetime.now() + timedelta(days=predicao['dias_restantes'])
    analise.append("")
    analise.append(f"📅 **Previsão de colheita:** {data_colheita.strftime('%d/%m/%Y')}")
    
    return "\n".join(analise)

# =========================
# INTEGRAÇÃO OLLAMA
# =========================

def chamar_ollama(mensagem_usuario, dados_estufa=None, historico_conversa=None):
    """
    Integração real com Ollama para gerar respostas inteligentes.
    """
    try:
        # Preparar o contexto com dados da estufa
        contexto_estufa = ""
        if dados_estufa and dados_estufa.get("mediaTemperatura"):
            contexto_estufa = f"""
Dados atuais da estufa:
- Temperatura: {dados_estufa.get('mediaTemperatura', 'N/A'):.1f}°C (min: {dados_estufa.get('minTemperatura', 'N/A'):.1f}°C, max: {dados_estufa.get('maxTemperatura', 'N/A'):.1f}°C)
- Umidade: {dados_estufa.get('mediaUmidade', 'N/A'):.1f}% (min: {dados_estufa.get('minUmidade', 'N/A'):.1f}%, max: {dados_estufa.get('maxUmidade', 'N/A'):.1f}%)
- Luminosidade: {dados_estufa.get('mediaLuminosidade', 'N/A'):.1f} lux
- Umidade do solo: {dados_estufa.get('mediaUmidadeSolo', 'N/A'):.1f}%
- Nível de água: {dados_estufa.get('mediaNivelAgua', 'N/A'):.1f}%
"""
        
        # Preparar histórico de conversa
        historico_formatado = ""
        if historico_conversa:
            for msg in historico_conversa[-6:]:
                role = "Usuário" if msg['role'] == 'user' else "Assistente"
                historico_formatado += f"{role}: {msg['content']}\n"
        
        # Sistema prompt para orientar o modelo
        sistema_prompt = """Você é um assistente especializado em agricultura de estufa e cultivo de tomate cereja. 
Responda de forma direta e específica sobre o que o usuário perguntar.
Se ele perguntar sobre temperatura, fale apenas sobre temperatura.
Se perguntar sobre umidade, responda apenas sobre umidade.
Só dê a análise completa se o usuário explicitamente pedir.

Seja útil, técnico mas acessível, e sempre baseie suas respostas nos dados disponíveis.
"""
        
        # Construir mensagem final para o Ollama
        mensagem_completa = f"{sistema_prompt}\n\n{contexto_estufa}\n\nHistórico recente:\n{historico_formatado}\nUsuário: {mensagem_usuario}\nAssistente:"
        
        payload = {
            "model": "llama3.2:1b",
            "messages": [
                {
                    "role": "user",
                    "content": mensagem_completa
                }
            ],
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 500
            }
        }
        
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            resultado = response.json()
            return resultado['message']['content'].strip()
        else:
            print(f"Erro Ollama: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Exceção ao chamar Ollama: {e}")
        return None

# =========================
# FUNÇÕES DE INICIALIZAÇÃO
# =========================

def fetch_external_data(endpoint="/registros", params=None):
    """Busca dados no servidor externo com autenticação."""
    try:
        url = f"{EXTERNAL_SERVER_URL}{endpoint}"
        response = requests.get(
            url,
            headers=AUTH_HEADER,
            params=params,
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        else:
            print(f"DEBUG: Erro HTTP ao buscar {endpoint}: {response.status_code}")
            return None
    except Exception as e:
        print(f"DEBUG: Exceção ao buscar dados em {endpoint}: {e}")
        return None

def process_initial_data(data):
    """Processa dados iniciais e popula o cache."""
    if not data:
        return

    processed_data = []
    for item in data:
        try:
            temp = float(item.get("temperatura", 0))
            umid = float(item.get("umidade", 0))
            lum = float(item.get("luminosidade", 0))
            nivel_agua = float(item.get("nivel_alto", 0)) if item.get("nivel_alto") is not None else 0
            
            processed_data.append({
                "timestamp": item.get("timestamp", ""),
                "temperatura": temp,
                "umidade": umid,
                "luminosidade": lum,
                "nivel_reservatorio": nivel_agua
            })
        except (ValueError, TypeError):
            continue

    data_cache['dados'] = processed_data

    if data:
        data_sorted = sorted(data, key=lambda x: x.get("timestamp", ""), reverse=True)
        data_sorted.reverse()

        times, temps, umids = [], [], []

        for item in data_sorted:
            timestamp = item.get("timestamp", "")
            if len(timestamp) > 16:
                times.append(timestamp[11:16])
            else:
                times.append(timestamp)
            try:
                temp = float(item.get("temperatura", 0))
                umid = float(item.get("umidade", 0))
                temps.append(temp)
                umids.append(umid)
            except (ValueError, TypeError):
                continue

        data_cache['series'] = {
            'time': times,
            'temperatura': temps,
            'umidade': umids
        }

    pts = []
    for item in data:
        try:
            pts.append({
                "temperatura": float(item.get("temperatura", 0)),
                "umidade": float(item.get("umidade", 0))
            })
        except (ValueError, TypeError):
            continue

    if pts:
        data_cache['analise'] = analyzer.analisar(pts)

    data_cache['last_update'] = time.time()

def initialize_system():
    """Inicializa o sistema carregando dados reais do servidor externo."""
    global system_ready

    print(" Inicializando sistema...")
    print(" Aguardando 20 dados reais do servidor externo...")

    max_retries = 30
    dados_coletados = 0

    for attempt in range(max_retries):
        try:
            print(f"Tentativa {attempt + 1}/{max_retries} - buscando 20 dados...")
            initial_data = fetch_external_data("/registros", {"limit": 20})

            if initial_data and len(initial_data) >= 20:
                dados_validos = [
                    p for p in initial_data
                    if float(p.get('temperatura', 0)) > 0
                    and float(p.get('umidade', 0)) > 0
                ]
                if len(dados_validos) >= 20:
                    process_initial_data(initial_data)
                    system_ready = True
                    dados_coletados = len(initial_data)
                    print(" Sistema inicializado com sucesso!")
                    print(f" Carregados {dados_coletados} registros reais")
                    break
                else:
                    print(f"Dados válidos insuficientes: {len(dados_validos)}/20")
            else:
                print(f"Dados insuficientes recebidos: {len(initial_data) if initial_data else 0}/20")
        except Exception as e:
            print(f" Erro na tentativa {attempt + 1}: {e}")

        if attempt < max_retries - 1:
            time.sleep(3)

    if not system_ready:
        print("Sistema NÃO inicializado - não foi possível coletar 20 dados reais")
        print("Verifique: conexão com servidor, dados disponíveis, credenciais")
    else:
        print(f"Sistema pronto com {dados_coletados} dados reais!")

# Thread de inicialização
init_thread = threading.Thread(target=initialize_system, daemon=True)
init_thread.start()

# =========================
# GERENCIAMENTO DE CONVERSAS
# =========================

def get_or_create_session(session_id=None):
    """Obtém ou cria uma sessão de conversa."""
    if session_id and session_id in conversation_histories:
        conversation_histories[session_id]['last_activity'] = datetime.now()
        return session_id, conversation_histories[session_id]['history']
    else:
        new_session_id = str(uuid.uuid4())
        conversation_histories[new_session_id] = {
            'history': [],
            'last_activity': datetime.now(),
            'created_at': datetime.now()
        }
        return new_session_id, []

def add_to_history(session_id, role, content):
    """Adiciona uma mensagem ao histórico da sessão."""
    if session_id in conversation_histories:
        conversation_histories[session_id]['history'].append({
            'role': role,
            'content': content,
            'timestamp': datetime.now()
        })
        if len(conversation_histories[session_id]['history']) > 20:
            conversation_histories[session_id]['history'] = conversation_histories[session_id]['history'][-10:]
        conversation_histories[session_id]['last_activity'] = datetime.now()

def cleanup_old_conversations():
    """Remove conversas com mais de 1 hora."""
    now = datetime.now()
    expired_sessions = [
        sid for sid, data in conversation_histories.items()
        if now - data['last_activity'] > timedelta(hours=1)
    ]
    for sid in expired_sessions:
        del conversation_histories[sid]
    print(f"DEBUG: Limpas {len(expired_sessions)} conversas expiradas")

def schedule_cleanup():
    while True:
        threading.Event().wait(1800)
        cleanup_old_conversations()

cleanup_thread = threading.Thread(target=schedule_cleanup, daemon=True)
cleanup_thread.start()

# =========================
# ASSISTENTE AGRONÔMICO / AGENTE ANALÍTICO
# =========================

def obter_dados_estufa_atual(limit=50):
    """
    Busca dados recentes na API externa e calcula médias/min/max para as grandezas.
    """
    data = fetch_external_data("/registros", {"limit": limit})
    if not data:
        return {}

    agregados = {
        "temperatura": [],
        "umidade": [],
        "luminosidade": [],
        "nivel_reservatorio": [],
    }

    for p in data:
        # Temperatura
        if p.get("temperatura") is not None:
            try:
                agregados["temperatura"].append(float(p["temperatura"]))
            except (ValueError, TypeError):
                pass
        
        # Umidade
        if p.get("umidade") is not None:
            try:
                agregados["umidade"].append(float(p["umidade"]))
            except (ValueError, TypeError):
                pass
        
        # Luminosidade
        if p.get("luminosidade") is not None:
            try:
                agregados["luminosidade"].append(float(p["luminosidade"]))
            except (ValueError, TypeError):
                pass
        
        # Nível de água - usando nivel_alto como indicador (0=baixo, 1=alto)
        if p.get("nivel_alto") is not None:
            try:
                # Converter para porcentagem: 0 = 0%, 1 = 100%
                nivel = 100.0 if p["nivel_alto"] else 0.0
                agregados["nivel_reservatorio"].append(nivel)
            except (ValueError, TypeError):
                pass

    resultado = {}
    for chave, valores in agregados.items():
        if not valores:
            continue
        media = sum(valores) / len(valores)
        minimo = min(valores)
        maximo = max(valores)

        if chave == "temperatura":
            resultado["mediaTemperatura"] = media
            resultado["minTemperatura"] = minimo
            resultado["maxTemperatura"] = maximo
        elif chave == "umidade":
            resultado["mediaUmidade"] = media
            resultado["minUmidade"] = minimo
            resultado["maxUmidade"] = maximo
        elif chave == "luminosidade":
            resultado["mediaLuminosidade"] = media
            resultado["minLuminosidade"] = minimo
            resultado["maxLuminosidade"] = maximo
        elif chave == "nivel_reservatorio":
            resultado["mediaNivelAgua"] = media
            resultado["minNivelAgua"] = minimo
            resultado["maxNivelAgua"] = maximo

    return resultado

def avaliar_variavel_individual(nome_variavel, valor):
    """Avalia uma única variável em relação aos parâmetros ideais."""
    params = get_estufa_parameters()
    
    if nome_variavel not in params:
        return None
        
    p = params[nome_variavel]
    
    if valor < p["limiar_inferior"]:
        status = "BAIXO"
        acao = p["acao_inferior"]
        emoji = "🔵"
    elif valor > p["limiar_superior"]:
        status = "ALTO"
        acao = p["acao_superior"]
        emoji = "🔴"
    elif p["ideal_min"] <= valor <= p["ideal_max"]:
        status = "IDEAL"
        acao = None
        emoji = "✅"
    else:
        status = "ACEITÁVEL"
        acao = "Monitorar e ajustar se necessário"
        emoji = "🟡"
    
    return {
        "status": status,
        "acao": acao,
        "emoji": emoji,
        "ideal_min": p["ideal_min"],
        "ideal_max": p["ideal_max"]
    }

def avaliar_variaveis_ambiente(dados_estufa):
    """
    Avalia cada grandeza em relação às faixas ideais/limiares
    e gera um índice de qualidade do ambiente (0 a 1).
    """
    params = get_estufa_parameters()
    avaliacao = {}
    scores = []

    def avalia(nome_campo_media, chave_param):
        media = dados_estufa.get(nome_campo_media)
        if media is None:
            return None
        p = params[chave_param]
        status = ""
        acao = None
        score_local = 0.0

        if media < p["limiar_inferior"]:
            status = "BAIXO"
            acao = p["acao_inferior"]
            score_local = 0.2
        elif media > p["limiar_superior"]:
            status = "ALTO"
            acao = p["acao_superior"]
            score_local = 0.2
        elif p["ideal_min"] <= media <= p["ideal_max"]:
            status = "IDEAL"
            acao = None
            score_local = 1.0
        else:
            status = "ACEITÁVEL"
            acao = "Monitorar e ajustar se necessário"
            score_local = 0.7

        scores.append(score_local)
        return {
            "media": media,
            "status": status,
            "acao": acao,
            "ideal_min": p["ideal_min"],
            "ideal_max": p["ideal_max"]
        }

    avaliacao["temperatura"] = avalia("mediaTemperatura", "temperatura")
    avaliacao["umidade"] = avalia("mediaUmidade", "umidade")
    avaliacao["luminosidade"] = avalia("mediaLuminosidade", "luminosidade")

    if scores:
        indice_qualidade = sum(scores) / len(scores)
    else:
        indice_qualidade = 0.0

    return avaliacao, indice_qualidade

def gerar_resposta_temperatura(dados_estufa):
    """Gera resposta específica para temperatura."""
    if not dados_estufa.get("mediaTemperatura"):
        return "Não tenho dados de temperatura no momento."
    
    temp_atual = dados_estufa["mediaTemperatura"]
    temp_min = dados_estufa.get("minTemperatura", temp_atual)
    temp_max = dados_estufa.get("maxTemperatura", temp_atual)
    
    avaliacao = avaliar_variavel_individual("temperatura", temp_atual)
    
    resposta = f"🌡️ Temperatura atual: {temp_atual:.1f}°C\n"
    resposta += f"📊 Variação: {temp_min:.1f}°C a {temp_max:.1f}°C\n\n"
    
    if avaliacao:
        resposta += f"{avaliacao['emoji']} Status: {avaliacao['status']}\n"
        resposta += f"🎯 Faixa ideal: {avaliacao['ideal_min']}–{avaliacao['ideal_max']}°C\n"
        if avaliacao['acao']:
            resposta += f"💡 Recomendação: {avaliacao['acao']}"
    
    return resposta

def gerar_resposta_umidade(dados_estufa):
    """Gera resposta específica para umidade."""
    if not dados_estufa.get("mediaUmidade"):
        return "Não tenho dados de umidade no momento."
    
    umid_atual = dados_estufa["mediaUmidade"]
    umid_min = dados_estufa.get("minUmidade", umid_atual)
    umid_max = dados_estufa.get("maxUmidade", umid_atual)
    
    avaliacao = avaliar_variavel_individual("umidade", umid_atual)
    
    resposta = f"💧 Umidade atual: {umid_atual:.1f}%\n"
    resposta += f"📊 Variação: {umid_min:.1f}% a {umid_max:.1f}%\n\n"
    
    if avaliacao:
        resposta += f"{avaliacao['emoji']} Status: {avaliacao['status']}\n"
        resposta += f"🎯 Faixa ideal: {avaliacao['ideal_min']}–{avaliacao['ideal_max']}%\n"
        if avaliacao['acao']:
            resposta += f"💡 Recomendação: {avaliacao['acao']}"
    
    return resposta

def gerar_resposta_luminosidade(dados_estufa):
    """Gera resposta específica para luminosidade."""
    if not dados_estufa.get("mediaLuminosidade"):
        return "Não tenho dados de luminosidade no momento."
    
    lum_atual = dados_estufa["mediaLuminosidade"]
    lum_min = dados_estufa.get("minLuminosidade", lum_atual)
    lum_max = dados_estufa.get("maxLuminosidade", lum_atual)
    
    avaliacao = avaliar_variavel_individual("luminosidade", lum_atual)
    
    resposta = f"☀️ Luminosidade atual: {lum_atual:.1f} lux\n"
    resposta += f"📊 Variação: {lum_min:.1f} a {lum_max:.1f} lux\n\n"
    
    if avaliacao:
        resposta += f"{avaliacao['emoji']} Status: {avaliacao['status']}\n"
        resposta += f"🎯 Faixa ideal: {avaliacao['ideal_min']}–{avaliacao['ideal_max']} lux\n"
        if avaliacao['acao']:
            resposta += f"💡 Recomendação: {avaliacao['acao']}"
    
    return resposta

def gerar_resposta_nivel_agua(dados_estufa):
    """Gera resposta específica para nível de água."""
    if not dados_estufa.get("mediaNivelAgua"):
        return "Não tenho dados do nível de água no momento."
    
    nivel = dados_estufa["mediaNivelAgua"]
    nivel_min = dados_estufa.get("minNivelAgua", nivel)
    nivel_max = dados_estufa.get("maxNivelAgua", nivel)
    
    resposta = f"💧 Nível de água: {nivel:.1f}%\n"
    resposta += f"📊 Variação: {nivel_min:.1f}% a {nivel_max:.1f}%\n\n"
    
    if nivel < 20:
        resposta += "🔴 ATENÇÃO: Nível muito baixo! Considere abastecer o reservatório."
    elif nivel < 40:
        resposta += "🟡 Monitorar: Nível está moderado."
    else:
        resposta += "✅ OK: Nível adequado."
    
    return resposta

def is_analytic_query(mensagem_lower):
    """Detecta se a mensagem é sobre dados específicos da estufa."""
    palavras_chave = [
        "temperatura", "umidade", "umido", "úmido", "luminosidade", "luz", "luminosa",
        "solo", "ph", "ec", "condutividade", "co2", "carbono", "água", "agua", "nivel", "nível",
        "reservatorio", "reservatório", "dados", "sensores", "condição", "condicoes", "condições"
    ]
    return any(p in mensagem_lower for p in palavras_chave)

def is_complete_analysis_query(mensagem_lower):
    """Detecta se o usuário quer análise completa."""
    palavras_completas = [
        "análise completa", "analise completa", "relatório completo", "relatorio completo",
        "visão geral", "visao geral", "resumo geral", "tudo sobre", "todas as variáveis",
        "condições completas", "estado geral", "dashboard", "painel completo"
    ]
    return any(p in mensagem_lower for p in palavras_completas)

# =========================
# LÓGICA DO CHAT / AGENTE
# =========================

def gerar_resposta_analitica_completa(dados_estufa):
    """Gera a análise completa (apenas quando explicitamente solicitada)."""
    if not dados_estufa or not dados_estufa.get("mediaTemperatura"):
        return "Não tenho dados suficientes para uma análise completa."

    # Usar a função de avaliação correta
    avaliacao, indice = avaliar_variaveis_ambiente(dados_estufa)
    texto_colheita = gerar_texto_colheita_tomate(indice)

    resposta = []
    resposta.append("📊 RELATÓRIO COMPLETO DA ESTUFA")
    resposta.append("")
    resposta.append(f"⭐ Índice de qualidade: {indice*10:.1f}/10")
    resposta.append("")

    # Adicionar análise de cada variável
    if avaliacao.get("temperatura"):
        temp = avaliacao["temperatura"]
        emoji = "🔵" if temp['status'] == "BAIXO" else "🔴" if temp['status'] == "ALTO" else "✅" if temp['status'] == "IDEAL" else "🟡"
        resposta.append(f"{emoji} Temperatura: {temp['media']:.1f}°C | {temp['status']}")
        if temp['acao']:
            resposta.append(f"   💡 {temp['acao']}")
        resposta.append("")
    
    if avaliacao.get("umidade"):
        umid = avaliacao["umidade"]
        emoji = "🔵" if umid['status'] == "BAIXO" else "🔴" if umid['status'] == "ALTO" else "✅" if umid['status'] == "IDEAL" else "🟡"
        resposta.append(f"{emoji} Umidade: {umid['media']:.1f}% | {umid['status']}")
        if umid['acao']:
            resposta.append(f"   💡 {umid['acao']}")
        resposta.append("")
    
    if avaliacao.get("luminosidade"):
        lum = avaliacao["luminosidade"]
        emoji = "🔵" if lum['status'] == "BAIXO" else "🔴" if lum['status'] == "ALTO" else "✅" if lum['status'] == "IDEAL" else "🟡"
        resposta.append(f"{emoji} Luminosidade: {lum['media']:.1f} lux | {lum['status']}")
        if lum['acao']:
            resposta.append(f"   💡 {lum['acao']}")
        resposta.append("")

    # Nível de água
    if dados_estufa.get("mediaNivelAgua"):
        nivel = dados_estufa["mediaNivelAgua"]
        if nivel < 20:
            resposta.append("🔴 Nível de água: CRÍTICO - Abastecer reservatório")
        elif nivel < 40:
            resposta.append("🟡 Nível de água: MODERADO - Monitorar")
        else:
            resposta.append("✅ Nível de água: ADEQUADO")
        resposta.append("")

    resposta.append(texto_colheita)

    return "\n".join(resposta)

def gerar_resposta_especifica(mensagem_lower, dados_estufa):
    """Gera resposta específica baseada no que foi perguntado."""
    
    # Análise completa (apenas quando explicitamente pedido)
    if is_complete_analysis_query(mensagem_lower):
        return gerar_resposta_analitica_completa(dados_estufa)
    
    # Respostas específicas por variável
    if any(p in mensagem_lower for p in ['temperatura', 'quente', 'frio', 'fria']):
        return gerar_resposta_temperatura(dados_estufa)
    
    elif any(p in mensagem_lower for p in ['umidade', 'úmido', 'umido', 'seco']):
        return gerar_resposta_umidade(dados_estufa)
    
    elif any(p in mensagem_lower for p in ['luminosidade', 'luz', 'luminosa', 'claro', 'escuro']):
        return gerar_resposta_luminosidade(dados_estufa)
    
    elif any(p in mensagem_lower for p in ['água', 'agua', 'nivel', 'nível', 'reservatorio', 'reservatório']):
        return gerar_resposta_nivel_agua(dados_estufa)
    
    elif any(p in mensagem_lower for p in ['dados', 'sensores', 'valores', 'métricas']):
        # Resumo breve dos dados disponíveis
        resposta = "📈 Dados disponíveis:\n\n"
        if dados_estufa.get("mediaTemperatura"):
            resposta += f"🌡️ Temperatura: {dados_estufa['mediaTemperatura']:.1f}°C\n"
        if dados_estufa.get("mediaUmidade"):
            resposta += f"💧 Umidade: {dados_estufa['mediaUmidade']:.1f}%\n"
        if dados_estufa.get("mediaLuminosidade"):
            resposta += f"☀️ Luminosidade: {dados_estufa['mediaLuminosidade']:.1f} lux\n"
        if dados_estufa.get("mediaNivelAgua"):
            resposta += f"💧 Nível de água: {dados_estufa['mediaNivelAgua']:.1f}%\n"
        
        resposta += "\n💡 Pergunte por uma variável específica para mais detalhes!"
        return resposta
    
    # Se não identificou uma variável específica, usar Ollama
    return None

def gerar_texto_colheita_tomate(indice_qualidade):
    """Gera texto sobre projeção de colheita."""
    ciclo_base_min = 85
    ciclo_base_max = 95

    if indice_qualidade >= 0.85:
        tipo = "acelerado"
        fator = 0.85
        emoji = "⚡"
    elif indice_qualidade >= 0.65:
        tipo = "normal" 
        fator = 1.0
        emoji = "📅"
    else:
        tipo = "lento"
        fator = 1.15
        emoji = "🐌"

    dias_min = int(ciclo_base_min * fator)
    dias_max = int(ciclo_base_max * fator)

    texto = []
    texto.append(f"{emoji} Projeção de colheita para tomate cereja")
    texto.append(f"📊 {tipo.capitalize()} - estimativa: {dias_min} a {dias_max} dias")
    
    return "\n".join(texto)

def gerar_resposta_inteligente(mensagem, dados_estufa=None, historico_conversa=None):
    """
    Agente principal de resposta ATUALIZADO:
    - Respostas específicas para variáveis individuais
    - Análise completa apenas quando explicitamente pedido
    - Ollama para outras conversas
    - Análise preditiva automática no final
    """
    mensagem_lower = mensagem.lower().strip()

    # Primeiro tentar resposta específica
    resposta_especifica = gerar_resposta_especifica(mensagem_lower, dados_estufa or {})
    
    resposta_final = resposta_especifica
    
    # Se não for resposta específica, tentar Ollama
    if not resposta_especifica:
        try:
            resposta_ollama = chamar_ollama(mensagem, dados_estufa, historico_conversa)
            if resposta_ollama and len(resposta_ollama.strip()) > 10:
                resposta_final = resposta_ollama
        except Exception as e:
            print(f"Fallback para regras - Erro Ollama: {e}")

    # Fallback para sistema baseado em regras
    if not resposta_final:
        if any(p in mensagem_lower for p in ['oi', 'olá', 'ola', 'hey', 'hello', 'bom dia', 'boa tarde', 'boa noite']):
            resposta_final = (
                "👋 Olá! Sou o assistente inteligente da Estufa IoT.\n\n"
                "🌱 Posso te dar informações específicas sobre:\n"
                "• 🌡️ Temperatura atual e recomendações\n"
                "• 💧 Umidade do ar\n" 
                "• ☀️ Luminosidade e condições de luz\n"
                "• 💧 Nível da água no reservatório\n\n"
                "💡 Pergunte por exemplo: *\"qual é a temperatura?\"* ou *\"como está a umidade?\"*"
            )
        else:
            resposta_final = (
                "🤖 Assistente de Estufa Inteligente\n\n"
                "🌱 Posso te ajudar com informações específicas sobre:\n\n"
                "🌡️ Temperatura atual e histórica\n"
                "💧 Umidade do ar\n" 
                "☀️ Luminosidade e condições de luz\n"
                "💧 Nível de água\n\n"
                "💡 Pergunte sobre qualquer uma dessas variáveis!"
            )

    # ADICIONAR ANÁLISE PREDITIVA AUTOMATICAMENTE NO FINAL
    # Apenas se for uma pergunta sobre condições atuais e tivermos dados
    if dados_estufa and dados_estufa.get("mediaTemperatura"):
        # Verificar se a mensagem é sobre condições atuais (não cumprimentos, etc)
        if (is_analytic_query(mensagem_lower) and 
            not any(p in mensagem_lower for p in ['oi', 'olá', 'ola', 'hey', 'hello', 'bom dia', 'boa tarde', 'boa noite'])):
            
            analise_preditiva = gerar_analise_preditiva_colheita(dados_estufa)
            resposta_final += "\n\n" + "="*50 + "\n\n"
            resposta_final += analise_preditiva

    return resposta_final

# =========================
# ROTAS DE SAÚDE / DEBUG
# =========================

@app.route("/health")
def health():
    try:
        test_response = fetch_external_data("/registros", {"limit": 1})
        conexao_externa = test_response is not None
        
        # Testar conexão com Ollama também
        test_ollama = requests.get(OLLAMA_URL.replace('/api/chat', '/api/tags'), timeout=5)
        ollama_ok = test_ollama.status_code == 200
        
    except:
        conexao_externa = False
        ollama_ok = False

    status = {
        "ok": system_ready,
        "msg": "Sistema pronto" if system_ready else "Sistema inicializando",
        "dados_carregados": len(data_cache['dados']) if system_ready else 0,
        "conexao_externa": conexao_externa,
        "ollama_conectado": ollama_ok,
        "modo_ia": True
    }
    return jsonify(status)

@app.route("/init-status")
def init_status():
    status = {
        "system_ready": system_ready,
        "dados_carregados": len(data_cache['dados']),
        "exige_20_dados": True,
        "mensagem": "Sistema pronto com 20 dados reais" if system_ready else "Aguardando 20 dados reais do servidor externo",
        "ollama_integrado": True
    }
    return jsonify(status)

@app.route("/debug")
def debug():
    data = fetch_external_data("/registros", {"limit": 5})
    
    # Testar Ollama
    ollama_status = "desconhecido"
    try:
        test = requests.get(OLLAMA_URL.replace('/api/chat', '/api/tags'), timeout=5)
        ollama_status = "conectado" if test.status_code == 200 else f"erro {test.status_code}"
    except Exception as e:
        ollama_status = f"erro: {str(e)}"
    
    return jsonify({
        "dados_brutos": data,
        "quantidade": len(data) if data else 0,
        "system_ready": system_ready,
        "cache_size": len(data_cache['dados']),
        "ollama_status": ollama_status,
        "conversations_active": len(conversation_histories)
    })

# =========================
# ROTAS DE DADOS / CSV
# =========================

@app.route("/dados")
def dados():
    limit = int(request.args.get("limit", 20))
    try:
        if not system_ready:
            return jsonify([])

        data = fetch_external_data("/registros", {"limit": limit})
        if data:
            processed_data = []
            for item in data:
                try:
                    temp = float(item.get("temperatura", 0))
                    umid = float(item.get("umidade", 0))
                    lum = float(item.get("luminosidade", 0))
                    nivel_agua = 100.0 if item.get("nivel_alto") else 0.0
                    
                    processed_data.append({
                        "timestamp": item.get("timestamp", ""),
                        "temperatura": temp,
                        "umidade": umid,
                        "luminosidade": lum,
                        "nivel_reservatorio": nivel_agua
                    })
                except (ValueError, TypeError):
                    continue

            if len(processed_data) >= 20:
                data_cache['dados'] = processed_data
                data_cache['last_update'] = time.time()

            return jsonify(processed_data)

        if len(data_cache['dados']) >= 20:
            return jsonify(data_cache['dados'][-limit:])
        else:
            return jsonify([])

    except Exception as e:
        print(f"DEBUG: Erro em /dados: {e}")
        return jsonify([])

@app.route("/series")
def series():
    limit = int(request.args.get("limit", 20))
    try:
        if not system_ready:
            return jsonify({'time': [], 'temperatura': [], 'umidade': []})

        data = fetch_external_data("/registros", {"limit": limit})
        if data:
            data_sorted = sorted(data, key=lambda x: x.get("timestamp", ""), reverse=True)
            if limit and len(data_sorted) > limit:
                data_sorted = data_sorted[:limit]
            data_sorted.reverse()

            times, temps, umids = [], [], []
            for item in data_sorted:
                timestamp = item.get("timestamp", "")
                if len(timestamp) > 16:
                    times.append(timestamp[11:16])
                else:
                    times.append(timestamp)
                try:
                    temps.append(float(item.get("temperatura", 0)))
                    umids.append(float(item.get("umidade", 0)))
                except (ValueError, TypeError):
                    continue

            series_data = {
                "time": times,
                "temperatura": temps,
                "umidade": umids,
            }

            if len(temps) >= 20 and len(umids) >= 20:
                data_cache['series'] = series_data
                data_cache['last_update'] = time.time()

            return jsonify(series_data)

        if len(data_cache['series']['temperatura']) >= 20:
            return jsonify(data_cache['series'])
        else:
            return jsonify({'time': [], 'temperatura': [], 'umidade': []})

    except Exception as e:
        print(f"DEBUG: Erro em /series: {e}")
        return jsonify({'time': [], 'temperatura': [], 'umidade': []})

@app.route("/analise")
def analise():
    limit = int(request.args.get("limit", 20))
    try:
        if not system_ready:
            return jsonify({})

        data = fetch_external_data("/registros", {"limit": limit})
        if data:
            pts = []
            for item in data:
                try:
                    pts.append({
                        "temperatura": float(item.get("temperatura", 0)),
                        "umidade": float(item.get("umidade", 0))
                    })
                except (ValueError, TypeError):
                    continue

            if pts and len(pts) >= 20:
                result = analyzer.analisar(pts)
                data_cache['analise'] = result
                data_cache['last_update'] = time.time()
                return jsonify(result)

        if data_cache['analise'] and data_cache['analise'].get('temperatura', {}).get('media', 0) > 0:
            return jsonify(data_cache['analise'])
        else:
            return jsonify({})

    except Exception as e:
        print(f"DEBUG: Erro em /analise: {e}")
        return jsonify({})

@app.route("/dados_completos")
def dados_completos():
    limit = int(request.args.get("limit", 10))
    try:
        data = fetch_external_data("/registros", {"limit": limit})
        if data:
            return jsonify(data)
        return jsonify({"erro": "Sem dados disponíveis"})
    except Exception as e:
        return jsonify({"erro": f"Falha ao buscar dados: {e}"}), 500

@app.route("/export.csv")
def export_csv():
    try:
        data = fetch_external_data("/registros")
        if data:
            export_path = "/app/exports/sensores.csv"
            os.makedirs(os.path.dirname(export_path), exist_ok=True)

            import csv
            with open(export_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["timestamp", "temperatura", "umidade", "luminosidade", "nivel_reservatorio",
                            "bomba", "valvula", "luminaria", "ventilador", "exaustor", "emergencia"])
                for p in data:
                    w.writerow([
                        p.get("timestamp", ""),
                        p.get("temperatura", 0),
                        p.get("umidade", 0),
                        p.get("luminosidade", 0),
                        100.0 if p.get("nivel_alto") else 0.0,
                        p.get("bomba", 0),
                        p.get("valvula", 0),
                        p.get("luminaria", 0),
                        p.get("ventilador", 0),
                        p.get("exaustor", 0),
                        p.get("emergencia", 0)
                    ])

            return send_file(
                export_path,
                mimetype="text/csv",
                as_attachment=True,
                download_name="sensores_completos.csv"
            )

        return jsonify({"erro": "Falha ao exportar dados"}), 500
    except Exception as e:
        return jsonify({"erro": f"Falha na exportação: {e}"}), 500

# =========================
# CHAT
# =========================

@app.route("/chat", methods=["POST"])
def chat():
    """
    Chat da Estufa IoT ATUALIZADO:
    - Respostas específicas para cada variável
    - Análise completa apenas quando pedido
    - Geração de relatórios quando solicitado
    """
    try:
        data = request.get_json(force=True)
        raw_msg = data.get("mensagem", "").strip()
        session_id = data.get("session_id")

        if not raw_msg:
            return jsonify({"erro": "mensagem vazia"}), 400

        # Verificar se é solicitação de relatório
        mensagem_lower = raw_msg.lower()
        if any(p in mensagem_lower for p in ['download', 'baixar', 'relatório', 'relatorio', 'exportar', 'csv', 'planilha']):
            # Gerar relatório
            resultado_relatorio = gerar_relatorio()
            if resultado_relatorio.status_code == 200:
                dados_relatorio = resultado_relatorio.get_json()
                
                # Adicionar ao histórico
                session_id, conversation_history = get_or_create_session(session_id)
                add_to_history(session_id, "user", raw_msg)
                add_to_history(session_id, "assistant", 
                              f"📊 Relatório gerado com sucesso! \n\n"
                              f"📁 Arquivo: {dados_relatorio['arquivo']}\n"
                              f"📈 Contém: Dados atuais + análise completa + histórico de sensores\n\n"
                              f"⬇️ [Baixar Relatório]({dados_relatorio['caminho']})")
                
                return jsonify({
                    "resposta": f"📊 Relatório gerado com sucesso! \n\n"
                               f"📁 Arquivo: {dados_relatorio['arquivo']}\n"
                               f"📈 Contém: Dados atuais + análise completa + histórico de sensores\n\n"
                               f"⬇️ [Baixar Relatório]({dados_relatorio['caminho']})",
                    "session_id": session_id,
                    "modo_ia": True,
                    "tem_relatorio": True,
                    "url_download": dados_relatorio['caminho']
                })
            else:
                return jsonify({
                    "resposta": "❌ Desculpe, não consegui gerar o relatório no momento. Tente novamente mais tarde.",
                    "session_id": session_id,
                    "modo_ia": False
                })

        # Sessão normal
        session_id, conversation_history = get_or_create_session(session_id)

        # Dados atuais da estufa
        dados_estufa = {}
        try:
            dados_estufa = obter_dados_estufa_atual(limit=50)
        except Exception as e:
            print(f"DEBUG: erro ao obter dados da estufa: {e}")

        # Gera resposta INTELIGENTE com tratamento de erro
        try:
            resposta = gerar_resposta_inteligente(
                raw_msg, 
                dados_estufa, 
                conversation_history
            )
        except Exception as e:
            print(f"Erro ao gerar resposta: {e}")
            resposta = "👋 Olá! Sou o assistente da Estufa IoT. Posso te ajudar com informações sobre temperatura, umidade, luminosidade e outras condições da estufa. Pergunte algo como 'qual é a temperatura?'"

        # Histórico
        add_to_history(session_id, "user", raw_msg)
        add_to_history(session_id, "assistant", resposta)

        return jsonify({
            "resposta": resposta,
            "session_id": session_id,
            "modo_ia": True
        })

    except Exception as e:
        print(f"DEBUG: Erro geral em /chat: {e}")
        return jsonify({
            "resposta": "👋 Olá! Sou o assistente da Estufa IoT. Como posso ajudar você hoje?",
            "modo_ia": False
        })

# =========================
# OUTRAS ROTAS
# =========================

@app.route("/test-ollama")
def test_ollama():
    """Testa conexão com Ollama de forma mais completa."""
    try:
        # Testar listagem de modelos
        models_response = requests.get(
            OLLAMA_URL.replace('/api/chat', '/api/tags'),
            timeout=10
        )
        
        if models_response.status_code == 200:
            modelos = models_response.json().get('models', [])
            modelo_nomes = [m['name'] for m in modelos]
            
            # Testar geração simples
            test_payload = {
                "model": "llama3.2:1b",
                "prompt": "Responda brevemente: Qual é sua especialidade?",
                "stream": False
            }

            r = requests.post(
                OLLAMA_URL.replace('/api/chat', '/api/generate'),
                json=test_payload,
                timeout=15
            )

            if r.status_code == 200:
                return jsonify({
                    "status": "conectado", 
                    "modelos_disponiveis": modelo_nomes,
                    "resposta_teste": r.json().get('response', 'OK')
                })
            else:
                return jsonify({
                    "status": "erro_geracao", 
                    "code": r.status_code,
                    "modelos_disponiveis": modelo_nomes
                })
        else:
            return jsonify({"status": "erro_conexao", "code": models_response.status_code})

    except Exception as e:
        return jsonify({"status": "erro", "details": str(e)})

@app.route("/conversations")
def list_conversations():
    """Lista conversas ativas (debug)."""
    active_sessions = {}
    for session_id, data in conversation_histories.items():
        active_sessions[session_id] = {
            'message_count': len(data['history']),
            'last_activity': data['last_activity'].isoformat(),
            'created_at': data['created_at'].isoformat(),
            'last_messages': [msg['content'][:50] + '...' for msg in data['history'][-3:]]
        }
    return jsonify(active_sessions)

@app.route("/gerar-relatorio", methods=["POST"])
def gerar_relatorio():
    """Gera um relatório CSV com dados atuais e análise da IA."""
    try:
        data = request.get_json(force=True)
        mensagem = data.get("mensagem", "").lower().strip()
        session_id = data.get("session_id")
        
        # Verificar se é uma solicitação de download/relatório
        if not any(p in mensagem for p in ['download', 'baixar', 'relatório', 'relatorio', 'exportar', 'csv']):
            return jsonify({"erro": "Não é uma solicitação de relatório"}), 400
        
        # Buscar dados atuais
        dados_estufa = obter_dados_estufa_atual(limit=100)
        dados_completos = fetch_external_data("/registros", {"limit": 100})
        
        if not dados_completos:
            return jsonify({"erro": "Não foi possível obter dados para o relatório"}), 500
        
        # Gerar análise da IA
        analise_ia = gerar_resposta_analitica_completa(dados_estufa)
        
        # Criar diretório de exports se não existir
        export_dir = "/app/exports"
        os.makedirs(export_dir, exist_ok=True)
        
        # Nome do arquivo com timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"relatorio_estufa_{timestamp}.csv"
        filepath = os.path.join(export_dir, filename)
        
        # Gerar CSV
        import csv
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            
            # Cabeçalho
            writer.writerow(["RELATÓRIO DA ESTUFA INTELIGENTE"])
            writer.writerow([f"Data de geração: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"])
            writer.writerow([])
            
            # Dados resumidos atuais
            writer.writerow(["DADOS ATUAIS DA ESTUFA"])
            if dados_estufa.get("mediaTemperatura"):
                writer.writerow(["Temperatura média:", f"{dados_estufa['mediaTemperatura']:.1f}°C"])
            if dados_estufa.get("mediaUmidade"):
                writer.writerow(["Umidade média:", f"{dados_estufa['mediaUmidade']:.1f}%"])
            if dados_estufa.get("mediaLuminosidade"):
                writer.writerow(["Luminosidade média:", f"{dados_estufa['mediaLuminosidade']:.1f} lux"])
            if dados_estufa.get("mediaNivelAgua"):
                writer.writerow(["Nível de água médio:", f"{dados_estufa['mediaNivelAgua']:.1f}%"])
            writer.writerow([])
            
            # Análise da IA
            writer.writerow(["ANÁLISE DO ASSISTENTE INTELIGENTE"])
            for linha in analise_ia.split('\n'):
                if linha.strip():
                    writer.writerow([linha.strip()])
            writer.writerow([])
            
            # Dados completos
            writer.writerow(["DADOS COMPLETOS DOS SENSORES"])
            writer.writerow(["Timestamp", "Temperatura", "Umidade", "Luminosidade", "Nível Água", "Bomba", "Válvula", "Luminária", "Ventilador", "Exaustor", "Emergência"])
            
            for registro in dados_completos:
                writer.writerow([
                    registro.get("timestamp", ""),
                    registro.get("temperatura", ""),
                    registro.get("umidade", ""),
                    registro.get("luminosidade", ""),
                    100.0 if registro.get("nivel_alto") else 0.0,
                    registro.get("bomba", ""),
                    registro.get("valvula", ""),
                    registro.get("luminaria", ""),
                    registro.get("ventilador", ""),
                    registro.get("exaustor", ""),
                    registro.get("emergencia", "")
                ])
        
        # Adicionar ao histórico do chat se houver sessão
        if session_id and session_id in conversation_histories:
            mensagem_relatorio = f"Relatório gerado com sucesso! Arquivo: {filename}"
            add_to_history(session_id, "system", mensagem_relatorio)
        
        return jsonify({
            "mensagem": "Relatório gerado com sucesso!",
            "arquivo": filename,
            "caminho": f"/download-relatorio/{filename}"
        })
        
    except Exception as e:
        print(f"Erro ao gerar relatório: {e}")
        return jsonify({"erro": f"Falha ao gerar relatório: {str(e)}"}), 500

@app.route("/download-relatorio/<filename>")
def download_relatorio(filename):
    """Faz download do relatório gerado."""
    try:
        return send_file(
            f"/app/exports/{filename}",
            mimetype="text/csv",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({"erro": f"Arquivo não encontrado: {str(e)}"}), 404

@app.route("/analise-preditiva", methods=["GET"])
def analise_preditiva():
    """Rota específica para análise preditiva de colheita."""
    try:
        dados_estufa = obter_dados_estufa_atual(limit=50)
        analise = gerar_analise_preditiva_colheita(dados_estufa)
        
        return jsonify({
            "analise": analise,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "erro": f"Falha ao gerar análise preditiva: {str(e)}"
        }), 500

# Servir frontend estático
@app.route("/")
def index():
    return send_from_directory("../frontend", "index.html")

@app.route("/<path:path>")
def static_proxy(path):
    return send_from_directory("../frontend", path)

# =========================
# MAIN
# =========================

if __name__ == "__main__":
    print(f"Backend iniciado - Conectando ao servidor externo: {EXTERNAL_SERVER_URL}")
    print(f"Ollama URL: {OLLAMA_URL}")
    print("Sistema de inicialização ativado...")
    print(" Modo: Respostas específicas por variável + Análise Preditiva")
    app.run(host="0.0.0.0", port=5000, debug=True)