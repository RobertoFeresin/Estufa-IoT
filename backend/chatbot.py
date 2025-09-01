def responder(mensagem: str) -> str:
    m = mensagem.lower()
    if "temperatura" in m:
        return "A temperatura é atualizada a cada poucos segundos e você pode ver a média em /analise."
    if "umidade" in m:
        return "A umidade está sob controle; veja os dados em tempo real no gráfico."
    if "export" in m or "csv" in m:
        return "Use /export.csv para baixar os dados e abrir no VSCode."
    return "Sou um bot de demonstração da estufa. Pergunte sobre temperatura, umidade ou export."
