

## Ferramentas Utilizadas

- **Podman** → gerencia os containers  
- **InfluxDB** → banco de dados para séries temporais  
- **Flask (Python)** → backend simulando sensores, exportando API e CSV  
- **Nginx** → servidor web do frontend em produção  
- **Vite (Node.js)** → ambiente de desenvolvimento do frontend  
- **VSCode** → usado como editor, abrindo CSV exportados ou explorando via extensões  

---

## Fluxo de Funcionamento

1. O **InfluxDB** roda em um container e armazena dados de séries temporais.  
2. O **Backend Flask** roda em outro container:  
   - Simula sensores de **temperatura** e **umidade**  
   - Escreve esses dados no InfluxDB  
   - Disponibiliza endpoints (`/dados`, `/analise`, `/series`, `/chat`, `/export.csv`)  
3. O **Frontend** (HTML/JS) roda via **Nginx**:  
   - Consome os dados da API  
   - Mostra gráficos, tabelas e chatbot  
4. O usuário pode **exportar dados em CSV** e abrir no VSCode.  

---

## Como Rodar

### 1. Pré-requisitos
- Podman instalado
- Node.js 20+ (para rodar `npm run dev` ou `npm run build`)

### 2. Script automático
Na raiz do projeto:
```bash
chmod +x reset.sh
./reset.sh
````

Esse script:

* Remove containers e imagens antigas
* Rebuilda o backend
* Recria a rede
* Sobe InfluxDB, Backend e Frontend

### 3. URLs de acesso

* **Backend API** → [http://localhost:5000/dados](http://localhost:5000/dados)
* **Frontend (site)** → [http://localhost:8081](http://localhost:8081)
* **InfluxDB (ping)** → [http://localhost:8086/ping](http://localhost:8086/ping)

---

## Endpoints Backend

* `/dados` → últimos registros
* `/series` → séries para gráficos
* `/analise` → estatísticas básicas
* `/seed` (POST) → gera dados de teste
* `/export.csv` → exporta para CSV
* `/chat/<mensagem>` → chatbot simples

---

## Desenvolvimento Frontend

Dentro da pasta `frontend`:

```bash
npm install
npm run dev     # ambiente de desenvolvimento
npm run build   # gera ./dist para produção
```

Produção é servida pelo Nginx no container (porta 8081).

---

## Observação

* Este projeto é **acadêmico** e não deve ser usado em produção.
* O InfluxDB salva arquivos binários em `data/` → estes são **ignorados no Git**.
* Apenas o código fonte e scripts são versionados.


