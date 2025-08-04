
# 🌱 Estufa-IoT

O **Estufa-IoT** é um projeto de demonstração que simula um sistema IoT para coleta e visualização de dados.

Ele é composto por dois serviços:

- **🔧 Backend**: API em Node.js (Express) com SQLite e Python para geração dos dados, empacotada com Podman.
- **💻 Frontend**: Interface em React que consome os dados da API e exibe em uma tabela.

---

## 📁 Estrutura do Projeto

```plaintext
Estufa-IoT
├── backend
│   ├── Dockerfile           # Dockerfile para o backend
│   ├── server.js            # Servidor Express
│   ├── script.coleta.py     # Script Python que popula o banco
│   ├── dados_imagem.db      # Banco SQLite (opcional, pode ser gerado)
│   ├── package.json         # Dependências do backend
│   └── ...
└── frontend
    ├── src/                 # Código React
    ├── public/              # Arquivos estáticos
    ├── package.json         # Dependências do frontend
    └── ...
````


## ⚙️ Tecnologias Utilizadas

| Componente | Tecnologias                        |
| ---------- | ---------------------------------- |
| Backend    | Node.js, Express, SQLite, Python 3 |
| Frontend   | React, Axios                       |
| Containers | Podman (alternativa ao Docker)     |

---

## 🚀 Como Executar o Projeto

### 🔽 1. Clone o repositório

```bash
git clone git@github.com:RobertoFeresin/Estufa-IoT.git
cd Estufa-IoT
```

---

### 🐍 2. Rodar o Backend com Podman

```bash
cd backend
podman build -t estufa-backend .
podman run -p 3001:3001 estufa-backend
```

> A API estará acessível em: [http://localhost:3001/dados](http://localhost:3001/dados)

---

### 💻 3. Rodar o Frontend em modo de desenvolvimento

```bash
cd ../frontend
npm install
npm start
```

> Acesse: [http://localhost:3000](http://localhost:3000)


## 🔄 Fluxo de Funcionamento

```plaintext
[ script.coleta.py ] → Gera banco SQLite com dados simulados
        ↓
[ server.js ] → Exposição da API REST /dados
        ↓
[ React (frontend) ] → Consome a API e exibe os dados na interface
```

## 📦 (Opcional) Empacotar o Frontend com Podman

```bash
cd frontend
npm run build
podman build -t estufa-frontend .
podman run -p 3000:80 estufa-frontend
```

> Interface acessível em: [http://localhost:3000](http://localhost:3000)

---

## ✨ Melhorias Futuras

* ✅ Implementar OCR real com Tesseract para leitura de texto de imagem
* ✅ Orquestração com `podman-compose`
* ✅ Autenticação de usuários
* ✅ Dashboard com gráficos e dados dinâmicos
* ✅ Deploy em ambientes externos (Render, Railway, VPS, etc.)

---

## 👤 Autor

**Roberto Tini de Azevedo Feresin**
📍 São Paulo - SP
📬 [robertoferesin12@gmail.com](mailto:robertoferesin12@gmail.com)
🌐 [github.com/RobertoFeresin](https://github.com/RobertoFeresin)

---

## 📄 Licença

Este projeto é livre para fins educacionais e demonstrativos.


