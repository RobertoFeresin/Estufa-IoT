import requests
import json
import logging

# Endereços dos serviços
OLLAMA_URL = "http://localhost:11434/api/chat"
BACKEND_URL = "http://192.168.68.111:5000"  # IP do servidor Flask real

def responder(mensagem: str) -> str:
    """
    IA responde com base nos dados REAIS vindos da rota /registros.
    Nenhum dado aleatório é gerado.
    """
    try:
        # Tenta buscar dados reais
        try:
            registros = requests.get(f"{BACKEND_URL}/registros", timeout=5).json()
        except Exception as e:
            logging.error(f"Erro ao buscar registros: {e}")
            registros = []

        # Monta resumo dos dados reais
        if registros:
            ultimos = registros[-5:]  # últimas 5 leituras
            medias = {
                "temperatura": sum(r.get("temperatura", 0) for r in registros) / len(registros),
                "umidade": sum(r.get("umidade", 0) for r in registros) / len(registros),
            }
            resumo = (
                f"Temperatura média: {medias['temperatura']:.2f}°C, "
                f"Umidade média: {medias['umidade']:.2f}%. "
                f"Últimas leituras: " +
                "; ".join([f"{r['temperatura']}°C/{r['umidade']}%" for r in ultimos])
            )
        else:
            resumo = "Nenhum registro encontrado até o momento."

        # Envia prompt para o Ollama
        payload = {
            "model": "qwen2:1.5b",
            "stream": False,
            "options": {"num_predict": 150, "temperature": 0.6},
            "messages": [
                {
                    "role": "system",
                    "content": "Você é um assistente da Estufa IoT. Use dados da rota /registros para responder. Sempre fale em português do Brasil."
                },
                {
                    "role": "user",
                    "content": f"{mensagem}\n\nContexto dos sensores: {resumo}"
                }
            ]
        }

        r = requests.post(OLLAMA_URL, headers={"Content-Type": "application/json"}, data=json.dumps(payload), timeout=60)

        if r.status_code == 200:
            data = r.json()
            resposta = data.get("message", {}).get("content") or data.get("response")
            if resposta:
                return resposta.strip()

        logging.warning(f"Falha na IA: {r.status_code} - {r.text}")
        return resposta_padrao(mensagem)

    except Exception as e:
        logging.error(f"Erro ao conectar com IA: {e}")
        return resposta_padrao(mensagem)


def resposta_padrao(mensagem: str) -> str:
    m = mensagem.lower()
    if "temperatura" in m:
        return "Os dados da temperatura estão sendo coletados diretamente do sistema da estufa."
    if "umidade" in m:
        return "Os valores de umidade estão sendo atualizados em tempo real pela rota /registros."
    return "Sou o assistente da Estufa IoT 🌱. Posso responder sobre temperatura, umidade e condições dos sensores."
